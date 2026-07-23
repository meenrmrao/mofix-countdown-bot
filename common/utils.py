"""
MOFIX Countdown Bot - Shared utility helpers
"""
import datetime as dt
import re

from werkzeug.security import generate_password_hash, check_password_hash
from zoneinfo import ZoneInfo


def hash_password(raw: str) -> str:
    return generate_password_hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return check_password_hash(hashed, raw)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "countdown"


def local_to_utc(naive_local_dt: dt.datetime, tz_name: str) -> dt.datetime:
    """Convert a naive datetime (as picked in the dashboard, in tz_name) to naive UTC."""
    tz = ZoneInfo(tz_name)
    aware_local = naive_local_dt.replace(tzinfo=tz)
    aware_utc = aware_local.astimezone(ZoneInfo("UTC"))
    return aware_utc.replace(tzinfo=None)


def utc_to_local(naive_utc_dt: dt.datetime, tz_name: str) -> dt.datetime:
    aware_utc = naive_utc_dt.replace(tzinfo=ZoneInfo("UTC"))
    aware_local = aware_utc.astimezone(ZoneInfo(tz_name))
    return aware_local.replace(tzinfo=None)


def remaining_parts(target_utc: dt.datetime, now_utc: dt.datetime = None):
    """Return (days, hours, minutes, seconds, total_seconds) remaining. Clamped at 0."""
    now_utc = now_utc or dt.datetime.utcnow()
    delta = target_utc - now_utc
    total_seconds = max(0, int(delta.total_seconds()))
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    return days, hours, minutes, seconds, total_seconds


def format_countdown_message(countdown, now_utc: dt.datetime = None) -> str:
    """Build the pinned Telegram message text for a countdown."""
    days, hours, minutes, _, total_seconds = remaining_parts(countdown.target_datetime_utc, now_utc)

    if total_seconds <= 0:
        return f"🎉 {countdown.live_message}"

    return (
        f"🚀 {countdown.title_line}\n"
        f"⏳ {countdown.subtitle_line}\n\n"
        f"{days:02d} Days  {hours:02d} Hours  {minutes:02d} Minutes"
    )
