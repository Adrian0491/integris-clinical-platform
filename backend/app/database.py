"""
SQLAlchemy engine and session factory.

get_db() is the FastAPI dependency used by every endpoint that needs the DB.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,          # evict stale connections
    echo=settings.DEBUG,         # SQL logging in development
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,      # safe for background tasks
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
