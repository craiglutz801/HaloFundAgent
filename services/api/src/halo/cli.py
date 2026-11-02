"""Local commands. reset-fixtures cannot target a live database."""

from __future__ import annotations

import argparse

import uvicorn

from halo.services.reset import reset_fixtures
from halo.services.seed import seed
from halo.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="halo")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed")
    sub.add_parser("reset-fixtures")
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    settings = get_settings()
    if args.command == "seed":
        created = seed(settings)
        print("seeded" if created else "already-seeded")
    elif args.command == "reset-fixtures":
        reset_fixtures(settings)
        print("reset")
    elif args.command == "serve":
        host = args.host or settings.halo_bind_host
        if settings.halo_mode == "fixture" and host not in {"127.0.0.1", "localhost", "::1"}:
            raise SystemExit("fixture mode must bind to local development access")
        uvicorn.run("halo.main:app", host=host, port=args.port, factory=False)
    else:
        raise SystemExit(f"unknown command {args.command}")


if __name__ == "__main__":
    main()
