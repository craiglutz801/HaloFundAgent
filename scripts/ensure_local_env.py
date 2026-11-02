"""Fill a gitignored .env with local fixture defaults. Existing values stay."""

from __future__ import annotations

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULTS = {
    "HALO_MODE": "fixture",
    "HALO_BIND_HOST": "127.0.0.1",
    "DATABASE_URL": "postgresql+psycopg://halo_app:halo_app_fixture@127.0.0.1:5432/halo_fixture",
    "MIGRATION_DATABASE_URL": (
        "postgresql+psycopg://halo_migrator:halo_migrator_fixture@127.0.0.1:5432/halo_fixture"
    ),
    "TEMPORAL_ADDRESS": "127.0.0.1:7233",
    "TEMPORAL_NAMESPACE": "default",
    "OBJECT_STORE": "local",
    "OBJECT_ROOT": "var/object-store",
    "MODEL_PROVIDER": "fake",
    "APP_ORIGIN": "http://127.0.0.1:5173",
    "SESSION_COOKIE_SECURE": "false",
}


def parse(text: str) -> list[tuple[str, str | None]]:
    rows: list[tuple[str, str | None]] = []
    for line in text.splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            rows.append((line, None))
            continue
        key, value = line.split("=", 1)
        rows.append((key, value))
    return rows


def main() -> None:
    example = (ROOT / ".env.example").read_text()
    target = ROOT / ".env"
    rows = parse(target.read_text() if target.exists() else example)
    present = {key for key, value in rows if value is not None}
    for key in DEFAULTS:
        if key not in present:
            rows.append((key, ""))
    rendered: list[str] = []
    for key, value in rows:
        if value is None:
            rendered.append(key)
            continue
        if value == "" and key in DEFAULTS:
            value = DEFAULTS[key]
        if key == "SESSION_SECRET" and value == "":
            value = secrets.token_hex(32)
        rendered.append(f"{key}={value}")
    if not any(line.startswith("SESSION_SECRET=") and line.split("=", 1)[1] for line in rendered):
        rendered.append(f"SESSION_SECRET={secrets.token_hex(32)}")
    target.write_text("\n".join(rendered) + "\n")
    print("local fixture environment is ready")


if __name__ == "__main__":
    main()
