from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from halo.api.deps import get_db
from halo.db.models import Organization, Principal, WorkspaceMembership
from halo.errors import HaloError
from halo.services import read_model

router = APIRouter(prefix="/api/v1")


def _require(request: Request) -> str:
    principal_id = request.state.principal_id
    if principal_id is None:
        raise HaloError(401, "UNAUTHENTICATED", "Sign in is required.")
    return principal_id


@router.get("/overview")
def overview(request: Request, db: Session = Depends(get_db)) -> dict:
    return read_model.overview(db, _require(request))


@router.get("/companies")
def companies(
    request: Request,
    db: Session = Depends(get_db),
    stage: str | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    _require(request)
    safe = ""
    if q:
        safe = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return read_model.list_companies(db, stage=stage, query=safe or None, cursor=cursor, limit=limit)


@router.get("/companies/{company_id}")
def company(company_id: UUID, request: Request, db: Session = Depends(get_db)) -> dict:
    _require(request)
    return read_model.company_detail(db, company_id)


@router.get("/evidence")
def search_evidence(
    request: Request, db: Session = Depends(get_db), q: str = ""
) -> dict:
    _require(request)
    return read_model.search_evidence(db, q)


@router.get("/evidence/{evidence_id}")
def evidence(evidence_id: UUID, request: Request, db: Session = Depends(get_db)) -> dict:
    _require(request)
    return read_model.evidence_detail(db, evidence_id)


@router.get("/ic-packets/{packet_id}")
def packet(packet_id: UUID, request: Request, db: Session = Depends(get_db)) -> dict:
    _require(request)
    return read_model.packet_detail(db, packet_id)


@router.get("/runs/{run_id}")
def run(run_id: UUID, request: Request, db: Session = Depends(get_db)) -> dict:
    _require(request)
    return read_model.run_detail(db, run_id)


@router.get("/portfolio")
def portfolio(request: Request, db: Session = Depends(get_db)) -> dict:
    _require(request)
    return read_model.portfolio(db)


@router.get("/value")
def value(request: Request, db: Session = Depends(get_db)) -> dict:
    _require(request)
    return read_model.value_ledger(db)


@router.get("/agents")
def agents(request: Request, db: Session = Depends(get_db)) -> dict:
    _require(request)
    return read_model.agent_directory(db)


@router.get("/review/queue")
def review_queue(request: Request, db: Session = Depends(get_db)) -> dict:
    payload = read_model.overview(db, _require(request))
    return {"decisions": payload["decisions"], "synced_at": payload["synced_at"]}


@router.get("/administration")
def administration(request: Request, db: Session = Depends(get_db)) -> dict:
    principal_id = UUID(_require(request))
    memberships = db.scalars(
        select(WorkspaceMembership).where(WorkspaceMembership.principal_id == principal_id)
    ).all()
    if not any("admin.manage" in membership.capabilities for membership in memberships):
        raise HaloError(403, "FORBIDDEN", "Administration rights are required.")
    org = db.scalar(select(Organization))
    people = db.scalars(select(Principal).order_by(Principal.display_name)).all()
    return {
        "organization": None
        if org is None
        else {"name": org.name, "mode": org.mode, "policy_version": org.policy_version},
        "principals": [
            {"id": str(person.id), "display_name": person.display_name, "email": person.email}
            for person in people
        ],
        "note": "Administrative rights do not include investment committee or reporting approval.",
    }
