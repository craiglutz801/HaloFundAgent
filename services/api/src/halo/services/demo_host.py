"""Prepare a public demo database.

The platform gives one database owner and that owner is not a superuser, so it
cannot grant BYPASSRLS. Migrations run as the owner. The browser uses a second
role, halo_app, which does not own tables. Row security stays enabled. FORCE is
lifted so owner-backed security-definer functions can read membership rows, while
halo_app remains subject to the policies.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from urllib.parse import quote, urlsplit, urlunsplit

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from halo.db.base import Base
from halo.services.seed import seed
from halo.settings import Settings


def demo_app_password(session_secret: str) -> str:
    return hashlib.sha256(f"halo-demo-app:{session_secret}".encode()).hexdigest()


def database_url_for_role(url: str, user: str, password: str) -> str:
    temporary = url.replace("postgresql+psycopg://", "postgresql://", 1)
    parts = urlsplit(temporary)
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{quote(user, safe='')}:{quote(password, safe='')}@{host}{port}"
    rewritten = urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    if url.startswith("postgresql+psycopg://"):
        return rewritten.replace("postgresql://", "postgresql+psycopg://", 1)
    return rewritten


def prepare_demo_database(settings: Settings) -> str:
    """Migrate and seed as the owner. Returns the halo_app URL the server should use."""
    settings.assert_demo_boot()
    owner_url = settings.migration_database_url or settings.database_url
    os.environ["MIGRATION_DATABASE_URL"] = owner_url
    password = demo_app_password(settings.session_secret)
    engine = create_engine(owner_url, pool_pre_ping=True)
    last_error: Exception | None = None
    for _ in range(30):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            last_error = None
            break
        except Exception as exc:  # noqa: BLE001 — the host database may still be starting
            last_error = exc
            time.sleep(2)
    if last_error is not None:
        raise RuntimeError("demo database did not accept a connection") from last_error

    with engine.begin() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = 'halo_app'")
        ).scalar()
        if exists:
            # A non-superuser cannot mention BYPASSRLS in ALTER ROLE.
            connection.execute(text(f"ALTER ROLE halo_app WITH LOGIN PASSWORD '{password}'"))
        else:
            connection.execute(
                text(f"CREATE ROLE halo_app LOGIN PASSWORD '{password}' NOBYPASSRLS")
            )
        database = str(connection.execute(text("SELECT current_database()")).scalar())
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database):
            raise RuntimeError("demo database name is not a plain identifier")
        connection.execute(text(f'GRANT CONNECT ON DATABASE "{database}" TO halo_app'))

    command.upgrade(Config("alembic.ini"), "head")
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            connection.execute(text(f'ALTER TABLE "{table.name}" NO FORCE ROW LEVEL SECURITY'))
        connection.execute(text("GRANT USAGE ON SCHEMA public TO halo_app"))
        connection.execute(text("GRANT EXECUTE ON FUNCTION halo_fixture_roster() TO halo_app"))
    seed(settings)
    engine.dispose()
    return database_url_for_role(owner_url, "halo_app", password)
