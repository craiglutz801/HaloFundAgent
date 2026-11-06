"""Runtime configuration. Live mode refuses fixture identity and fake models."""

from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_BINDS = {"127.0.0.1", "localhost", "::1"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    halo_mode: Literal["fixture", "demo", "live"] = "fixture"
    halo_bind_host: str = "127.0.0.1"
    database_url: str = Field(
        default="postgresql+psycopg://halo_app:halo_app_fixture@127.0.0.1:5432/halo_fixture"
    )
    migration_database_url: str = Field(
        default=(
            "postgresql+psycopg://halo_migrator:halo_migrator_fixture"
            "@127.0.0.1:5432/halo_fixture"
        )
    )
    temporal_address: str = ""
    temporal_namespace: str = ""
    object_store: Literal["local", "s3"] = "local"
    object_bucket: str = ""
    object_root: str = "var/object-store"
    model_provider: Literal["fake", "openai", "anthropic"] = "fake"
    model_id_fast: str = ""
    model_id_analysis: str = ""
    model_id_critic: str = ""
    model_provider_key: str = ""
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    app_origin: str = "http://127.0.0.1:5173"
    session_secret: str = ""
    otel_exporter_otlp_endpoint: str = ""
    session_cookie_secure: bool = False
    session_ttl_seconds: int = 60 * 60 * 12
    policy_version: str = "2026-10-06"
    demo_access_code: str = ""

    @field_validator("database_url", "migration_database_url", mode="before")
    @classmethod
    def normalize_postgres_url(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            value = "postgresql+psycopg://" + value.removeprefix("postgres://")
        elif value.startswith("postgresql://"):
            value = "postgresql+psycopg://" + value.removeprefix("postgresql://")
        if value and not value.startswith("postgresql"):
            raise ValueError("Halo persists business records in PostgreSQL")
        return value

    @model_validator(mode="after")
    def enforce_deployment_guards(self) -> Settings:
        if self.halo_mode != "live":
            return self
        problems: list[str] = []
        if self.model_provider == "fake":
            problems.append("MODEL_PROVIDER=fake is not allowed when HALO_MODE=live")
        if not self.model_provider_key:
            problems.append("MODEL_PROVIDER_KEY is required when HALO_MODE=live")
        if not self.oidc_issuer or not self.oidc_client_id or not self.oidc_client_secret:
            problems.append("OIDC issuer, client id, and client secret are required in live mode")
        if not self.session_cookie_secure:
            problems.append("SESSION_COOKIE_SECURE must be true in live mode")
        if len(self.session_secret) < 32:
            problems.append("SESSION_SECRET must be at least 32 characters in live mode")
        if self.object_store != "s3" or not self.object_bucket:
            problems.append("live mode requires an S3 object bucket")
        if self.halo_bind_host in LOCAL_BINDS:
            problems.append("live mode cannot bind only to loopback")
        if "fixture" in _database_name(self.database_url):
            problems.append("live mode cannot use a fixture database name")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def assert_fixture_boot(self) -> None:
        """Fake identity is only available on a loopback fixture process."""
        if self.halo_mode != "fixture":
            raise RuntimeError("fixture identity is disabled")
        if self.halo_bind_host not in LOCAL_BINDS:
            raise RuntimeError("fixture mode must bind to local development access")
        if self.model_provider != "fake":
            raise RuntimeError("fixture mode uses the fake model provider")
        if "fixture" not in _database_name(self.database_url):
            raise RuntimeError("fixture mode requires a database name containing 'fixture'")
        if "live" in _database_name(self.database_url):
            raise RuntimeError("refusing a database name that contains 'live'")

    def assert_demo_boot(self) -> None:
        """Public review host. Fictional data only, and the browser role is not the table owner."""
        if self.halo_mode != "demo":
            raise RuntimeError("demo identity is disabled")
        external = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
        if external and (
            self.app_origin.startswith("http://127.0.0.1")
            or self.app_origin.startswith("http://localhost")
        ):
            self.app_origin = external
        problems: list[str] = []
        if self.model_provider != "fake":
            problems.append("demo mode uses the fake model provider")
        if self.model_provider_key:
            problems.append("demo mode cannot carry a model provider key")
        if self.oidc_issuer or self.oidc_client_id or self.oidc_client_secret:
            problems.append("demo mode cannot use a live identity provider")
        if not self.session_cookie_secure:
            problems.append("demo mode requires SESSION_COOKIE_SECURE=true")
        if len(self.session_secret) < 32:
            problems.append("demo mode requires SESSION_SECRET of at least 32 characters")
        if len(self.demo_access_code) < 8:
            problems.append("demo mode requires DEMO_ACCESS_CODE of at least 8 characters")
        if not self.app_origin.startswith("https://"):
            problems.append("demo mode requires an https APP_ORIGIN")
        if self.object_store != "local":
            problems.append("demo mode uses the local object directory")
        name = _database_name(self.database_url)
        if "live" in name:
            problems.append("demo mode refuses a database name that contains 'live'")
        elif not any(token in name for token in ("fixture", "demo")):
            problems.append("demo mode requires a database name containing 'fixture' or 'demo'")
        if problems:
            raise RuntimeError("; ".join(problems))

    @property
    def object_root_path(self) -> Path:
        return Path(self.object_root)


def _database_name(url: str) -> str:
    name = url.rsplit("/", 1)[-1]
    return name.split("?", 1)[0].lower()


def assert_fixture_reset_target(database_url: str, mode: str) -> str:
    """reset-fixtures may touch only a fixture database. Returns the database name."""
    if mode != "fixture":
        raise RuntimeError("reset-fixtures requires HALO_MODE=fixture")
    name = _database_name(database_url)
    if "fixture" not in name:
        raise RuntimeError(
            f"refusing to reset database '{name}': name must contain 'fixture'"
        )
    if "live" in name:
        raise RuntimeError(f"refusing to reset database '{name}': name contains 'live'")
    return name


@functools.lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
