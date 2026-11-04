from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session

from halo.api.deps import get_db
from halo.auth.csrf import CSRF_COOKIE, CSRF_HEADER, assert_csrf, new_csrf_token
from halo.auth.sessions import (
    SESSION_COOKIE,
    new_session_token,
    open_fixture_session,
    revoke_session,
)
from halo.errors import HaloError
from halo.services.read_model import me
from halo.settings import get_settings
from halo.util import sha256_hex

DEMO_COOKIE = "halo_demo"

router = APIRouter(prefix="/api/v1")


class FixtureLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str


class DemoAccess(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str


def _demo_digest() -> str:
    settings = get_settings()
    return sha256_hex(f"{settings.session_secret}:{settings.demo_access_code}".encode())


def _demo_cookie_ok(request: Request) -> bool:
    presented = request.cookies.get(DEMO_COOKIE, "")
    if len(presented) != 64:
        return False
    return hmac.compare_digest(presented, _demo_digest())


def _require_fixture_identity(request: Request) -> None:
    settings = get_settings()
    if settings.halo_mode not in {"fixture", "demo"}:
        raise HaloError(404, "NOT_FOUND", "Not found.")
    if settings.halo_mode == "demo" and not _demo_cookie_ok(request):
        raise HaloError(401, "DEMO_ACCESS_REQUIRED", "Enter the demo access code first.")


def _csrf_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        CSRF_COOKIE,
        token,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_seconds,
    )


def _session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_seconds,
    )


@router.get("/auth/csrf")
def csrf(response: Response) -> dict[str, str]:
    token = new_csrf_token()
    _csrf_cookie(response, token)
    return {"csrf_token": token}


@router.get("/auth/demo-access")
def demo_access_status(request: Request) -> dict[str, bool]:
    settings = get_settings()
    if settings.halo_mode != "demo":
        return {"required": False, "accepted": True}
    return {"required": True, "accepted": _demo_cookie_ok(request)}


@router.post("/auth/demo-access")
def accept_demo_access(body: DemoAccess, request: Request, response: Response) -> dict[str, bool]:
    settings = get_settings()
    if settings.halo_mode != "demo":
        raise HaloError(404, "NOT_FOUND", "Not found.")
    assert_csrf(request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER))
    offered = sha256_hex(f"{settings.session_secret}:{body.code}".encode())
    if not hmac.compare_digest(offered, _demo_digest()):
        raise HaloError(401, "DEMO_ACCESS_REQUIRED", "That access code is not valid.")
    response.set_cookie(
        DEMO_COOKIE,
        offered,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_seconds,
    )
    return {"required": True, "accepted": True}


@router.get("/auth/fixture-principals")
def fixture_principals(
    request: Request, db: Session = Depends(get_db)
) -> dict[str, list[dict[str, str]]]:
    _require_fixture_identity(request)
    rows = db.execute(text("SELECT id, display_name, email, role FROM halo_fixture_roster()")).all()
    return {
        "principals": [
            {
                "id": str(row.id),
                "display_name": row.display_name,
                "email": row.email,
                "role": row.role,
            }
            for row in rows
        ]
    }


@router.post("/auth/fixture-login")
def fixture_login(
    body: FixtureLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    _require_fixture_identity(request)
    assert_csrf(request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER))
    token = new_session_token()
    try:
        open_fixture_session(db, body.principal_id, token, get_settings().session_ttl_seconds)
    except Exception as exc:
        raise HaloError(404, "NOT_FOUND", "Not found.") from exc
    _session_cookie(response, token)
    csrf_token = new_csrf_token()
    _csrf_cookie(response, csrf_token)
    return {"status": "signed_in", "csrf_token": csrf_token}


@router.post("/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    assert_csrf(request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER))
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        revoke_session(db, token)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"status": "signed_out"}


@router.get("/me")
def current(request: Request, db: Session = Depends(get_db)) -> dict:
    principal_id = request.state.principal_id
    if principal_id is None:
        raise HaloError(401, "UNAUTHENTICATED", "Sign in is required.")
    payload = me(db, principal_id)
    payload["mode"] = get_settings().halo_mode
    payload["policy_version"] = get_settings().policy_version
    return payload
