"""SQLAlchemy engine and session factory.

Local default: SQLite file beside the backend. Hosted: Postgres via DATABASE_URL (serverless hosts such as
Vercel have no persistent local disk, so SQLite cannot be used there).
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def make_url_engine(url: str) -> Engine:
    # NullPool: serverless functions are short-lived; let the provider's pooler manage connections.
    return create_engine(url, poolclass=NullPool, future=True)


def make_engine(path: Path) -> Engine:
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread": False}, future=True)

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

    return engine


engine = make_url_engine(settings.database_url) if settings.database_url else make_engine(settings.database_path)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def configure(path: Path) -> None:
    """Point the application at a different database file (used by tests)."""
    global engine
    engine.dispose()
    engine = make_engine(path)
    SessionLocal.configure(bind=engine)


def reconnect() -> None:
    """Dispose and rebuild the engine from current settings (simulates an application restart)."""
    global engine
    engine.dispose()
    engine = make_url_engine(settings.database_url) if settings.database_url else make_engine(settings.database_path)
    SessionLocal.configure(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
