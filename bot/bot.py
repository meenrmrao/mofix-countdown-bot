"""
MOFIX Countdown Bot
--------------------
Aiogram-based Telegram bot that keeps a single pinned message per countdown
up to date, edited in place every minute (no spam). When a countdown hits
zero it edits the message to the "live" announcement and posts a fresh
announcement message.

Run with:  python run_bot.py
"""
import asyncio
import contextlib
import logging
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramConflictError, TelegramRetryAfter
from aiogram.filters import CommandStart
from aiogram.types import Message

from common.config import config
from common.db import init_db
from common.utils import format_countdown_message, remaining_parts
from bot import repository as repo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mofix.bot")

dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "🚀 <b>MOFIX Countdown Bot</b>\n\n"
        "I keep countdown messages updated automatically.\n"
        "Manage countdowns from the admin web dashboard."
    )


@dp.message(F.text == "/status")
async def cmd_status(message: Message):
    active = repo.get_active_countdowns()
    if not active:
        await message.answer("No active countdowns right now.")
        return
    lines = ["📊 <b>Active countdowns</b>"]
    for c in active:
        _, _, _, _, secs = remaining_parts(c.target_datetime_utc)
        lines.append(f"• {c.name} — {secs // 3600}h remaining")
    await message.answer("\n".join(lines))


async def sync_countdown(bot: Bot, countdown):
    """Post/pin if needed, then edit the message text or finalize it."""
    if not countdown.chat_id:
        return

    _, _, _, _, total_seconds = remaining_parts(countdown.target_datetime_utc)
    text = format_countdown_message(countdown)

    try:
        # No message posted yet -> send + pin it
        if not countdown.message_id:
            sent = await bot.send_message(countdown.chat_id, text)
            await bot.pin_chat_message(countdown.chat_id, sent.message_id, disable_notification=True)
            repo.update_countdown_fields(
                countdown.id, message_id=sent.message_id, is_pinned=True
            )
            countdown.message_id = sent.message_id
        else:
            try:
                await bot.edit_message_text(
                    chat_id=countdown.chat_id,
                    message_id=countdown.message_id,
                    text=text,
                )
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e).lower():
                    raise

        # Countdown finished -> finalize
        if total_seconds <= 0:
            announcement = await bot.send_message(
                countdown.chat_id, countdown.announcement_text or "🎉 We're live!"
            )
            repo.mark_completed(countdown.id, announcement_message_id=announcement.message_id)
            logger.info("Countdown '%s' completed and announced.", countdown.name)

    except TelegramRetryAfter as e:
        logger.warning("Rate limited, sleeping %s seconds", e.retry_after)
        await asyncio.sleep(e.retry_after)
    except Exception as e:
        logger.exception("Failed to sync countdown '%s': %s", countdown.name, e)
        repo.heartbeat(error=str(e))


async def countdown_loop(bot: Bot, stop_event: asyncio.Event):
    """Background loop: runs every UPDATE_INTERVAL_SECONDS.

    Writes a heartbeat immediately on startup (so the dashboard flips to
    "Online" right away instead of waiting up to UPDATE_INTERVAL_SECONDS),
    then on every cycle. When a restart is requested from the dashboard,
    this sets `stop_event` and returns instead of calling sys.exit()
    directly — sys.exit() here would only kill *this* asyncio task (since
    it runs as a separate task from dp.start_polling()), not the process,
    which used to leave the bot polling forever with a permanently frozen
    heartbeat after the first restart click. The actual process exit now
    happens once in main(), after both tasks have been cleanly stopped.
    """
    repo.heartbeat()

    while not stop_event.is_set():
        try:
            active = repo.get_active_countdowns()
            for countdown in active:
                await sync_countdown(bot, countdown)
            repo.heartbeat()

            if repo.should_restart():
                logger.info("Restart requested from dashboard. Stopping for supervisor restart.")
                repo.clear_restart_flag()
                stop_event.set()
                break

        except Exception as e:
            logger.exception("Error in countdown loop: %s", e)
            repo.heartbeat(error=str(e))

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=config.UPDATE_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass  # normal case: just means it's time for the next cycle


async def main():
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN is not set. Please configure your .env file.")
        sys.exit(1)

    init_db()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Clear any leftover webhook and drop stale pending updates before
    # polling. A dangling webhook (or an old, unreleased getUpdates session
    # from a previous instance that crashed mid-poll, e.g. during a Railway
    # rolling redeploy) is the most common real-world cause of
    # "TelegramConflictError: terminated by other getUpdates request" — this
    # makes sure Telegram's server-side state is clean before we start.
    await bot.delete_webhook(drop_pending_updates=True)

    stop_event = asyncio.Event()
    loop_task = asyncio.create_task(countdown_loop(bot, stop_event))
    polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=True))

    logger.info("MOFIX Countdown Bot started. Polling for commands...")

    done, pending = await asyncio.wait(
        {loop_task, polling_task}, return_when=asyncio.FIRST_COMPLETED
    )

    # Whichever finished first (a restart request via loop_task, or the
    # poller stopping/erroring), cleanly cancel the other side rather than
    # leaving an orphaned task running.
    for task in pending:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    await bot.session.close()

    conflict_error = None
    for task in done:
        if task is polling_task:
            exc = task.exception() if not task.cancelled() else None
            if isinstance(exc, TelegramConflictError):
                conflict_error = exc
            elif exc is not None:
                raise exc

    if conflict_error is not None:
        logger.error(
            "TelegramConflictError: another instance of this bot is already "
            "polling with the same BOT_TOKEN ('terminated by other getUpdates "
            "request'). This means two processes are polling at once — check "
            "for a duplicate Railway service/replica, a leftover local "
            "`python run_bot.py`, or a second deployment still shutting down. "
            "Exiting so only one instance remains; the platform's process "
            "supervisor should not restart this into a conflict loop once "
            "the duplicate is stopped."
        )
        sys.exit(1)

    if stop_event.is_set():
        logger.info("Exiting for supervisor restart.")
        sys.exit(0)

    # polling_task ended on its own without an exception and without a
    # restart being requested (e.g. graceful shutdown signal) — exit clean.
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
