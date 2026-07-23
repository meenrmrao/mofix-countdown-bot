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
    DATA_DIR: Path = BASE_DIR / "data"
    DATABASE_PATH: Path = DATA_DIR / os.getenv("DATABASE_FILE", "mofix.db")
    DATABASE_URL: str = f"sqlite:///{DATABASE_PATH}"

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
