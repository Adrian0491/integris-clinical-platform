"""
SQLAlchemy engine and session factory.
get_db() is the FastAPI dependency used by every endpoint that needs the DB.
"""
from __future__ import annotations
from collections.abc import Generator
from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db(request: Request = None) -> Generator[Session, None, None]:
    """FastAPI dependency — yields a session and closes it after the request."""
    db = SessionLocal()
    if request and request.client:
        db.info['ip_address'] = request.client.host
        db.info['user_agent'] = request.headers.get('user-agent')
    try:
        yield db
    finally:
        db.close()