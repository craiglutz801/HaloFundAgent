.PHONY: bootstrap dev seed-fixtures test test-e2e eval build reset-fixtures generate-client compose-up

export PYTHONPATH := services/api/src

bootstrap:
	uv sync
	npm ci
	uv run python scripts/ensure_local_env.py

dev: bootstrap
	bash scripts/dev.sh

seed-fixtures: bootstrap
	uv run alembic upgrade head
	uv run python -m halo.cli seed

reset-fixtures: bootstrap
	uv run python -m halo.cli reset-fixtures

test: bootstrap
	uv run pytest tests/unit tests/eval -q

test-e2e: bootstrap
	uv run pytest tests/e2e -q

eval: bootstrap
	uv run pytest tests/eval -q

build:
	npm run build --workspace @halo/web

generate-client: bootstrap
	uv run python scripts/generate_api_client.py

compose-up:
	docker compose up -d
