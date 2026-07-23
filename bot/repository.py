"""
MOFIX Countdown Bot - Repository helpers for the bot process.
Keeps SQLAlchemy session handling out of the bot/scheduler logic.
"""
import datetime as dt

from common.db import get_session
from common.models import Countdown, BotStatus, BOT_STATUS_SINGLETON_ID


def _get_or_create_status(session):
    """Fetch the single BotStatus row (fixed id), creating it if missing.

    Using the fixed singleton id — instead of `.query(BotStatus).first()` —
    guarantees the bot always reads/writes the exact same row the web
    dashboard reads, even if a duplicate row was ever created by a race
    at startup.
    """
    status = session.get(BotStatus, BOT_STATUS_SINGLETON_ID)
    if not status:
        status = BotStatus(id=BOT_STATUS_SINGLETON_ID)
        session.add(status)
    return status


def get_active_countdowns():
    with get_session() as session:
        rows = session.query(Countdown).filter_by(status="active").all()
        session.expunge_all()
        return rows


def get_countdown(countdown_id: int):
    with get_session() as session:
        row = session.query(Countdown).filter_by(id=countdown_id).first()
        if row:
            session.expunge(row)
        return row


def update_countdown_fields(countdown_id: int, **fields):
    with get_session() as session:
        session.query(Countdown).filter_by(id=countdown_id).update(
            fields, synchronize_session=False
        )


def mark_completed(countdown_id: int, announcement_message_id: int = None):
    fields = {"status": "completed"}
    if announcement_message_id is not None:
        fields["announcement_message_id"] = announcement_message_id
    update_countdown_fields(countdown_id, **fields)


def heartbeat(error: str = None):
    with get_session() as session:
        status = _get_or_create_status(session)
        status.last_heartbeat = dt.datetime.utcnow()
        if error is not None:
            status.last_error = error


def should_restart() -> bool:
    with get_session() as session:
        status = session.get(BotStatus, BOT_STATUS_SINGLETON_ID)
        return bool(status and status.restart_requested)


def clear_restart_flag():
    with get_session() as session:
        status = session.get(BotStatus, BOT_STATUS_SINGLETON_ID)
        if status:
            status.restart_requested = False
