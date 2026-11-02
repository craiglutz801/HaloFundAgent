"""Server-side sessions. The raw token is never stored."""

from __future__ import annotations

import secrets

from sqlalchemy import text
from sqlalchemy.orm import Session

from halo.util import sha256_hex

SESSION_COOKIE = "halo_session"


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return sha256_hex(token.encode())


def open_fixture_session(db: Session, principal_id: str, token: str, ttl_seconds: int) -> None:
    db.execute(
        text("SELECT halo_open_fixture_session(CAST(:principal AS uuid), :token_hash, :ttl)"),
        {"principal": principal_id, "token_hash": token_hash(token), "ttl": ttl_seconds},
    )


def resolve_session(db: Session, token: str) -> str | None:
    found = db.execute(
        text("SELECT halo_resolve_session(:token_hash)"),
        {"token_hash": token_hash(token)},
    ).scalar()
    if found is None:
        return None
    return str(found)


def revoke_session(db: Session, token: str) -> None:
    db.execute(
        text("SELECT halo_revoke_session(:token_hash)"),
        {"token_hash": token_hash(token)},
    )


def set_principal(db: Session, principal_id: str) -> None:
    db.execute(
        text("SELECT set_config('halo.principal_id', :principal, true)"),
        {"principal": principal_id},
    )


def set_stage_transition(db: Session, transition_id: str) -> None:
    db.execute(
        text("SELECT set_config('halo.stage_transition_id', :transition, true)"),
        {"transition": transition_id},
    )
