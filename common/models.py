"""
MOFIX Countdown Bot - Database Models
"""
import datetime as dt

from sqlalchemy import (Boolean, Column, DateTime, Integer, String, Text)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def utcnow():
    return dt.datetime.utcnow()


class Admin(Base):
    """Dashboard administrator account."""
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utcnow)


class Countdown(Base):
    """A single countdown event tracked by the bot and shown on the site."""
    __tablename__ = "countdowns"

    id = Column(Integer, primary_key=True)

    # Basic info
    name = Column(String(120), nullable=False)
    slug = Column(String(120), unique=True, nullable=False)
    title_line = Column(String(200), default="MOFIX AUTH TOOL")
    subtitle_line = Column(String(200), default="Release Countdown")
    live_message = Column(String(200), default="MOFIX AUTH TOOL IS NOW LIVE!")
    announcement_text = Column(Text, default="The wait is over! 🎉")

    # Schedule
    target_datetime_utc = Column(DateTime, nullable=False)
    timezone = Column(String(64), default="Asia/Kolkata")

    # Telegram wiring
    chat_id = Column(String(64), nullable=True)      # e.g. -1001234567890 or @channel
    message_id = Column(Integer, nullable=True)      # pinned message id once posted
    is_pinned = Column(Boolean, default=False)
    announcement_message_id = Column(Integer, nullable=True)

    # State: active | stopped | completed
    # NOTE: every countdown is automatically saved as ACTIVE the moment it is
    # created (see web/app.py::_save_countdown_from_form). "draft" used to be
    # the default here, but nothing in the UI ever offered a way to move a
    # countdown out of "draft", and /api/countdowns (which the public page's
    # JS depends on for its target time) only returns "active"/"completed"
    # rows — so a countdown stuck on the old "draft" default was invisible to
    # the public page's timer and rendered as a frozen 00:00:00:00 forever.
    status = Column(String(20), default="active")

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "title_line": self.title_line,
            "subtitle_line": self.subtitle_line,
            "live_message": self.live_message,
            "announcement_text": self.announcement_text,
            "target_datetime_utc": self.target_datetime_utc.isoformat() if self.target_datetime_utc else None,
            "timezone": self.timezone,
            "chat_id": self.chat_id,
            "message_id": self.message_id,
            "is_pinned": self.is_pinned,
            "status": self.status,
        }


#: BotStatus is meant to be a single-row table. We pin that one row to a
#: fixed, known primary key instead of relying on "whichever row happens to
#: be first" (`.first()` has no ORDER BY, so on a table with more than one
#: row — e.g. if the web and bot processes ever raced and each inserted
#: their own row — it can non-deterministically return a stale row that
#: nobody is updating, making the dashboard show "Offline" forever even
#: though the bot is heartbeating into a different row). All reads/writes
#: of BotStatus should go through this fixed id.
BOT_STATUS_SINGLETON_ID = 1


class BotStatus(Base):
    """Singleton row used by the web dashboard to know if the bot is alive."""
    __tablename__ = "bot_status"

    id = Column(Integer, primary_key=True)
    last_heartbeat = Column(DateTime, default=utcnow)
    restart_requested = Column(Boolean, default=False)
    started_at = Column(DateTime, default=utcnow)
    last_error = Column(Text, nullable=True)
