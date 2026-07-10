from __future__ import annotations

import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.models import Base


def _make_database_url() -> str:
    if settings.database_url:
        return settings.database_url
    db_path = Path(settings.database_path)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


DATABASE_URL = _make_database_url()

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": int(os.getenv("SQLITE_TIMEOUT", "30"))},
        pool_pre_ping=True,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
        pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "20")),
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
        future=True,
    )

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    return SessionLocal()
