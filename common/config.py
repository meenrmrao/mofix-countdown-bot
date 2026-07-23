"""
MOFIX Countdown Bot - Shared Configuration
Loads settings from environment variables (.env file supported via python-dotenv).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(val, default=False):
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")


class Config:
    # --- Telegram ---
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    DEFAULT_CHAT_ID: str = os.getenv("DEFAULT_CHAT_ID", "")

    # --- Database ---
    # IMPORTANT (Railway / multi-service deployments):
    # The Web dashboard and the Bot run as TWO SEPARATE services/containers.
    # Each container has its own private, ephemeral filesystem — a file
    # written by one service is NOT visible to the other unless both
    # services mount the exact same persistent Volume at the exact same
    # path. If you only see countdowns/bot-status update on one side
    # (e.g. "Bot Status: Offline" even though the bot is running, or
    # countdowns created in the admin never show up publicly), the most
    # common cause is that the two Railway services are NOT sharing a
    # Volume — attach one Volume to both the "web" and "bot" services in
    # the Railway dashboard, mounted at the same path (e.g. /app/data).
    #
    # DATABASE_URL can be set directly to fully control this (e.g.
    # "sqlite:////app/data/mofix.db" pointing at a shared Volume mount).
    # If not set, it's derived from DATA_DIR/DATABASE_FILE below, which
    # defaults to a "data" folder next to the project root.
    DATA_DIR: Path = BASE_DIR / "data"
    DATABASE_PATH: Path = DATA_DIR / os.getenv("DATABASE_FILE", "mofix.db")
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")

    # DATABASE_PATH is re-derived from the final DATABASE_URL (rather than
    # left as the pre-override default above) so that features which need
    # a raw filesystem path — e.g. the "Backup DB" download — keep working
    # correctly even when DATABASE_URL was overridden directly instead of
    # via DATABASE_FILE. Falls back to the default path for non-sqlite URLs
    # or anything unparsable, since a raw path doesn't apply there anyway.
    if DATABASE_URL.startswith("sqlite:///"):
        DATABASE_PATH = Path(DATABASE_URL[len("sqlite:///"):] or DATABASE_PATH)

    # --- Web dashboard ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "changeme123")
    WEB_HOST: str = os.getenv("WEB_HOST", "0.0.0.0")
    # Railway (and most PaaS providers) assign the port to bind to via the
    # PORT environment variable, and it can change on every deploy — so PORT
    # always wins here. WEB_PORT is kept only as a manual override for local
    # development when PORT isn't set (e.g. plain `docker run` or bare metal).
    WEB_PORT: int = int(os.getenv("PORT", os.getenv("WEB_PORT", "5000")))
    DEBUG: bool = _bool(os.getenv("DEBUG"), False)

    # --- Behaviour ---
    DEFAULT_TIMEZONE: str = os.getenv("DEFAULT_TIMEZONE", "Asia/Kolkata")
    UPDATE_INTERVAL_SECONDS: int = int(os.getenv("UPDATE_INTERVAL_SECONDS", "60"))
    HEARTBEAT_STALE_SECONDS: int = int(os.getenv("HEARTBEAT_STALE_SECONDS", "90"))

    BACKUP_DIR: Path = BASE_DIR / "backups"


config = Config()
config.DATA_DIR.mkdir(parents=True, exist_ok=True)
config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
# In case DATABASE_URL was overridden to a path outside DATA_DIR (e.g. a
# Railway Volume mounted elsewhere), make sure that directory exists too.
config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
