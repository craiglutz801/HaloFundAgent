import os

os.environ["HALO_MODE"] = "fixture"
os.environ["HALO_BIND_HOST"] = "127.0.0.1"
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://halo_app:halo_app_fixture@127.0.0.1:5432/halo_fixture_test"
)
os.environ["MIGRATION_DATABASE_URL"] = (
    "postgresql+psycopg://halo_migrator:halo_migrator_fixture@127.0.0.1:5432/halo_fixture_test"
)
os.environ["OBJECT_ROOT"] = "/tmp/halo-pytest-object-store"
os.environ["MODEL_PROVIDER"] = "fake"
os.environ["SESSION_SECRET"] = "test-session-secret-is-long-enough"
os.environ["SESSION_COOKIE_SECURE"] = "false"
os.environ["APP_ORIGIN"] = "http://127.0.0.1:5173"

import pytest
from alembic import command
from alembic.config import Config

from halo.db.session import reset_engines
from halo.settings import clear_settings_cache


@pytest.fixture(scope="session", autouse=True)
def migrate_test_database():
    clear_settings_cache()
    reset_engines()
    command.upgrade(Config("alembic.ini"), "head")
    yield
    reset_engines()
    clear_settings_cache()
