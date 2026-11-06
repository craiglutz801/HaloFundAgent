"""One filter applied to processes and the assignments on those processes."""

from __future__ import annotations

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.sql import Select

from halo.db.models import AgentAssignment, Company, InvestmentCase
from halo.domain.lifecycle import ACTIVE_ASSIGNMENT, PAST_ASSIGNMENT, CompanyFilter


def matching_cases(filt: CompanyFilter) -> Select:
    """Case ids that satisfy phase, outcome, and the same assignment predicate."""
    stmt = select(InvestmentCase.id).join(Company, Company.id == InvestmentCase.company_id)
    stmt = stmt.where(InvestmentCase.case_type != "exit")
    if filt.company_id is not None:
        stmt = stmt.where(Company.id == filt.company_id)
    if filt.phase is not None:
        stmt = stmt.where(InvestmentCase.phase == filt.phase)
    if filt.outcome is not None:
        stmt = stmt.where(InvestmentCase.outcome == filt.outcome)
    elif filt.funnel:
        stmt = stmt.where(InvestmentCase.outcome == "open", InvestmentCase.on_hold.is_(False))
    if filt.monitor is True:
        stmt = stmt.where(InvestmentCase.monitor.is_(True))
    elif filt.monitor is False:
        stmt = stmt.where(InvestmentCase.monitor.is_(False))
    if filt.q or filt.agent_id or filt.scope:
        stmt = stmt.where(_assignment_matches(filt))
    return stmt


def _assignment_matches(filt: CompanyFilter):
    """A process matches only when one of its own assignments matches agent and scope."""
    assignment = AgentAssignment
    conditions = [
        assignment.company_id == Company.id,
        assignment.investment_process_id == InvestmentCase.id,
    ]
    if filt.agent_id:
        conditions.append(assignment.agent_id == filt.agent_id)
    if filt.scope == "active":
        conditions.append(assignment.status.in_(ACTIVE_ASSIGNMENT))
    elif filt.scope == "paused":
        conditions.append(assignment.status == "paused")
    elif filt.scope == "past":
        conditions.append(assignment.status.in_(PAST_ASSIGNMENT))
    text_match = None
    if filt.q:
        like = f"%{filt.q}%"
        text_match = or_(
            Company.display_name.ilike(like),
            Company.legal_name.ilike(like),
            exists(
                select(assignment.id).where(
                    assignment.company_id == Company.id,
                    assignment.investment_process_id == InvestmentCase.id,
                    or_(assignment.title.ilike(like), assignment.objective.ilike(like)),
                    *([assignment.agent_id == filt.agent_id] if filt.agent_id else []),
                )
            ),
        )
    assignment_exists = exists(select(assignment.id).where(*conditions))
    if filt.q and not filt.agent_id and not filt.scope:
        return text_match
    if filt.q:
        return and_(assignment_exists, text_match)
    return assignment_exists
