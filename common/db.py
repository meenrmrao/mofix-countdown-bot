"""
MOFIX Countdown Bot - Database engine & session management
"""
import logging
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, scoped_session

from common.config import config
from common.models import Base, Admin, BotStatus, BOT_STATUS_SINGLETON_ID
from common.utils import hash_password

logger = logging.getLogger("mofix.db")

# `timeout` (seconds) controls how long the sqlite3 driver waits on a locked
# database before raising "database is locked" — this matters a lot here
# because the Web service and the Bot service are two separate processes
# that both read AND write the same SQLite file concurrently (admin
# start/stop/create vs. the bot's minute-by-minute sync + heartbeat).
engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    future=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """
    Configure SQLite for safe multi-process concurrent access.

    - WAL journal mode lets readers and a writer proceed concurrently
      instead of the writer exclusively locking the whole file (the
      default "delete"/rollback-journal mode), which is what caused
      intermittent failures to persist "start countdown" / heartbeat
      writes when the web and bot processes touched the DB at the same
      moment.
    - busy_timeout makes any connection that *does* hit a lock retry for
      up to 30s instead of failing immediately.
    - This is a no-op (and harmless) for non-sqlite backends since this
      project only targets SQLite, but we guard on the module name anyway.
    """
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))


def init_db():
    """Create tables and seed the initial admin + bot status row if missing.

    Both the web service and the bot service call this on startup, and a
    single service may itself start multiple workers (gunicorn -w 2), so
    two processes can race to seed the same row at (almost) the same
    moment. That's handled defensively below: on a unique-constraint
    violation we simply roll back and move on, since it means the row
    already exists (created by the other process).
    """
    logger.info("Using database: %s", config.DATABASE_URL)
    Base.metadata.create_all(engine)

    session = SessionLocal()
    try:
        try:
            if not session.query(Admin).filter_by(username=config.ADMIN_USERNAME).first():
                session.add(Admin(
                    username=config.ADMIN_USERNAME,
                    password_hash=hash_password(config.ADMIN_PASSWORD),
                ))
            session.commit()
        except IntegrityError:
            session.rollback()  # another process/worker already seeded the admin

        try:
            # BotStatus is a true singleton: always the SAME row (fixed
            # primary key), so the web dashboard and the bot process are
            # guaranteed to be reading/writing the one row, rather than
            # each creating their own row via `.first()` (which has no
            # ORDER BY and can silently pick a different, stale row).
            if not session.get(BotStatus, BOT_STATUS_SINGLETON_ID):
                session.add(BotStatus(id=BOT_STATUS_SINGLETON_ID))
            session.commit()
        except IntegrityError:
            session.rollback()  # another process/worker already seeded the status row
    finally:
        session.close()


@contextmanager
def get_session():
    """Context-managed session: with get_session() as session: ..."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
