from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from halo.settings import get_settings

_app_engine: Engine | None = None
_migration_engine: Engine | None = None
_app_factory: sessionmaker[Session] | None = None


def get_app_engine() -> Engine:
    global _app_engine, _app_factory
    if _app_engine is None:
        _app_engine = create_engine(get_settings().database_url, pool_pre_ping=True)
        _app_factory = sessionmaker(bind=_app_engine, expire_on_commit=False, autoflush=False)
    return _app_engine


def get_migration_engine() -> Engine:
    global _migration_engine
    if _migration_engine is None:
        _migration_engine = create_engine(
            get_settings().migration_database_url, pool_pre_ping=True
        )
    return _migration_engine


def open_app_session() -> Session:
    get_app_engine()
    assert _app_factory is not None
    return _app_factory()


def open_migration_session() -> Session:
    return Session(get_migration_engine(), expire_on_commit=False, autoflush=False)


def reset_engines() -> None:
    global _app_engine, _migration_engine, _app_factory
    if _app_engine is not None:
        _app_engine.dispose()
    if _migration_engine is not None:
        _migration_engine.dispose()
    _app_engine = None
    _migration_engine = None
    _app_factory = None
