"""
MOFIX Countdown Bot - Repository helpers for the bot process.
Keeps SQLAlchemy session handling out of the bot/scheduler logic.
"""
import datetime as dt

from common.db import get_session
from common.models import Countdown, BotStatus


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
        session.query(Countdown).filter_by(id=countdown_id).update(fields)


def mark_completed(countdown_id: int, announcement_message_id: int = None):
    fields = {"status": "completed"}
    if announcement_message_id is not None:
        fields["announcement_message_id"] = announcement_message_id
    update_countdown_fields(countdown_id, **fields)


def heartbeat(error: str = None):
    with get_session() as session:
        status = session.query(BotStatus).first()
        if not status:
            status = BotStatus()
            session.add(status)
        status.last_heartbeat = dt.datetime.utcnow()
        if error is not None:
            status.last_error = error

def should_restart() -> bool:
    with get_session() as session:
        status = session.query(BotStatus).first()
        return bool(status and status.restart_requested)


def clear_restart_flag():
    with get_session() as session:
        status = session.query(BotStatus).first()
        if status:
            status.restart_requested = False
