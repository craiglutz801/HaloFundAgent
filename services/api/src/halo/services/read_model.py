"""Read models. Rows the caller cannot see are absent, not redacted in place."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from halo.calculations.health import DefinitionView, ObservationView, evaluate_health
from halo.db.models import (
    AgentRun,
    Artifact,
    Company,
    Concern,
    Decision,
    Document,
    EvidenceRecord,
    IcPacket,
    Initiative,
    InvestmentCase,
    MetricDefinition,
    MetricObservation,
    Notification,
    Principal,
    Review,
    StageEvent,
    ValueEntry,
    Workspace,
    WorkspaceMembership,
)
from halo.domain.actions import has_capability, ic_gaps
from halo.errors import HaloError

AGENTS = [
    {
        "id": "gm",
        "name": "GM",
        "job": "Route bounded work, detect stalls, and summarize decisions needed.",
        "output": "PartnerBrief",
        "owner": "Managing partner",
    },
    {
        "id": "scout",
        "name": "Scout",
        "job": "Find an evidenced reason for Halo to meet a company.",
        "output": "ScoutShortlist",
        "owner": "Investment partner",
    },
    {
        "id": "ainge",
        "name": "Ainge",
        "job": "Produce a sourced investment case and expose the assumptions that could change it.",
        "output": "AingeReport",
        "owner": "Deal lead",
    },
    {
        "id": "xavier",
        "name": "Xavier",
        "job": "Compare the company story with customer, employee, brand, and product evidence.",
        "output": "XavierScorecard",
        "owner": "Deal lead",
    },
    {
        "id": "mutombo",
        "name": "Mutombo",
        "job": "Form an independent bear case, then check assembled claims.",
        "output": "IndependentRiskReport",
        "owner": "Deal lead and IC",
    },
    {
        "id": "stockton",
        "name": "Stockton",
        "job": "Plan platform activation without booking inventory or promising access.",
        "output": "ActivationThesis",
        "owner": "Platform lead",
    },
    {
        "id": "sloan",
        "name": "Sloan",
        "job": "Recommend operating work and separate capacity from cash saved.",
        "output": "OperatingRoadmap",
        "owner": "Operating partner",
    },
    {
        "id": "trainer",
        "name": "Trainer",
        "job": "Report portfolio health and prepare board discussion.",
        "output": "PortfolioHealth",
        "owner": "Board member",
    },
    {
        "id": "scorekeeper",
        "name": "Scorekeeper",
        "job": "Keep the decision journal, value evidence, and release-controlled reporting.",
        "output": "DecisionRetrospective",
        "owner": "CFO",
    },
]


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def _money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _names(db: Session, ids: set[UUID]) -> dict[UUID, str]:
    if not ids:
        return {}
    rows = db.scalars(select(Principal).where(Principal.id.in_(ids))).all()
    return {row.id: row.display_name for row in rows}


def me(db: Session, principal_id: str) -> dict[str, Any]:
    actor = db.get(Principal, UUID(principal_id))
    if actor is None:
        raise HaloError(401, "UNAUTHENTICATED", "Sign in is required.")
    memberships = db.scalars(
        select(WorkspaceMembership).where(WorkspaceMembership.principal_id == actor.id)
    ).all()
    workspaces = []
    for membership in memberships:
        workspace = db.get(Workspace, membership.workspace_id)
        if workspace is None:
            continue
        workspaces.append(
            {
                "id": str(workspace.id),
                "name": workspace.name,
                "kind": workspace.kind,
                "company_id": str(workspace.company_id) if workspace.company_id else None,
                "role": membership.role,
                "capabilities": list(membership.capabilities),
            }
        )
    return {
        "principal": {
            "id": str(actor.id),
            "display_name": actor.display_name,
            "email": actor.email,
        },
        "workspaces": workspaces,
    }


def overview(db: Session, principal_id: str) -> dict[str, Any]:
    actor = UUID(principal_id)
    packets = db.scalars(select(IcPacket).where(IcPacket.status == "frozen")).all()
    decisions = []
    for packet in packets:
        if db.scalar(select(Decision.id).where(Decision.packet_id == packet.id)) is not None:
            continue
        if not has_capability(db, packet.organization_id, packet.workspace_id, "ic.decide"):
            continue
        case = db.get(InvestmentCase, packet.case_id)
        company = db.get(Company, case.company_id) if case else None
        if case is None or company is None:
            continue
        owner = db.get(Principal, case.owner_id)
        reason = (
            "IC decision on the follow-on packet"
            if case.case_type == "follow_on"
            else "IC decision on the reviewed initial investment packet"
        )
        decisions.append(
            {
                "packet_id": str(packet.id),
                "case_id": str(case.id),
                "company_id": str(company.id),
                "company_name": company.display_name,
                "case_type": case.case_type,
                "owner_name": owner.display_name if owner else "",
                "due_at": _iso(case.due_at),
                "reason": reason,
                "manifest_sha256": packet.manifest_sha256,
            }
        )
    concerns = db.scalars(
        select(Concern).where(Concern.status == "open", Concern.blocking.is_(True))
    ).all()
    names = _names(db, {item.owner_id for item in concerns})
    blockers = []
    for concern in concerns:
        case = db.get(InvestmentCase, concern.case_id)
        company = db.get(Company, case.company_id) if case else None
        if company is None:
            continue
        blockers.append(
            {
                "concern_id": str(concern.id),
                "case_id": str(concern.case_id),
                "company_id": str(company.id),
                "company_name": company.display_name,
                "question": concern.question,
                "severity": concern.severity,
                "owner_name": names.get(concern.owner_id, ""),
            }
        )
    attention = []
    for company in db.scalars(select(Company).where(Company.stage == "owned")).all():
        health, missing = _health(db, company)
        if health != "on_plan":
            attention.append(
                {
                    "company_id": str(company.id),
                    "company_name": company.display_name,
                    "health": health,
                    "reason": _health_reason(health, missing),
                }
            )
    counts: dict[str, int] = {}
    for stage, count in db.execute(
        select(Company.stage, func.count()).group_by(Company.stage)
    ).all():
        counts[stage] = count
    order = [
        "discovered",
        "first_look",
        "diligence",
        "ic_review",
        "closing",
        "owned",
        "exited",
        "passed",
        "paused",
    ]
    notifications = db.scalars(
        select(Notification)
        .where(Notification.principal_id == actor, Notification.read_at.is_(None))
        .order_by(Notification.created_at.desc())
    ).all()
    return {
        "decisions": decisions,
        "blockers": blockers,
        "portfolio_attention": attention,
        "stage_counts": [{"stage": stage, "count": counts.get(stage, 0)} for stage in order],
        "notifications": [
            {
                "id": str(item.id),
                "title": item.title,
                "body": item.body,
                "severity": item.severity,
                "created_at": _iso(item.created_at),
            }
            for item in notifications
        ],
        "synced_at": _iso(datetime.now(timezone.utc)),
    }


def list_companies(
    db: Session, *, stage: str | None, query: str | None, cursor: str | None, limit: int
) -> dict[str, Any]:
    stmt = select(Company).order_by(Company.display_name, Company.id)
    if stage:
        stmt = stmt.where(Company.stage == stage)
    if query:
        stmt = stmt.where(Company.display_name.ilike(f"%{query}%"))
    if cursor:
        stmt = stmt.where(Company.display_name > cursor)
    rows = db.scalars(stmt.limit(limit + 1)).all()
    page = rows[:limit]
    names = _names(db, {row.owner_id for row in page})
    items = []
    for company in page:
        blocking = db.scalar(
            select(func.count())
            .select_from(Concern)
            .join(InvestmentCase, InvestmentCase.id == Concern.case_id)
            .where(
                InvestmentCase.company_id == company.id,
                Concern.status == "open",
                Concern.blocking.is_(True),
            )
        )
        items.append(
            {
                "id": str(company.id),
                "display_name": company.display_name,
                "legal_name": company.legal_name,
                "website": company.website,
                "stage": company.stage,
                "owner_name": names.get(company.owner_id, ""),
                "open_blocking_concerns": int(blocking or 0),
                "row_version": company.row_version,
            }
        )
    next_cursor = page[-1].display_name if len(rows) > limit and page else None
    return {"items": items, "next_cursor": next_cursor}


def company_detail(db: Session, company_id: UUID) -> dict[str, Any]:
    company = db.get(Company, company_id)
    if company is None:
        raise HaloError(404, "NOT_FOUND", "Not found.")
    owner = db.get(Principal, company.owner_id)
    cases = db.scalars(
        select(InvestmentCase).where(InvestmentCase.company_id == company.id)
    ).all()
    case_ids = [case.id for case in cases]
    concerns = db.scalars(select(Concern).where(Concern.case_id.in_(case_ids))).all() if case_ids else []
    runs = db.scalars(select(AgentRun).where(AgentRun.case_id.in_(case_ids))).all() if case_ids else []
    run_ids = [run.id for run in runs]
    artifacts = db.scalars(select(Artifact).where(Artifact.run_id.in_(run_ids))).all() if run_ids else []
    artifact_ids = [item.id for item in artifacts]
    reviews = (
        db.scalars(select(Review).where(Review.artifact_id.in_(artifact_ids))).all() if artifact_ids else []
    )
    evidence = db.scalars(
        select(EvidenceRecord).where(EvidenceRecord.workspace_id == company.workspace_id)
    ).all()
    documents = {
        row.id: row
        for row in db.scalars(select(Document).where(Document.workspace_id == company.workspace_id)).all()
    }
    events = db.scalars(
        select(StageEvent)
        .where(StageEvent.company_id == company.id)
        .order_by(StageEvent.created_at)
    ).all()
    packets = db.scalars(select(IcPacket).where(IcPacket.case_id.in_(case_ids))).all() if case_ids else []
    names = _names(
        db,
        {company.owner_id, *(case.owner_id for case in cases), *(item.owner_id for item in concerns)},
    )
    return {
        "company": {
            "id": str(company.id),
            "legal_name": company.legal_name,
            "display_name": company.display_name,
            "website": company.website,
            "stage": company.stage,
            "owner_name": owner.display_name if owner else "",
            "row_version": company.row_version,
        },
        "cases": [
            {
                "id": str(case.id),
                "case_type": case.case_type,
                "status": case.status,
                "owner_name": names.get(case.owner_id, ""),
                "due_at": _iso(case.due_at),
                "row_version": case.row_version,
                "policy_version": case.policy_version,
                "ic_gaps": ic_gaps(db, case) if company.stage == "diligence" and case.case_type == "initial" else [],
            }
            for case in cases
        ],
        "stage_events": [
            {
                "id": str(event.id),
                "from_stage": event.from_stage,
                "to_stage": event.to_stage,
                "reason": event.reason,
                "created_at": _iso(event.created_at),
            }
            for event in events
        ],
        "concerns": [
            {
                "id": str(item.id),
                "case_id": str(item.case_id),
                "question": item.question,
                "severity": item.severity,
                "blocking": item.blocking,
                "status": item.status,
                "owner_name": names.get(item.owner_id, ""),
                "row_version": item.row_version,
                "due_at": _iso(item.due_at),
            }
            for item in concerns
        ],
        "runs": [
            {
                "id": str(run.id),
                "case_id": str(run.case_id) if run.case_id else None,
                "agent_name": run.agent_name,
                "phase": run.phase,
                "status": run.status,
                "status_detail": run.status_detail,
                "provider": run.provider,
                "model": run.model,
            }
            for run in runs
        ],
        "artifacts": [_artifact(item) for item in artifacts],
        "reviews": [
            {
                "id": str(review.id),
                "artifact_id": str(review.artifact_id),
                "artifact_sha256": review.artifact_sha256,
                "verdict": review.verdict,
                "notes": review.notes,
                "reviewed_at": _iso(review.reviewed_at),
            }
            for review in reviews
        ],
        "evidence": [_evidence(item, documents.get(item.document_id)) for item in evidence],
        "packets": [
            {
                "id": str(packet.id),
                "case_id": str(packet.case_id),
                "version": packet.version,
                "status": packet.status,
                "manifest_sha256": packet.manifest_sha256,
                "policy_version": packet.policy_version,
            }
            for packet in packets
        ],
    }


def evidence_detail(db: Session, evidence_id: UUID) -> dict[str, Any]:
    row = db.get(EvidenceRecord, evidence_id)
    if row is None:
        raise HaloError(404, "NOT_FOUND", "Not found.")
    document = db.get(Document, row.document_id)
    return _evidence(row, document)


def search_evidence(db: Session, query: str) -> dict[str, Any]:
    stmt = select(EvidenceRecord)
    if query.strip():
        stmt = stmt.where(
            func.to_tsvector("english", EvidenceRecord.excerpt).bool_op("@@")(
                func.plainto_tsquery("english", query)
            )
        )
    rows = db.scalars(stmt.limit(50)).all()
    return {
        "items": [
            {
                "id": str(row.id),
                "kind": row.kind,
                "locator": row.locator_json,
                "origin_class": row.origin_class,
            }
            for row in rows
        ]
    }


def packet_detail(db: Session, packet_id: UUID) -> dict[str, Any]:
    packet = db.get(IcPacket, packet_id)
    if packet is None:
        raise HaloError(404, "NOT_FOUND", "Not found.")
    case = db.get(InvestmentCase, packet.case_id)
    company = db.get(Company, case.company_id) if case else None
    if case is None or company is None:
        raise HaloError(404, "NOT_FOUND", "Not found.")
    artifacts = db.scalars(select(Artifact).where(Artifact.id.in_(packet.artifact_ids or []))).all()
    decision = db.scalar(select(Decision).where(Decision.packet_id == packet.id))
    concerns = db.scalars(select(Concern).where(Concern.case_id == case.id)).all()
    return {
        "id": str(packet.id),
        "status": packet.status,
        "version": packet.version,
        "manifest_sha256": packet.manifest_sha256,
        "policy_version": packet.policy_version,
        "case": {
            "id": str(case.id),
            "case_type": case.case_type,
            "status": case.status,
            "row_version": case.row_version,
        },
        "company": {
            "id": str(company.id),
            "display_name": company.display_name,
            "stage": company.stage,
        },
        "can_decide": has_capability(db, packet.organization_id, packet.workspace_id, "ic.decide")
        and packet.status == "frozen"
        and decision is None,
        "artifacts": [_artifact(item) for item in artifacts],
        "concerns": [
            {
                "id": str(item.id),
                "question": item.question,
                "severity": item.severity,
                "blocking": item.blocking,
                "status": item.status,
            }
            for item in concerns
        ],
        "decision": None
        if decision is None
        else {
            "id": str(decision.id),
            "decision": decision.decision,
            "rationale": decision.rationale,
            "decided_at": _iso(decision.decided_at),
            "packet_sha256": decision.packet_sha256,
        },
    }


def portfolio(db: Session) -> dict[str, Any]:
    companies = db.scalars(select(Company).where(Company.stage == "owned").order_by(Company.display_name)).all()
    items = []
    for company in companies:
        health, missing = _health(db, company)
        items.append(
            {
                "company_id": str(company.id),
                "display_name": company.display_name,
                "health": health,
                "missing_metrics": missing,
                "reason": _health_reason(health, missing),
            }
        )
    return {"companies": items, "synced_at": _iso(datetime.now(timezone.utc))}


def value_ledger(db: Session) -> dict[str, Any]:
    entries = db.scalars(select(ValueEntry)).all()
    items = []
    company_ids: set[UUID] = set()
    for entry in entries:
        initiative = db.get(Initiative, entry.initiative_id)
        company = db.get(Company, initiative.company_id) if initiative else None
        if company is None or initiative is None:
            continue
        company_ids.add(company.id)
        items.append(
            {
                "id": str(entry.id),
                "company_id": str(company.id),
                "company_name": company.display_name,
                "initiative_id": str(initiative.id),
                "agent_name": initiative.agent_name,
                "goal": initiative.goal,
                "metric": entry.metric,
                "amount": _money(entry.amount),
                "unit": entry.unit,
                "classification": entry.classification,
                "method": entry.method,
                "period": entry.period,
            }
        )
    gaps = []
    for company_id in company_ids:
        company = db.get(Company, company_id)
        if company is None:
            continue
        gaps.append(
            {
                "company_id": str(company.id),
                "company_name": company.display_name,
                "metric": "incremental_revenue",
                "reason": "Tagged activity is not revenue. No incremental revenue evidence is on file.",
            }
        )
        gaps.append(
            {
                "company_id": str(company.id),
                "company_name": company.display_name,
                "metric": "cash_savings",
                "reason": "Estimated capacity is not cash saved. No verified budget change is on file.",
            }
        )
    return {"entries": items, "gaps": gaps, "total": None}


def agent_directory(db: Session) -> dict[str, Any]:
    counts = dict(db.execute(select(AgentRun.agent_name, func.count()).group_by(AgentRun.agent_name)).all())
    return {
        "agents": [{**agent, "visible_runs": int(counts.get(agent["id"], 0))} for agent in AGENTS]
    }


def run_detail(db: Session, run_id: UUID) -> dict[str, Any]:
    run = db.get(AgentRun, run_id)
    if run is None:
        raise HaloError(404, "NOT_FOUND", "Not found.")
    artifacts = db.scalars(select(Artifact).where(Artifact.run_id == run.id)).all()
    company = None
    if run.case_id is not None:
        case = db.get(InvestmentCase, run.case_id)
        if case is not None:
            company = db.get(Company, case.company_id)
    return {
        "id": str(run.id),
        "agent_name": run.agent_name,
        "phase": run.phase,
        "status": run.status,
        "status_detail": run.status_detail,
        "provider": run.provider,
        "model": run.model,
        "prompt_version": run.prompt_version,
        "company_id": str(company.id) if company else None,
        "company_name": company.display_name if company else None,
        "case_id": str(run.case_id) if run.case_id else None,
        "artifacts": [_artifact(item) for item in artifacts],
        "comparison_locked": run.agent_name == "mutombo" and run.phase == "independent" and run.status != "reviewed",
    }


def _artifact(item: Artifact) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "run_id": str(item.run_id),
        "kind": item.kind,
        "phase": item.phase,
        "version": item.version,
        "sha256": item.sha256,
        "status": item.status,
        "sealed_at": _iso(item.sealed_at),
        "content": item.content_json,
    }


def _evidence(row: EvidenceRecord, document: Document | None) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "kind": row.kind,
        "locator": row.locator_json,
        "excerpt": row.excerpt,
        "observed_start": _iso(row.observed_start),
        "observed_end": _iso(row.observed_end),
        "collected_at": _iso(row.collected_at),
        "sample_size": row.sample_size,
        "origin_class": row.origin_class,
        "limitations": row.limitations,
        "status": row.status,
        "document": None
        if document is None
        else {
            "id": str(document.id),
            "filename": document.filename,
            "mime": document.mime,
            "sha256": document.sha256,
            "version": document.version,
            "source_kind": document.source_kind,
        },
    }


def _health(db: Session, company: Company) -> tuple[str, list[str]]:
    definitions = db.scalars(
        select(MetricDefinition).where(MetricDefinition.workspace_id == company.workspace_id)
    ).all()
    observations: dict[str, list[ObservationView]] = {}
    views = []
    for definition in definitions:
        views.append(
            DefinitionView(
                slug=definition.slug,
                required=definition.required,
                freshness_limit_days=definition.freshness_limit_days,
            )
        )
        rows = db.scalars(
            select(MetricObservation).where(MetricObservation.definition_id == definition.id)
        ).all()
        observations[definition.slug] = [
            ObservationView(
                period_end=row.period_end,
                value=row.value,
                completeness=row.completeness,
                observed_at=row.observed_at,
            )
            for row in rows
        ]
    if not any(item.required for item in views):
        return "unknown", ["required_metric"]
    return evaluate_health(views, observations, datetime.now(timezone.utc))


def _health_reason(health: str, missing: list[str]) -> str:
    if health == "unknown":
        metrics = ", ".join(missing) if missing else "required reporting"
        return f"{metrics} is missing or stale. A prior green period does not keep health on plan."
    return "Required reporting is fresh."
