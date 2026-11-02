from __future__ import annotations

import uuid
from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from halo.auth.sessions import resolve_session, set_principal
from halo.db.session import open_app_session

REQUEST_HEADER = "x-request-id"


def get_db(request: Request) -> Iterator[Session]:
    db = open_app_session()
    try:
        token = request.cookies.get("halo_session")
        principal_id = resolve_session(db, token) if token else None
        if principal_id is not None:
            set_principal(db, principal_id)
        request.state.principal_id = principal_id
        if not getattr(request.state, "request_id", None):
            request.state.request_id = request.headers.get(REQUEST_HEADER) or str(uuid.uuid4())
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
