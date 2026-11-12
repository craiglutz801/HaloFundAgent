FROM node:22-bookworm-slim AS web
WORKDIR /src
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
RUN npm ci
COPY apps/web apps/web
RUN npm run build --workspace @halo/web

FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY services services
COPY alembic alembic
COPY alembic.ini ./
COPY --from=web /src/apps/web/dist apps/web/dist
ENV PATH="/app/.venv/bin:${PATH}"
ENV PYTHONPATH="/app/services/api/src"
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "halo.cli", "serve"]
