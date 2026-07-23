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
import datetime as dt
import logging
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
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

    days, hours, minutes, _, total_seconds = remaining_parts(countdown.target_datetime_utc)
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


async def countdown_loop(bot: Bot):
    """Background loop: runs every UPDATE_INTERVAL_SECONDS."""
    while True:
        try:
            active = repo.get_active_countdowns()
            for countdown in active:
                await sync_countdown(bot, countdown)
            repo.heartbeat()

            if repo.should_restart():
                logger.info("Restart requested from dashboard. Exiting for supervisor restart.")
                repo.clear_restart_flag()
                sys.exit(0)

        except Exception as e:
            logger.exception("Error in countdown loop: %s", e)
            repo.heartbeat(error=str(e))

        await asyncio.sleep(config.UPDATE_INTERVAL_SECONDS)


async def main():
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN is not set. Please configure your .env file.")
        sys.exit(1)

    init_db()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    asyncio.create_task(countdown_loop(bot))

    logger.info("MOFIX Countdown Bot started. Polling for commands...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
