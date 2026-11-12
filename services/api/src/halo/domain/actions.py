"""Human decisions, reviews, and stage gates. Agents do not call these."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from halo.auth.sessions import set_stage_transition
from halo.db.models import (
    AgentRun,
    Artifact,
    AuditEvent,
    CloseRecord,
    Company,
    Concern,
    ConcernDisposition,
    Decision,
    Document,
    EvidenceRecord,
    IcPacket,
    IdempotencyKey,
    InvestmentCase,
    OutboxEvent,
    Principal,
    Review,
    StageEvent,
)
from halo.errors import HaloError
from halo.util import canonical_sha256

IC_ARTIFACTS = (
    ("ainge_report", "Reviewed Ainge report"),
    ("xavier_scorecard", "Reviewed Xavier scorecard"),
    ("independent_risk_report", "Sealed Mutombo independent pass"),
    ("activation_thesis", "Stockton activation thesis"),
)


def has_capability(db: Session, organization_id: UUID, workspace_id: UUID, capability: str) -> bool:
    return bool(
        db.execute(
            text("SELECT halo_has_capability(:org, :ws, :cap)"),
            {"org": organization_id, "ws": workspace_id, "cap": capability},
        ).scalar()
    )


def require_actor(db: Session, principal_id: str | None) -> Principal:
    if principal_id is None:
        raise HaloError(401, "UNAUTHENTICATED", "Sign in is required.")
    actor = db.get(Principal, UUID(principal_id))
    if actor is None or not actor.active:
        raise HaloError(401, "UNAUTHENTICATED", "Sign in is required.")
    return actor


def lookup_idempotency(
    db: Session,
    *,
    principal_id: UUID,
    route: str,
    key: str | None,
    body: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    if not key:
        raise HaloError(400, "IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key header is required.")
    digest = canonical_sha256(body)
    existing = db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.principal_id == principal_id,
            IdempotencyKey.route == route,
            IdempotencyKey.key == key,
        )
    )
    if existing is None:
        return digest, None
    if existing.request_hash != digest:
        raise HaloError(
            409,
            "IDEMPOTENCY_CONFLICT",
            "This idempotency key was already used with a different request.",
        )
    return digest, {"status_code": existing.status_code, "body": existing.response_json}


def store_idempotency(
    db: Session,
    *,
    organization_id: UUID,
    principal_id: UUID,
    route: str,
    key: str,
    request_hash: str,
    status_code: int,
    body: dict[str, Any],
) -> None:
    db.add(
        IdempotencyKey(
            organization_id=organization_id,
            principal_id=principal_id,
            route=route,
            key=key,
            request_hash=request_hash,
            response_json=body,
            status_code=status_code,
            expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        )
    )


def record_review(
    db: Session,
    *,
    actor: Principal,
    artifact_id: UUID,
    artifact_sha256: str,
    verdict: str,
    notes: str,
    request_id: str,
) -> dict[str, Any]:
    if verdict not in {"approve_draft", "request_changes", "reject_unsupported"}:
        raise HaloError(422, "INVALID_VERDICT", "Review verdict is not recognized.")
    if len(notes.strip()) < 8:
        raise HaloError(
            422,
            "NOTES_REQUIRED",
            "A review needs a note. It does not clear concerns or approve an investment.",
        )
    artifact = db.get(Artifact, artifact_id)
    if artifact is None:
        raise HaloError(404, "NOT_FOUND", "Not found.")
    if not has_capability(db, artifact.organization_id, artifact.workspace_id, "artifact.review"):
        raise HaloError(403, "FORBIDDEN", "You cannot review this artifact.")
    if artifact.sha256 != artifact_sha256:
        raise HaloError(
            409,
            "STALE_ARTIFACT",
            "The review must cite the artifact hash that is stored.",
        )
    review = Review(
        organization_id=artifact.organization_id,
        workspace_id=artifact.workspace_id,
        artifact_id=artifact.id,
        artifact_sha256=artifact.sha256,
        reviewer_id=actor.id,
        verdict=verdict,
        notes=notes.strip(),
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add(review)
    db.flush()
    _audit(
        db,
        organization_id=artifact.organization_id,
        workspace_id=artifact.workspace_id,
        actor_id=actor.id,
        action="ReviewRecorded",
        object_id=review.id,
        request_id=request_id,
        payload={"verdict": verdict, "artifact_id": str(artifact.id), "sha256": artifact.sha256},
    )
    return {
        "id": str(review.id),
        "artifact_id": str(artifact.id),
        "artifact_sha256": artifact.sha256,
        "verdict": verdict,
        "notes": review.notes,
        "effect": "Review recorded. Concerns, packet readiness, and investment stage are unchanged.",
    }


def dispose_concern(
    db: Session,
    *,
    actor: Principal,
    concern_id: UUID,
    disposition: str,
    rationale: str,
    evidence_ids: list[UUID],
    expected_version: int,
    request_id: str,
) -> dict[str, Any]:
    concern = db.get(Concern, concern_id)
    if concern is None:
        raise HaloError(404, "NOT_FOUND", "Not found.")
    if not has_capability(db, concern.organization_id, concern.workspace_id, "concern.disposition"):
        raise HaloError(403, "FORBIDDEN", "You cannot disposition this concern.")
    concern = db.scalar(select(Concern).where(Concern.id == concern_id).with_for_update())
    if concern is None:
        raise HaloError(404, "NOT_FOUND", "Not found.")
    if concern.row_version != expected_version:
        raise HaloError(409, "STALE_VERSION", "The concern changed. Reload it and try again.")
    if concern.status != "open":
        raise HaloError(409, "ALREADY_DISPOSED", "This concern already has a disposition.")
    if disposition not in {"resolved", "accepted", "waived"}:
        raise HaloError(
            422, "INVALID_DISPOSITION", "Disposition must be resolved, accepted, or waived."
        )
    if disposition == "waived":
        raise HaloError(
            409,
            "GATE_NOT_MET",
            "This policy does not let a waiver clear the concern.",
            details={"retryable": False},
        )
    if len(rationale.strip()) < 8:
        raise HaloError(422, "RATIONALE_REQUIRED", "A rationale is required.")
    if disposition == "resolved" and not evidence_ids:
        raise HaloError(
            422,
            "EVIDENCE_REQUIRED",
            "Text alone cannot resolve a concern. Attach authorized evidence.",
        )
    for evidence_id in evidence_ids:
        evidence = db.get(EvidenceRecord, evidence_id)
        if evidence is None or evidence.workspace_id != concern.workspace_id:
            raise HaloError(
                422, "EVIDENCE_REQUIRED", "Evidence is not available in this workspace."
            )
    row = ConcernDisposition(
        organization_id=concern.organization_id,
        workspace_id=concern.workspace_id,
        concern_id=concern.id,
        disposition=disposition,
        rationale=rationale.strip(),
        evidence_ids=evidence_ids,
        actor_id=actor.id,
        policy_version=_policy(db, concern),
    )
    db.add(row)
    concern.status = "resolved" if disposition == "resolved" else "accepted"
    concern.blocking = False
    concern.row_version += 1
    db.flush()
    _audit(
        db,
        organization_id=concern.organization_id,
        workspace_id=concern.workspace_id,
        actor_id=actor.id,
        action="ConcernDisposed",
        object_id=concern.id,
        request_id=request_id,
        payload={"disposition": disposition, "status": concern.status},
    )
    return {
        "concern_id": str(concern.id),
        "status": concern.status,
        "blocking": concern.blocking,
        "row_version": concern.row_version,
        "effect": "Disposition recorded. This does not verify a claim or approve an investment.",
    }


def stage_action(
    db: Session,
    *,
    actor: Principal,
    case_id: UUID,
    action: str,
    rationale: str,
    expected_case_version: int,
    request_id: str,
) -> dict[str, Any]:
    if action not in {
        "submit_ic",
        "accept_first_look",
        "advance_partner_review",
        "open_diligence",
        "advance_closing",
        "confirm_close",
        "pass",
        "pause",
    }:
        raise HaloError(422, "UNKNOWN_ACTION", "Stage action is not recognized.")
    case, company = _visible_case(db, case_id)
    if action == "submit_ic" and not has_capability(
        db, case.organization_id, case.workspace_id, "case.submit_ic"
    ):
        raise HaloError(403, "FORBIDDEN", "You cannot submit this case to IC.")
    if action in {"accept_first_look", "advance_partner_review"} and not has_capability(
        db, case.organization_id, case.workspace_id, "ic.decide"
    ):
        raise HaloError(
            403, "FORBIDDEN", "Moving a process forward requires explicit investment authority."
        )
    if action == "open_diligence" and not has_capability(
        db, case.organization_id, case.workspace_id, "case.submit_ic"
    ):
        raise HaloError(403, "FORBIDDEN", "Opening diligence requires deal authority.")
    if action in {"advance_closing", "confirm_close"} and not has_capability(
        db, case.organization_id, case.workspace_id, "ic.decide"
    ):
        raise HaloError(403, "FORBIDDEN", "Closing authority is required.")
    if action in {"pass", "pause"} and not (
        has_capability(db, case.organization_id, case.workspace_id, "ic.decide")
        or has_capability(db, case.organization_id, case.workspace_id, "case.submit_ic")
    ):
        raise HaloError(403, "FORBIDDEN", "You cannot change this stage.")
    case, company = _lock_case(db, case_id)
    if case.row_version != expected_case_version:
        raise HaloError(409, "STALE_VERSION", "The case changed. Reload it and try again.")
    if len(rationale.strip()) < 8:
        raise HaloError(422, "RATIONALE_REQUIRED", "A rationale is required.")
    if action == "submit_ic":
        if case.phase != "due_diligence":
            raise HaloError(
                409, "GATE_NOT_MET", "Only a process in due diligence can be submitted to IC."
            )
        missing = ic_gaps(db, case)
        if missing:
            raise HaloError(
                409,
                "GATE_NOT_MET",
                f"{company.display_name} cannot be submitted to IC yet.",
                details={"missing_requirements": missing, "retryable": False},
            )
        _move(db, actor, company, case, "ic_review", rationale.strip(), "stage_action", None)
        case.status = "ic_review"
        case.phase = "investment_committee"
    elif action == "accept_first_look":
        if case.phase != "sourcing":
            raise HaloError(
                409, "GATE_NOT_MET", "Only a sourcing process can be accepted into screening."
            )
        _move(db, actor, company, case, "first_look", rationale.strip(), "stage_action", None)
        case.status = "first_look"
        case.phase = "screening"
    elif action == "advance_partner_review":
        if case.phase != "screening":
            raise HaloError(409, "GATE_NOT_MET", "Partner review opens from screening.")
        _move(db, actor, company, case, "partner_review", rationale.strip(), "stage_action", None)
        case.status = "partner_review"
        case.phase = "partner_review"
    elif action == "open_diligence":
        if case.phase != "partner_review":
            raise HaloError(409, "GATE_NOT_MET", "Diligence opens from partner review.")
        _move(db, actor, company, case, "diligence", rationale.strip(), "stage_action", None)
        case.status = "diligence"
        case.phase = "due_diligence"
    elif action == "advance_closing":
        if case.phase != "term_sheet":
            raise HaloError(409, "GATE_NOT_MET", "Closing opens from the term sheet phase.")
        if company.stage == "owned":
            case.status = "closing"
            case.phase = "negotiation_closing"
            case.phase_entered_at = datetime.now(timezone.utc)
        else:
            _move(db, actor, company, case, "closing", rationale.strip(), "stage_action", None)
            case.status = "closing"
    elif action == "confirm_close":
        if case.phase != "negotiation_closing":
            raise HaloError(
                409,
                "GATE_NOT_MET",
                "Portfolio starts only after an authorized close from negotiation and closing.",
            )
        document = db.scalar(
            select(Document).where(
                Document.workspace_id == case.workspace_id,
                Document.source_kind == "closing",
                Document.ingestion_status == "verified",
            )
        )
        if document is None:
            raise HaloError(
                409,
                "GATE_NOT_MET",
                "Close confirmation needs a verified closing document on this company.",
            )
        now = datetime.now(timezone.utc)
        db.add(
            CloseRecord(
                organization_id=case.organization_id,
                workspace_id=case.workspace_id,
                case_id=case.id,
                document_id=document.id,
                effective_at=now,
                actor_id=actor.id,
                verified_at=now,
            )
        )
        if company.stage != "owned":
            _move(db, actor, company, case, "owned", rationale.strip(), "stage_action", None)
        else:
            case.outcome = "portfolio"
            case.outcome_at = now
            case.on_hold = False
        case.status = "owned"
    elif action in {"pass", "pause"}:
        target = "passed" if action == "pass" else "paused"
        if company.stage == "owned" and case.case_type != "initial":
            case.status = target
        else:
            _move(db, actor, company, case, target, rationale.strip(), "stage_action", None)
            case.status = target
    case.row_version += 1
    db.flush()
    return {
        "case_id": str(case.id),
        "company_id": str(company.id),
        "company_stage": company.stage,
        "case_status": case.status,
        "case_version": case.row_version,
    }


def record_decision(
    db: Session,
    *,
    actor: Principal,
    packet_id: UUID,
    packet_sha256: str,
    decision: str,
    rationale: str,
    expected_case_version: int,
    policy_version: str,
    request_id: str,
) -> dict[str, Any]:
    if decision not in {"approve", "pass", "defer", "terms_revision"}:
        raise HaloError(
            422, "INVALID_DECISION", "Decision must be approve, pass, defer, or terms_revision."
        )
    if len(rationale.strip()) < 8:
        raise HaloError(422, "RATIONALE_REQUIRED", "A rationale is required.")
    packet = db.get(IcPacket, packet_id)
    if packet is None:
        raise HaloError(404, "NOT_FOUND", "Not found.")
    if not has_capability(db, packet.organization_id, packet.workspace_id, "ic.decide"):
        raise HaloError(
            403, "FORBIDDEN", "Investment committee authority is not on your membership."
        )
    packet = db.scalar(select(IcPacket).where(IcPacket.id == packet_id).with_for_update())
    if packet is None:
        raise HaloError(404, "NOT_FOUND", "Not found.")
    case, company = _lock_case(db, packet.case_id)
    if case.row_version != expected_case_version:
        raise HaloError(409, "STALE_VERSION", "The case changed. Reload it and try again.")
    if packet.manifest_sha256 != packet_sha256 or packet.policy_version != policy_version:
        raise HaloError(
            409,
            "STALE_PACKET",
            "The decision does not match the frozen packet hash or policy version.",
        )
    if packet.status != "frozen":
        raise HaloError(409, "STALE_PACKET", "This packet is no longer open for a decision.")
    existing = db.scalar(select(Decision).where(Decision.packet_id == packet.id))
    if existing is not None:
        raise HaloError(409, "ALREADY_DECIDED", "This packet already has a decision.")
    blocking = _open_blocking(db, case.id)
    if decision == "approve" and blocking:
        raise HaloError(
            409,
            "GATE_NOT_MET",
            f"{company.display_name} cannot be approved yet.",
            details={
                "missing_requirements": [
                    {"kind": "blocking_concern", "label": item.question} for item in blocking
                ],
                "retryable": False,
            },
        )
    row = Decision(
        organization_id=packet.organization_id,
        workspace_id=packet.workspace_id,
        packet_id=packet.id,
        packet_sha256=packet.manifest_sha256,
        actor_id=actor.id,
        decision=decision,
        rationale=rationale.strip(),
        decided_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()
    if decision == "approve" and case.case_type == "initial":
        if case.phase != "investment_committee":
            raise HaloError(
                409, "GATE_NOT_MET", "Approval of an initial case requires Investment Committee."
            )
        _move(db, actor, company, case, "term_sheet", rationale.strip(), "decision", row.id)
        case.status = "term_sheet"
        case.phase = "term_sheet"
    elif decision == "approve" and case.case_type == "follow_on":
        if company.stage != "owned":
            raise HaloError(409, "GATE_NOT_MET", "A follow-on approval does not create ownership.")
        case.status = "closing"
        case.phase = "term_sheet"
        case.phase_entered_at = datetime.now(timezone.utc)
    elif decision == "pass" and case.case_type == "initial" and company.stage != "owned":
        _move(db, actor, company, case, "passed", rationale.strip(), "decision", row.id)
        case.status = "passed"
    elif decision == "pass":
        case.status = "passed"
    elif decision == "defer":
        case.status = "deferred"
    else:
        case.status = "terms_revision"
    packet.status = "decided"
    case.row_version += 1
    _audit(
        db,
        organization_id=packet.organization_id,
        workspace_id=packet.workspace_id,
        actor_id=actor.id,
        action="ICDecisionRecorded",
        object_id=row.id,
        request_id=request_id,
        payload={
            "decision": decision,
            "packet_id": str(packet.id),
            "packet_sha256": packet.manifest_sha256,
        },
    )
    db.add(
        OutboxEvent(
            organization_id=packet.organization_id,
            workspace_id=packet.workspace_id,
            aggregate_id=row.id,
            kind="ICDecisionRecorded",
            payload_ref=f"decisions/{row.id}",
            status="pending",
        )
    )
    db.flush()
    return {
        "decision_id": str(row.id),
        "decision": decision,
        "company_id": str(company.id),
        "company_stage": company.stage,
        "case_status": case.status,
        "case_version": case.row_version,
        "packet_status": packet.status,
        "owned": company.stage == "owned",
    }


def ic_gaps(db: Session, case: InvestmentCase) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    for concern in _open_blocking(db, case.id):
        missing.append({"kind": "blocking_concern", "label": concern.question})
    artifacts = db.scalars(
        select(Artifact)
        .join(AgentRun, AgentRun.id == Artifact.run_id)
        .where(AgentRun.case_id == case.id)
    ).all()
    by_kind = {item.kind: item for item in artifacts}
    for kind, label in IC_ARTIFACTS:
        artifact = by_kind.get(kind)
        if artifact is None or artifact.status not in {"validated", "reviewed", "sealed"}:
            missing.append({"kind": "artifact", "label": label})
            continue
        if kind == "independent_risk_report" and artifact.sealed_at is None:
            missing.append(
                {"kind": "independent_pass", "label": "Mutombo independent pass is not sealed"}
            )
    packet = db.scalar(
        select(IcPacket).where(IcPacket.case_id == case.id, IcPacket.status == "frozen")
    )
    if packet is None:
        missing.append({"kind": "packet", "label": "IC packet is not frozen"})
    return missing


def _open_blocking(db: Session, case_id: UUID) -> list[Concern]:
    return list(
        db.scalars(
            select(Concern).where(
                Concern.case_id == case_id,
                Concern.status == "open",
                Concern.blocking.is_(True),
            )
        ).all()
    )


def _visible_case(db: Session, case_id: UUID) -> tuple[InvestmentCase, Company]:
    case = db.get(InvestmentCase, case_id)
    if case is None:
        raise HaloError(404, "NOT_FOUND", "Not found.")
    company = db.get(Company, case.company_id)
    if company is None:
        raise HaloError(404, "NOT_FOUND", "Not found.")
    return case, company


def _lock_case(db: Session, case_id: UUID) -> tuple[InvestmentCase, Company]:
    case = db.scalar(select(InvestmentCase).where(InvestmentCase.id == case_id).with_for_update())
    if case is None:
        raise HaloError(404, "NOT_FOUND", "Not found.")
    company = db.scalar(select(Company).where(Company.id == case.company_id).with_for_update())
    if company is None:
        raise HaloError(404, "NOT_FOUND", "Not found.")
    return case, company


def _policy(db: Session, concern: Concern) -> str:
    from halo.db.models import Organization

    org = db.get(Organization, concern.organization_id)
    return org.policy_version if org is not None else "unknown"


def _move(
    db: Session,
    actor: Principal,
    company: Company,
    case: InvestmentCase,
    to_stage: str,
    reason: str,
    source_kind: str,
    source_id: UUID | None,
) -> None:
    event = StageEvent(
        id=uuid4(),
        organization_id=company.organization_id,
        workspace_id=company.workspace_id,
        company_id=company.id,
        case_id=case.id,
        from_stage=company.stage,
        to_stage=to_stage,
        reason=reason,
        actor_id=actor.id,
        source_kind=source_kind,
        source_id=source_id,
    )
    db.add(event)
    db.flush()
    set_stage_transition(db, str(event.id))
    company.stage = to_stage
    company.row_version += 1
    _sync_process(case, to_stage)
    db.flush()


def _sync_process(case: InvestmentCase, to_stage: str) -> None:
    """Keep the process phase and outcome aligned with an authorized stage event."""
    now = datetime.now(timezone.utc)
    if to_stage == "owned":
        case.outcome = "portfolio"
        case.outcome_at = now
        case.on_hold = False
        if case.phase == "unknown":
            case.phase = "negotiation_closing"
    elif to_stage == "passed":
        case.outcome = "passed"
        case.outcome_at = now
        case.on_hold = False
    elif to_stage == "paused":
        case.on_hold = True
    else:
        phase = {
            "discovered": "sourcing",
            "first_look": "screening",
            "diligence": "due_diligence",
            "ic_review": "investment_committee",
            "term_sheet": "term_sheet",
            "closing": "negotiation_closing",
            "partner_review": "partner_review",
        }.get(to_stage)
        if phase is not None:
            case.phase = phase
            case.phase_entered_at = now
            if case.outcome == "passed":
                case.outcome = "open"
            case.on_hold = False


def _audit(
    db: Session,
    *,
    organization_id: UUID,
    workspace_id: UUID,
    actor_id: UUID,
    action: str,
    object_id: UUID,
    request_id: str,
    payload: dict[str, Any],
) -> None:
    db.add(
        AuditEvent(
            organization_id=organization_id,
            workspace_id=workspace_id,
            actor_id=actor_id,
            action=action,
            object_id=object_id,
            request_id=request_id,
            payload_redacted=payload,
        )
    )
