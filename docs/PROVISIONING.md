# Provisioning

Fixture mode runs with no commercial credential. Live mode refuses to start until the checks in `halo.settings` pass. An unavailable provider returns `501 CAPABILITY_UNAVAILABLE` and no fabricated body.

## Required for `make dev`

| Dependency | Fixture use | Notes |
|---|---|---|
| Python 3.12 and uv | API, migrations, tests | `uv sync` installs the lockfile. No OpenAI SDK is installed. |
| Node.js 22 | Web app | `npm ci` installs the lockfile. |
| PostgreSQL | System of record | Compose uses `postgres:17`. A local cluster on PostgreSQL 16 is compatible with the migrations in this repository. The database name must contain `fixture` and must not contain `live`. |

Create the local roles once when you are not using Compose:

```sql
CREATE ROLE halo_app LOGIN PASSWORD 'halo_app_fixture' NOBYPASSRLS;
CREATE ROLE halo_migrator LOGIN PASSWORD 'halo_migrator_fixture' BYPASSRLS CREATEDB;
CREATE DATABASE halo_fixture OWNER halo_migrator;
CREATE DATABASE halo_fixture_test OWNER halo_migrator;
GRANT CONNECT ON DATABASE halo_fixture TO halo_app;
GRANT CONNECT ON DATABASE halo_fixture_test TO halo_app;
```

`infra/docker/init-db.sql` does the same on the first Compose boot, and it also creates the `temporal` role.

Passwords above are local fixture passwords, not production secrets. `.env.example` leaves secrets empty. `make bootstrap` writes a gitignored `.env` and generates `SESSION_SECRET` on that machine.

## Present in Compose, unused by Milestone 0

| Dependency | Address | Status |
|---|---|---|
| Temporal development server `temporalio/auto-setup:1.27.2` | `127.0.0.1:7233`, namespace `default` | Started by `make compose-up` or by `make dev` when Docker is installed. The API does not dispatch workflows yet. This image is a development server, not a production service. |

## Live-mode dependencies, not connected

| Dependency | What startup requires | Current behavior |
|---|---|---|
| Model provider | `MODEL_PROVIDER` of `openai` or `anthropic`, plus `MODEL_PROVIDER_KEY` | Fixture mode forces `fake`. The OpenAI and Anthropic adapters raise a capability error and do not call a network API. |
| OIDC | Issuer, client id, and client secret | Fixture login uses the fictional roster only when `HALO_MODE=fixture` and the process binds to loopback. |
| Object storage | S3 bucket | Fixture mode uses `var/object-store` on disk. |
| Cookies | `SESSION_COOKIE_SECURE=true` and a session secret of at least 32 characters | Fixture development may use an insecure cookie on loopback. |
| Telemetry | `OTEL_EXPORTER_OTLP_ENDPOINT` | Optional. Empty means no export. |

No CRM, market-data license, fund administrator, or private data room is connected. Do not point `DATABASE_URL` at a live Halo database.
