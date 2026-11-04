# Halo Front Office

Private investment operating application. This repository is the Milestone 0 fixture skeleton: fictional companies, no commercial key, and a visual shell over a real API.

## Open the app

```bash
make dev
```

That installs locked dependencies, writes a gitignored `.env` for fixture mode, migrates the database, seeds the six fictional companies, and serves the API at `http://127.0.0.1:8000` and the web app at `http://127.0.0.1:5173`.

You need Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js 22, and PostgreSQL listening on `127.0.0.1:5432`. With Docker, `make dev` starts the Compose Postgres service when nothing is already listening. Without Docker, start a local cluster and create the roles in `docs/PROVISIONING.md` first.

Sign in as **Jordan Hale**. Fixture mode has no password.

## Public review copy

Vercel’s free tier does not fit this app: the sign-in cookie and the database need one origin, and the API is a long-running Python process. Render’s free web service plus its free Postgres does. The blueprint is `render.yaml`.

From the Render dashboard, create a Blueprint, choose this repository and the branch that contains `render.yaml`, and set `DEMO_ACCESS_CODE` to a passphrase of your own. Render prints an `https://…onrender.com` address when the deploy is healthy. The first open after a quiet period waits about a minute while the free instance wakes. The free database expires 30 days after it is created. The companies stay fictional, and anyone with the address and the access code shares that one copy.

This environment cannot create the Render account. The blueprint is what gets deployed after you connect the repository.

## Other commands

| Command | What it does |
|---|---|
| `make bootstrap` | Install Python and Node dependencies and ensure `.env` |
| `make seed-fixtures` | Migrate and load fictional companies if the database is empty |
| `make reset-fixtures` | Replace fixture rows. Refuses any database whose name lacks `fixture`, contains `live`, or holds a non-fixture organization |
| `make test` | Python unit tests and the prompt/schema checks |
| `make test-e2e` | Fixture story against `halo_fixture_test` |
| `make eval` | Confirm the v1 prompts and JSON schemas |
| `make build` | Typecheck and build the web app |
| `make generate-client` | Refresh `contracts/openapi.json` and `apps/web/src/api/generated.ts` |
| `make compose-up` | Start Postgres 17 and the Temporal development server |

`make test-e2e` creates its own database name, `halo_fixture_test`. It does not truncate `halo_fixture`.

## Fixture people

| Person | Role | What to look at |
|---|---|---|
| Jordan Hale | Partner | Two decisions (Vela and Rally) and Atlas blockers |
| Priya Shah | Deal lead | Atlas diligence. Submit to IC is refused while gates are open |
| Blake Iverson | Analyst | Vela only. Atlas is absent |
| Riley Quinn | CFO | Value ledger. No summed total |
| Sam Okonkwo | Board | Court's overdue notification |
| Avery Brooks | Admin | Administration. No IC decision |
| Alex Chen | Platform | Rally |
| Morgan Ellis | Operating | Rally and Court |

Company stages: Northline discovered, Sideline first look, Atlas diligence, Vela IC review, Rally and Court owned.

## Scope of this milestone

Included: locked dependencies, Compose for Postgres and Temporal, fixture identity, environment checks, migrations and row security, the six-company seed, read models, reviews, concern dispositions, stage actions, IC decisions, calculation fixtures, the nine named routes, and a generated API client.

Not included yet: a Temporal worker, live model calls, uploads, or any private Halo data. An unconfigured provider returns a capability error and does not invent a memo. See `docs/PROVISIONING.md`.
