"""Halo API. Fixture mode serves fictional companies and does not call a model provider."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from halo.api.auth import router as auth_router
from halo.api.read import router as read_router
from halo.api.write import router as write_router
from halo.errors import HaloError
from halo.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.halo_mode == "fixture":
        settings.assert_fixture_boot()
    elif settings.halo_mode == "demo":
        settings.assert_demo_boot()
    app = FastAPI(title="Halo Front Office", version="0.1.0")
    app.include_router(auth_router)
    app.include_router(read_router)
    app.include_router(write_router)

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["x-request-id"] = request.state.request_id
        return response

    @app.exception_handler(HaloError)
    async def halo_error(_request: Request, exc: HaloError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "request_id": getattr(_request.state, "request_id", ""),
                "details": exc.details,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "INVALID_REQUEST",
                "message": "The request body is not valid.",
                "request_id": getattr(_request.state, "request_id", ""),
                "details": {"retryable": False},
            },
        )

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": settings.halo_mode}

    dist = Path(__file__).resolve().parents[4] / "apps" / "web" / "dist"
    if dist.is_dir():

        @app.get("/{full_path:path}", include_in_schema=False)
        def frontend(full_path: str) -> FileResponse:
            candidate = (dist / full_path).resolve()
            root = dist.resolve()
            if candidate.is_file() and (candidate == root or root in candidate.parents):
                return FileResponse(candidate)
            index = root / "index.html"
            if not index.is_file():
                raise HTTPException(status_code=404)
            return FileResponse(index)

    return app


app = create_app()
