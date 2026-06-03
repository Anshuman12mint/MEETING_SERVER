from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base, import_models


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    engine_options: dict[str, object] = {
        "future": True,
        "pool_pre_ping": settings.db_pool_pre_ping,
    }

    if settings.database_url.startswith("sqlite"):
        engine_options["connect_args"] = {"check_same_thread": False}
        if ":memory:" in settings.database_url:
            engine_options["poolclass"] = StaticPool
    else:
        engine_options["pool_size"] = settings.db_pool_size
        engine_options["max_overflow"] = settings.db_max_overflow
        engine_options["pool_recycle"] = settings.db_pool_recycle_seconds

    return create_engine(settings.database_url, **engine_options)


@lru_cache(maxsize=1)
def get_session_factory():
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def check_database_connection() -> None:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))


def initialize_database() -> None:
    import_models()
    Base.metadata.create_all(bind=get_engine())


def is_database_initialized(required_tables: tuple[str, ...] = ("meetings", "meeting_participants", "meeting_events")) -> bool:
    import_models()
    inspector = inspect(get_engine())
    existing_tables = set(inspector.get_table_names())
    return set(required_tables).issubset(existing_tables)


def dispose_database_engine() -> None:
    try:
        engine = get_engine()
    except Exception:
        get_session_factory.cache_clear()
        get_engine.cache_clear()
        return

    engine.dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()


def reset_database_state() -> None:
    dispose_database_engine()


def get_db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_context() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
