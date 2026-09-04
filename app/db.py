"""Database engine and session handling.

SQLite by default, so a fresh checkout runs with no setup at all. Point
``DATABASE_URL`` at Postgres for a real deployment — nothing else changes,
because every query goes through SQLAlchemy.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///./exercises.db"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    # SQLite otherwise refuses connections shared across FastAPI's threads.
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
    future=True,
)


@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_connection, _record):
    """SQLite needs foreign keys switched on explicitly, per connection."""
    if not _is_sqlite:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    # WAL lets reads proceed while a write is in flight — the difference
    # between a usable and an unusable SQLite under concurrent requests.
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False,
                            future=True)


class Base(DeclarativeBase):
    """Base class for every ORM model."""


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session that always closes."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_all() -> None:
    """Create any missing tables.

    Enough for a single-maintainer deployment. Introduce Alembic migrations
    before the first schema change that has to preserve live data.
    """
    from . import models  # noqa: F401  (import registers the models)

    Base.metadata.create_all(bind=engine)
