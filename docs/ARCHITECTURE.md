# Architecture

Halo Front Office is a modular monolith. The web app is React, TypeScript, and Vite. The API is FastAPI. PostgreSQL holds the business records. The browser talks only to `/api/v1` on the same origin through the Vite proxy.

## Processes

`make dev` runs two host processes:

- `python -m halo.cli serve` on `127.0.0.1:8000`
- Vite on `127.0.0.1:5173`, proxying `/api` to the API

Fixture mode refuses any other bind address. That is why Compose does not run the API inside a container that would publish `0.0.0.0`.

## Data access

The migrator role owns tables and bypasses row security. The application role `halo_app` has no `BYPASSRLS`. Policies are forced. The request session sets `halo.principal_id` with `set_config(..., true)` after resolving the session cookie. The client cannot supply that value. A header that names another person is ignored.

Unauthorized reads of a company the caller cannot see return `404 NOT_FOUND`. A caller who can see a record but lacks the mutation capability receives `403`. Capability checks use a plain `SELECT` before `SELECT FOR UPDATE`, because an update policy would hide the row and turn a forbidden action into a not-found.

Company stage is a projection. `companies_stage_guard` rejects an update that does not carry a transaction-local `halo.stage_transition_id` matching a `stage_events` row. Reviews, decisions, and packet manifests are append-only or otherwise immutable once written.

## Fixture isolation

`reset-fixtures` checks the database name and the `organizations.mode` column before it truncates. The object-store clear only runs for a directory named `object-store` or a path that contains `pytest`.

## Decisions and gates

An IC approval of an initial case in `ic_review` moves the company to `closing`. It does not create ownership. A follow-on approval on an owned company leaves the company `owned` and the case `closing`. Submit-to-IC from diligence returns `409 GATE_NOT_MET` with the missing requirements. A text-only concern resolution returns `422 EVIDENCE_REQUIRED`. A review does not clear concerns or change stage. An administrator does not have `ic.decide`.

A decision with a stale case version returns `409 STALE_VERSION`. A decision whose packet hash or policy version does not match the frozen packet returns `409 STALE_PACKET`. The same idempotency key and body replay the stored response. The same key with a different body returns `409 IDEMPOTENCY_CONFLICT`.

## Workflows

The durable workflow id for diligence, when the worker exists, is `diligence/{organization_id}/{case_id}/{request_id}`. A repeated start must deduplicate on that id. Activities are idempotent by job, phase, and artifact kind. Business writes commit in PostgreSQL first. The outbox table is present. The dispatcher, Temporal worker, and activity implementations are not in this milestone, so no workflow is started and no model call is made. Do not treat a missing worker as a successful specialist run.

## Health and value

Unknown beats a prior fresh or green observation. The latest period wins. A missing, invalid, or stale required metric yields `unknown`.

The value ledger does not sum incompatible units. Rally's tagged meetings stay observed, capacity stays estimated, and incremental revenue and cash savings stay gaps.
