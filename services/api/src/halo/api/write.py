from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from halo.api.deps import get_db
from halo.auth.csrf import CSRF_COOKIE, CSRF_HEADER, assert_csrf
from halo.db.models import OrganizationMembership
from halo.domain.actions import (
    dispose_concern,
    lookup_idempotency,
    record_decision,
    record_review,
    require_actor,
    stage_action,
    store_idempotency,
)

router = APIRouter(prefix="/api/v1")


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_sha256: str
    verdict: str
    notes: str


class DispositionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    disposition: str
    rationale: str
    evidence_ids: list[UUID] = []
    expected_version: int


class StageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str
    rationale: str
    expected_case_version: int


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    packet_sha256: str
    decision: str
    rationale: str
    expected_case_version: int
    policy_version: str


def _guard(request: Request, db: Session, route: str, body: dict[str, Any]):
    assert_csrf(request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER))
    actor = require_actor(db, request.state.principal_id)
    key = request.headers.get("idempotency-key")
    digest, replay = lookup_idempotency(
        db, principal_id=actor.id, route=route, key=key, body=body
    )
    return actor, key, digest, replay


def _finish(
    db: Session,
    *,
    actor_id: UUID,
    route: str,
    key: str,
    digest: str,
    body: dict[str, Any],
    status_code: int = 200,
) -> dict[str, Any]:
    org_id = db.scalar(
        select(OrganizationMembership.organization_id).where(
            OrganizationMembership.principal_id == actor_id
        )
    )
    if org_id is None:
        return body
    store_idempotency(
        db,
        organization_id=org_id,
        principal_id=actor_id,
        route=route,
        key=key,
        request_hash=digest,
        status_code=status_code,
        body=body,
    )
    return body


@router.post("/artifacts/{artifact_id}/reviews")
def post_review(
    artifact_id: UUID,
    payload: ReviewIn,
    request: Request,
    db: Session = Depends(get_db),
):
    body = payload.model_dump(mode="json")
    route = f"POST /artifacts/{artifact_id}/reviews"
    actor, key, digest, replay = _guard(request, db, route, body)
    if replay:
        return JSONResponse(replay["body"], status_code=replay["status_code"])
    result = record_review(
        db,
        actor=actor,
        artifact_id=artifact_id,
        artifact_sha256=payload.artifact_sha256,
        verdict=payload.verdict,
        notes=payload.notes,
        request_id=request.state.request_id,
    )
    return _finish(db, actor_id=actor.id, route=route, key=key or "", digest=digest, body=result)


@router.post("/concerns/{concern_id}/dispositions")
def post_disposition(
    concern_id: UUID,
    payload: DispositionIn,
    request: Request,
    db: Session = Depends(get_db),
):
    body = payload.model_dump(mode="json")
    route = f"POST /concerns/{concern_id}/dispositions"
    actor, key, digest, replay = _guard(request, db, route, body)
    if replay:
        return JSONResponse(replay["body"], status_code=replay["status_code"])
    result = dispose_concern(
        db,
        actor=actor,
        concern_id=concern_id,
        disposition=payload.disposition,
        rationale=payload.rationale,
        evidence_ids=payload.evidence_ids,
        expected_version=payload.expected_version,
        request_id=request.state.request_id,
    )
    return _finish(db, actor_id=actor.id, route=route, key=key or "", digest=digest, body=result)


@router.post("/cases/{case_id}/stage-actions")
def post_stage(
    case_id: UUID,
    payload: StageIn,
    request: Request,
    db: Session = Depends(get_db),
):
    body = payload.model_dump(mode="json")
    route = f"POST /cases/{case_id}/stage-actions"
    actor, key, digest, replay = _guard(request, db, route, body)
    if replay:
        return JSONResponse(replay["body"], status_code=replay["status_code"])
    result = stage_action(
        db,
        actor=actor,
        case_id=case_id,
        action=payload.action,
        rationale=payload.rationale,
        expected_case_version=payload.expected_case_version,
        request_id=request.state.request_id,
    )
    return _finish(db, actor_id=actor.id, route=route, key=key or "", digest=digest, body=result)


@router.post("/ic-packets/{packet_id}/decisions")
def post_decision(
    packet_id: UUID,
    payload: DecisionIn,
    request: Request,
    db: Session = Depends(get_db),
):
    body = payload.model_dump(mode="json")
    route = f"POST /ic-packets/{packet_id}/decisions"
    actor, key, digest, replay = _guard(request, db, route, body)
    if replay:
        return JSONResponse(replay["body"], status_code=replay["status_code"])
    result = record_decision(
        db,
        actor=actor,
        packet_id=packet_id,
        packet_sha256=payload.packet_sha256,
        decision=payload.decision,
        rationale=payload.rationale,
        expected_case_version=payload.expected_case_version,
        policy_version=payload.policy_version,
        request_id=request.state.request_id,
    )
    return _finish(db, actor_id=actor.id, route=route, key=key or "", digest=digest, body=result)
