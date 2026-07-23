"""
MOFIX Countdown Bot - Database engine & session management
"""
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from common.config import config
from common.models import Base, Admin, BotStatus
from common.utils import hash_password

engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))


def init_db():
    """Create tables and seed the initial admin + bot status row if missing."""
    Base.metadata.create_all(engine)

    session = SessionLocal()
    try:
        if not session.query(Admin).filter_by(username=config.ADMIN_USERNAME).first():
            session.add(Admin(
                username=config.ADMIN_USERNAME,
                password_hash=hash_password(config.ADMIN_PASSWORD),
            ))
        if not session.query(BotStatus).first():
            session.add(BotStatus())
        session.commit()
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
