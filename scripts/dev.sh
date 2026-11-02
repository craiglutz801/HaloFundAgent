#!/usr/bin/env bash
# Open the fixture application: migrate, seed, API on 127.0.0.1:8000, web on 127.0.0.1:5173.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
set -a
# shellcheck disable=SC1091
source .env
set +a
export PYTHONPATH=services/api/src

if ! pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
  if command -v docker >/dev/null 2>&1; then
    docker compose up -d postgres
    ready=0
    for _ in $(seq 1 40); do
      if pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
        ready=1
        break
      fi
      sleep 1
    done
    if [[ "$ready" -ne 1 ]]; then
      echo "PostgreSQL did not become ready on 127.0.0.1:5432." >&2
      exit 1
    fi
  else
    echo "PostgreSQL is not accepting connections on 127.0.0.1:5432." >&2
    echo "Start a local cluster, or install Docker and rerun make dev." >&2
    exit 1
  fi
fi

uv run alembic upgrade head
uv run python -m halo.cli seed

if command -v docker >/dev/null 2>&1; then
  docker compose up -d temporal || echo "Temporal did not start. Milestone 0 does not call it."
else
  echo "Docker is not installed. Temporal stays offline. Milestone 0 does not call it."
fi

stopping=0
cleanup() {
  if [[ "$stopping" -eq 1 ]]; then
    return
  fi
  stopping=1
  local pid
  for pid in $(jobs -p); do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

uv run python -m halo.cli serve --host 127.0.0.1 --port 8000 &
npm run dev --workspace @halo/web &
echo "Halo fixture app: http://127.0.0.1:5173"
wait
