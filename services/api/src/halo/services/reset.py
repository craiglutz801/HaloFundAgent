"""Fixture reset refuses any database that is not a fixture database."""

from __future__ import annotations

from sqlalchemy import text

from halo.db.base import Base
from halo.db.session import get_migration_engine, reset_engines
from halo.services.seed import seed
from halo.settings import Settings, assert_fixture_reset_target


def reset_fixtures(settings: Settings) -> None:
    assert_fixture_reset_target(settings.migration_database_url, settings.halo_mode)
    engine = get_migration_engine()
    with engine.connect() as connection:
        if database_has_live_organization_connection(connection):
            raise RuntimeError("refusing to reset: a non-fixture organization is present")
        names = ", ".join(table.name for table in Base.metadata.sorted_tables)
        connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
        connection.commit()
    reset_engines()
    seed(settings)


def database_has_live_organization_connection(connection) -> bool:
    rows = connection.execute(text("SELECT mode FROM organizations")).scalars().all()
    return any(mode != "fixture" for mode in rows)
