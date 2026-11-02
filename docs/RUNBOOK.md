# Runbook

Times below are for the operator's own machine. The application stores timestamps in UTC and the web app formats them in the browser timezone.

## Start

```bash
make dev
```

Open `http://127.0.0.1:5173`. The API health check is:

```bash
curl -s http://127.0.0.1:8000/api/v1/health
```

A healthy fixture process returns `{"status":"ok","mode":"fixture"}`.

## Reset fictional data

```bash
make reset-fixtures
```

This truncates application tables in the database named by `MIGRATION_DATABASE_URL`, then loads the seed. It does not drop the schema and it does not touch `alembic_version`. It aborts when:

- `HALO_MODE` is not `fixture`
- the database name does not contain `fixture`
- the database name contains `live`
- any organization row has a mode other than `fixture`

After a refused reset, fix the URL. Do not rename a live database to make the check pass.

## Sign-in problems

Fixture sign-in only works while the API is in fixture mode and bound to loopback. There is no password. If the roster is empty, the seed did not load. Run `make seed-fixtures`.

Switching people in the rail clears the React Query cache so the previous person's companies do not remain on screen.

## Stage and decision failures

| Code | Meaning |
|---|---|
| `GATE_NOT_MET` | A required artifact, seal, or blocking concern is still open. The response lists `missing_requirements`. |
| `STALE_VERSION` | Reload the case. The row version moved. |
| `STALE_PACKET` | The packet hash, policy version, or packet status does not match the decision. |
| `IDEMPOTENCY_CONFLICT` | This idempotency key was already used for a different body. |
| `EVIDENCE_REQUIRED` | A concern disposition needs evidence. Text alone is not enough. |
| `CAPABILITY_UNAVAILABLE` | A provider or identity feature is not configured. Nothing was invented in its place. |
| `FORBIDDEN` | The caller can see the record and lacks the capability. |
| `NOT_FOUND` | The record is absent or outside the caller's workspaces. |

## PostgreSQL

If `make dev` cannot connect, confirm a server is listening on port 5432. With Docker, `docker compose up -d postgres` starts the Compose cluster. If a local cluster already holds port 5432, use that cluster and the roles in `docs/PROVISIONING.md` instead of publishing a second server on the same port.

## Temporal

Milestone 0 does not require Temporal. If Docker is absent, `make dev` prints that and continues. When the worker is added, its development address is `127.0.0.1:7233`.
