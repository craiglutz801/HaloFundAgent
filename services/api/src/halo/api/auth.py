from __future__ import annotations

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

router = APIRouter(prefix="/api/v1")


class FixtureLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str


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


@router.get("/auth/fixture-principals")
def fixture_principals(db: Session = Depends(get_db)) -> dict[str, list[dict[str, str]]]:
    if get_settings().halo_mode != "fixture":
        raise HaloError(404, "NOT_FOUND", "Not found.")
    rows = db.execute(text("SELECT id, display_name, email, role FROM halo_fixture_roster()")).all()
    return {
        "principals": [
            {"id": str(row.id), "display_name": row.display_name, "email": row.email, "role": row.role}
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
    if get_settings().halo_mode != "fixture":
        raise HaloError(404, "NOT_FOUND", "Not found.")
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
