"""Read models. Rows the caller cannot see are absent, not redacted in place."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from halo.calculations.health import DefinitionView, ObservationView, evaluate_health
from halo.db.models import (
    AgentAssignment,
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
from halo.domain.lifecycle import (
    ACTIVE_ASSIGNMENT,
    PAST_ASSIGNMENT,
    PHASES,
    CompanyFilter,
    phase_label,
)
from halo.errors import HaloError
from halo.services.company_query import matching_cases

AGENTS = [
    {
        "id": "gm",
        "name": "GM",
        "job": "Keeps track of who is working and which decision is waiting on a person. An agent cannot take a step that a partner still has to approve.",
        "output": "PartnerBrief",
        "owner": "Managing partner",
    },
    {
        "id": "scout",
        "name": "Scout",
        "job": "Looks for a concrete reason Halo should take a meeting. If a fact is missing, it stays blank instead of being guessed.",
        "output": "ScoutShortlist",
        "owner": "Investment partner",
    },
    {
        "id": "ainge",
        "name": "Ainge",
        "job": "Writes the investment case and shows which assumptions it depends on. The result is for this company, not a return for the whole fund.",
        "output": "AingeReport",
        "owner": "Deal lead",
    },
    {
        "id": "xavier",
        "name": "Xavier",
        "job": "Compares what the company says with what customers, employees, the brand, and the product actually show. A missing source stays blank instead of becoming a score.",
        "output": "XavierScorecard",
        "owner": "Deal lead",
    },
    {
        "id": "mutombo",
        "name": "Mutombo",
        "job": "Writes the argument against the deal before reading anyone else's conclusion. That first pass is locked before it can be compared with other work.",
        "output": "IndependentRiskReport",
        "owner": "Deal lead and IC",
    },
    {
        "id": "stockton",
        "name": "Stockton",
        "job": "Plans how Halo would help a company get going after an investment. Customer interest is not sales, and a plan does not reserve product.",
        "output": "ActivationThesis",
        "owner": "Platform lead",
    },
    {
        "id": "sloan",
        "name": "Sloan",
        "job": "Suggests practical operating work and counts time that could be freed up. Time saved is not the same as money saved.",
        "output": "OperatingRoadmap",
        "owner": "Operating partner",
    },
    {
        "id": "trainer",
        "name": "Trainer",
        "job": "Checks whether companies Halo owns are sending the reports they owe. A missing or late report is unknown, not healthy.",
        "output": "PortfolioHealth",
        "owner": "Board member",
    },
    {
        "id": "scorekeeper",
        "name": "Scorekeeper",
        "job": "Keeps the record of decisions and the evidence behind them. A decision stays attached to the exact materials that were approved.",
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


def _process_list_item(
    db: Session, case: InvestmentCase, company: Company, names: dict[UUID, str]
) -> dict[str, Any]:
    blocking = db.scalar(
        select(func.count())
        .select_from(Concern)
        .where(Concern.case_id == case.id, Concern.status == "open", Concern.blocking.is_(True))
    )
    active = db.scalars(
        select(AgentAssignment.agent_id).where(
            AgentAssignment.investment_process_id == case.id,
            AgentAssignment.status.in_(ACTIVE_ASSIGNMENT),
        )
    ).all()
    labels = [
        next((item["name"] for item in AGENTS if item["id"] == agent_id), agent_id)
        for agent_id in active
    ]
    return {
        "id": str(company.id),
        "process_id": str(case.id),
        "display_name": company.display_name,
        "legal_name": company.legal_name,
        "website": company.website,
        "stage": company.stage,
        "phase": case.phase,
        "phase_label": phase_label(case.phase),
        "outcome": case.outcome,
        "on_hold": case.on_hold,
        "case_type": case.case_type,
        "owner_name": names.get(company.owner_id, ""),
        "open_blocking_concerns": int(blocking or 0),
        "row_version": company.row_version,
        "active_agents": labels,
    }


def _primary_process(db: Session, company_id: UUID) -> InvestmentCase | None:
    rows = db.scalars(
        select(InvestmentCase)
        .where(InvestmentCase.company_id == company_id, InvestmentCase.case_type != "exit")
        .order_by(InvestmentCase.created_at)
    ).all()
    for row in rows:
        if row.case_type == "initial":
            return row
    return rows[0] if rows else None


def _assignment_query(filt: CompanyFilter):
    stmt = select(AgentAssignment).where(
        AgentAssignment.investment_process_id.in_(matching_cases(filt))
    )
    if filt.agent_id:
        stmt = stmt.where(AgentAssignment.agent_id == filt.agent_id)
    if filt.scope == "active":
        stmt = stmt.where(AgentAssignment.status.in_(ACTIVE_ASSIGNMENT))
    elif filt.scope == "paused":
        stmt = stmt.where(AgentAssignment.status == "paused")
    elif filt.scope == "past":
        stmt = stmt.where(AgentAssignment.status.in_(PAST_ASSIGNMENT))
    return stmt


def _assignments(db: Session, company_id: UUID, filt: CompanyFilter) -> list[dict[str, Any]]:
    scoped = CompanyFilter(
        q=filt.q,
        agent_id=filt.agent_id,
        phase=filt.phase,
        outcome=filt.outcome,
        scope=filt.scope,
        monitor=filt.monitor,
        company_id=company_id,
        funnel=False,
    )
    rows = db.scalars(
        _assignment_query(scoped)
        .where(AgentAssignment.company_id == company_id)
        .order_by(AgentAssignment.agent_id, AgentAssignment.title)
    ).all()
    return [_assignment_card(db, row) for row in rows]


def _assignment_card(db: Session, row: AgentAssignment) -> dict[str, Any]:
    run = db.scalar(
        select(AgentRun)
        .where(AgentRun.assignment_id == row.id)
        .order_by(AgentRun.created_at.desc())
    )
    fresh = False
    if run is not None and run.status == "running" and run.heartbeat_at is not None:
        fresh = run.heartbeat_at >= datetime.now(timezone.utc) - timedelta(seconds=120)
    agent = next((item for item in AGENTS if item["id"] == row.agent_id), None)
    process = (
        db.get(InvestmentCase, row.investment_process_id) if row.investment_process_id else None
    )
    return {
        "id": str(row.id),
        "agent_id": row.agent_id,
        "agent_name": agent["name"] if agent else row.agent_id,
        "title": row.title,
        "objective": row.objective,
        "status": row.status,
        "working_now": bool(fresh),
        "working_state": "working"
        if fresh
        else ("unknown" if run is not None and run.status == "running" else None),
        "process_id": str(row.investment_process_id) if row.investment_process_id else None,
        "phase": process.phase if process else None,
        "phase_label": phase_label(process.phase) if process else None,
        "last_activity_at": _iso(row.last_activity_at),
        "run_id": str(run.id) if run else None,
        "run_status": run.status if run else None,
    }


def _case_matches(db: Session, filt: CompanyFilter, case_id: UUID) -> bool:
    if not filt.applied():
        return True
    return (
        db.scalar(
            select(InvestmentCase.id).where(
                InvestmentCase.id == case_id, InvestmentCase.id.in_(matching_cases(filt))
            )
        )
        is not None
    )


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


def overview(db: Session, principal_id: str, filt: CompanyFilter | None = None) -> dict[str, Any]:
    filt = filt or CompanyFilter(funnel=False)
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
        if not _case_matches(db, filt, case.id):
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
        if company is None or case is None or not _case_matches(db, filt, case.id):
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
    portfolio_ids = select(InvestmentCase.company_id).where(
        InvestmentCase.outcome == "portfolio", InvestmentCase.case_type != "exit"
    )
    attention_stmt = select(Company).where(Company.id.in_(portfolio_ids))
    if filt.applied():
        attention_stmt = attention_stmt.where(
            Company.id.in_(
                select(InvestmentCase.company_id).where(InvestmentCase.id.in_(matching_cases(filt)))
            )
        )
    for company in db.scalars(attention_stmt).all():
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
    funnel = CompanyFilter(
        q=filt.q,
        agent_id=filt.agent_id,
        phase=filt.phase,
        outcome=None,
        scope=filt.scope,
        monitor=filt.monitor,
        company_id=filt.company_id,
        funnel=True,
    )
    counts: dict[str, int] = {phase: 0 for phase in PHASES}
    for phase, count in db.execute(
        select(InvestmentCase.phase, func.count())
        .where(InvestmentCase.id.in_(matching_cases(funnel)))
        .group_by(InvestmentCase.phase)
    ).all():
        if phase in counts:
            counts[phase] = count
    portfolio_processes = (
        db.scalar(
            select(func.count())
            .select_from(InvestmentCase)
            .where(InvestmentCase.outcome == "portfolio", InvestmentCase.case_type != "exit")
        )
        or 0
    )
    notifications = db.scalars(
        select(Notification)
        .where(Notification.principal_id == actor, Notification.read_at.is_(None))
        .order_by(Notification.created_at.desc())
    ).all()
    return {
        "decisions": decisions,
        "blockers": blockers,
        "portfolio_attention": attention,
        "stage_counts": [{"stage": phase, "count": counts[phase]} for phase in PHASES],
        "process_counts": {
            "open_processes": sum(counts.values()),
            "portfolio_processes": int(portfolio_processes),
        },
        "applied_filters": filt.applied(),
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
    db: Session, *, filt: CompanyFilter, cursor: str | None, limit: int
) -> dict[str, Any]:
    matched = matching_cases(filt)
    stmt = (
        select(InvestmentCase, Company)
        .join(Company, Company.id == InvestmentCase.company_id)
        .where(InvestmentCase.id.in_(matched))
        .order_by(Company.display_name, InvestmentCase.id)
    )
    if cursor:
        stmt = stmt.where(Company.display_name > cursor)
    rows = db.execute(stmt.limit(limit + 1)).all()
    page = rows[:limit]
    names = _names(db, {company.owner_id for _, company in page})
    items = [_process_list_item(db, case, company, names) for case, company in page]
    company_count = db.scalar(
        select(func.count(func.distinct(InvestmentCase.company_id))).where(
            InvestmentCase.id.in_(matched)
        )
    )
    process_count = db.scalar(select(func.count()).select_from(matched.subquery()))
    next_cursor = page[-1][1].display_name if len(rows) > limit and page else None
    return {
        "applied_filters": filt.applied(),
        "counts": {
            "distinct_companies": int(company_count or 0),
            "processes": int(process_count or 0),
        },
        "items": items,
        "next_cursor": next_cursor,
    }


def company_detail(
    db: Session, company_id: UUID, filt: CompanyFilter | None = None
) -> dict[str, Any]:
    filt = filt or CompanyFilter(funnel=False)
    company = db.get(Company, company_id)
    if company is None:
        raise HaloError(404, "NOT_FOUND", "Not found.")
    owner = db.get(Principal, company.owner_id)
    cases = db.scalars(select(InvestmentCase).where(InvestmentCase.company_id == company.id)).all()
    case_ids = [case.id for case in cases]
    concerns = (
        db.scalars(select(Concern).where(Concern.case_id.in_(case_ids))).all() if case_ids else []
    )
    runs = (
        db.scalars(select(AgentRun).where(AgentRun.case_id.in_(case_ids))).all() if case_ids else []
    )
    run_ids = [run.id for run in runs]
    artifacts = (
        db.scalars(select(Artifact).where(Artifact.run_id.in_(run_ids))).all() if run_ids else []
    )
    artifact_ids = [item.id for item in artifacts]
    reviews = (
        db.scalars(select(Review).where(Review.artifact_id.in_(artifact_ids))).all()
        if artifact_ids
        else []
    )
    evidence = db.scalars(
        select(EvidenceRecord).where(EvidenceRecord.workspace_id == company.workspace_id)
    ).all()
    documents = {
        row.id: row
        for row in db.scalars(
            select(Document).where(Document.workspace_id == company.workspace_id)
        ).all()
    }
    events = db.scalars(
        select(StageEvent)
        .where(StageEvent.company_id == company.id)
        .order_by(StageEvent.created_at)
    ).all()
    packets = (
        db.scalars(select(IcPacket).where(IcPacket.case_id.in_(case_ids))).all() if case_ids else []
    )
    names = _names(
        db,
        {
            company.owner_id,
            *(case.owner_id for case in cases),
            *(item.owner_id for item in concerns),
        },
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
                "phase": case.phase,
                "phase_label": phase_label(case.phase),
                "outcome": case.outcome,
                "on_hold": case.on_hold,
                "primary": case.id == getattr(_primary_process(db, company.id), "id", None),
                "ic_gaps": ic_gaps(db, case)
                if case.phase == "due_diligence" and case.case_type == "initial"
                else [],
            }
            for case in cases
        ],
        "assignments": _assignments(db, company.id, filt),
        "applied_filters": filt.applied(),
        "filter_restricted": bool(
            filt.agent_id or filt.scope or filt.phase or filt.q or filt.outcome
        ),
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


def portfolio(db: Session, filt: CompanyFilter | None = None) -> dict[str, Any]:
    filt = filt or CompanyFilter(funnel=False)
    owned_ids = select(InvestmentCase.company_id).where(
        InvestmentCase.outcome == "portfolio", InvestmentCase.case_type != "exit"
    )
    stmt = select(Company).where(Company.id.in_(owned_ids)).order_by(Company.display_name)
    if filt.applied():
        stmt = stmt.where(
            Company.id.in_(
                select(InvestmentCase.company_id).where(InvestmentCase.id.in_(matching_cases(filt)))
            )
        )
    companies = db.scalars(stmt).all()
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
    return {
        "companies": items,
        "synced_at": _iso(datetime.now(timezone.utc)),
        "applied_filters": filt.applied(),
    }


def value_ledger(db: Session, filt: CompanyFilter | None = None) -> dict[str, Any]:
    filt = filt or CompanyFilter(funnel=False)
    allowed: set[UUID] | None = None
    if filt.applied():
        allowed = set(
            db.scalars(
                select(InvestmentCase.company_id).where(InvestmentCase.id.in_(matching_cases(filt)))
            ).all()
        )
    entries = db.scalars(select(ValueEntry)).all()
    items = []
    company_ids: set[UUID] = set()
    for entry in entries:
        initiative = db.get(Initiative, entry.initiative_id)
        company = db.get(Company, initiative.company_id) if initiative else None
        if company is None or initiative is None:
            continue
        if allowed is not None and company.id not in allowed:
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
    return {"entries": items, "gaps": gaps, "total": None, "applied_filters": filt.applied()}


def agent_directory(db: Session, filt: CompanyFilter | None = None) -> dict[str, Any]:
    filt = filt or CompanyFilter(funnel=False)
    cards = []
    for agent in AGENTS:
        if filt.agent_id and filt.agent_id != agent["id"]:
            cards.append({**agent, "visible_runs": 0, "company_count": 0, "project_count": 0})
            continue
        scoped = CompanyFilter(
            q=filt.q,
            agent_id=agent["id"],
            phase=filt.phase,
            outcome=filt.outcome,
            scope=filt.scope,
            monitor=filt.monitor,
            company_id=filt.company_id,
            funnel=False,
        )
        assignments = db.scalars(_assignment_query(scoped).order_by(AgentAssignment.title)).all()
        run_count = 0
        if assignments:
            run_count = db.scalar(
                select(func.count())
                .select_from(AgentRun)
                .where(AgentRun.assignment_id.in_([row.id for row in assignments]))
            )
        company_names = (
            {
                row.id: row.display_name
                for row in db.scalars(
                    select(Company).where(Company.id.in_({item.company_id for item in assignments}))
                ).all()
            }
            if assignments
            else {}
        )
        cards.append(
            {
                **agent,
                "visible_runs": int(run_count or 0),
                "company_count": len({row.company_id for row in assignments}),
                "project_count": len(assignments),
                "projects": [
                    {
                        "id": str(row.id),
                        "company_id": str(row.company_id),
                        "company_name": company_names.get(row.company_id, ""),
                        "title": row.title,
                        "status": row.status,
                        "objective": row.objective,
                        **_assignment_brief(db, row.id),
                    }
                    for row in assignments
                ],
            }
        )
    return {"agents": cards, "applied_filters": filt.applied()}


def _assignment_brief(db: Session, assignment_id: UUID) -> dict[str, str]:
    artifact = db.scalars(
        select(Artifact)
        .join(AgentRun, AgentRun.id == Artifact.run_id)
        .where(AgentRun.assignment_id == assignment_id)
        .order_by(Artifact.generated_at.desc())
    ).first()
    content = artifact.content_json if artifact is not None else {}
    return {
        "insight": str(content.get("insight") or content.get("summary") or ""),
        "recommendation": str(content.get("recommendation") or ""),
        "next_step": str(content.get("next_step") or ""),
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
        "comparison_locked": run.agent_name == "mutombo"
        and run.phase == "independent"
        and run.status != "reviewed",
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
