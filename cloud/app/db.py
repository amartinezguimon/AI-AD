"""Database engine, session factory, and the declarative Base.

SQLAlchemy 2.0 style. The engine is built from ``settings.database_url`` so the
exact same models run on SQLite (tests / zero-setup local) and PostgreSQL
(production). ``get_session`` is the FastAPI dependency that yields a request-
scoped session and always closes it.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    """Base for all ORM models."""


def _make_engine(url: str):
    # check_same_thread is a SQLite-only knob needed for the test client / uvicorn.
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True, future=True)


engine = _make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: a request-scoped DB session, always closed."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
