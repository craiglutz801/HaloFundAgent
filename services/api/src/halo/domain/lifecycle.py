"""Company-centered lifecycle. A phase belongs to a process, not to an agent."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

PHASES = (
    "sourcing",
    "screening",
    "partner_review",
    "due_diligence",
    "investment_committee",
    "term_sheet",
    "negotiation_closing",
)
PHASE_LABELS = {
    "sourcing": "Sourcing",
    "screening": "Screening",
    "partner_review": "Deep dive / Partner review",
    "due_diligence": "Due diligence",
    "investment_committee": "Investment Committee",
    "term_sheet": "Term sheet",
    "negotiation_closing": "Negotiation / Closing",
    "unknown": "Phase unknown",
}
OUTCOMES = ("open", "passed", "portfolio")
ASSIGNMENT_STATUSES = (
    "queued",
    "active",
    "waiting_for_input",
    "blocked",
    "paused",
    "completed",
    "cancelled",
)
ACTIVE_ASSIGNMENT = ("queued", "active", "waiting_for_input", "blocked")
PAST_ASSIGNMENT = ("completed", "cancelled")
SCOPES = ("active", "paused", "past", "all")

# Legacy company.stage values projected from a process, so the existing stage guard still applies.
LEGACY_STAGE = {
    "sourcing": "discovered",
    "screening": "first_look",
    "partner_review": "partner_review",
    "due_diligence": "diligence",
    "investment_committee": "ic_review",
    "term_sheet": "term_sheet",
    "negotiation_closing": "closing",
    "unknown": "discovered",
}


def phase_label(phase: str) -> str:
    return PHASE_LABELS.get(phase, phase.replace("_", " "))


def from_case_status(status: str) -> tuple[str, str, bool]:
    """Map a stored case status onto phase, outcome, and hold. Unknown phase stays unknown."""
    if status == "owned":
        return "negotiation_closing", "portfolio", False
    if status == "passed":
        return "unknown", "passed", False
    if status == "paused":
        return "unknown", "open", True
    phase = {
        "discovered": "sourcing",
        "first_look": "screening",
        "diligence": "due_diligence",
        "ic_review": "investment_committee",
        "closing": "negotiation_closing",
        "term_sheet": "term_sheet",
        "partner_review": "partner_review",
    }.get(status, "unknown")
    return phase, "open", False


def legacy_stage(phase: str, outcome: str, on_hold: bool) -> str:
    if outcome == "portfolio":
        return "owned"
    if outcome == "passed":
        return "passed"
    if on_hold:
        return "paused"
    return LEGACY_STAGE.get(phase, "discovered")


def assignment_status_for_run(run_status: str) -> str:
    if run_status == "running":
        return "active"
    if run_status in {"reviewed", "succeeded"}:
        return "completed"
    if run_status == "queued":
        return "queued"
    if run_status == "failed":
        return "blocked"
    return "active"


@dataclass(frozen=True)
class CompanyFilter:
    q: str | None = None
    agent_id: str | None = None
    phase: str | None = None
    outcome: str | None = None
    scope: str | None = None
    monitor: bool | None = None
    company_id: UUID | None = None
    funnel: bool = True

    def applied(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        if self.q:
            payload["q"] = self.q
        if self.agent_id:
            payload["agent_ids"] = [self.agent_id]
        if self.phase:
            payload["phase"] = self.phase
        if self.outcome:
            payload["outcome"] = self.outcome
        elif self.funnel:
            payload["outcome"] = "open"
        if self.scope:
            payload["assignment_scope"] = self.scope
        if self.monitor is not None:
            payload["monitor"] = self.monitor
        if self.company_id is not None:
            payload["company_ids"] = [str(self.company_id)]
        return payload


def parse_filter(
    *,
    q: str | None = None,
    agent: str | None = None,
    phase: str | None = None,
    outcome: str | None = None,
    scope: str | None = None,
    monitor: str | None = None,
    company: str | None = None,
    funnel: bool = True,
) -> CompanyFilter:
    from halo.errors import HaloError

    def blank(value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    agent_id = blank(agent)
    phase_key = blank(phase)
    outcome_key = blank(outcome)
    scope_key = blank(scope)
    company_key = blank(company)
    if phase_key is not None and phase_key not in PHASES:
        raise HaloError(422, "INVALID_FILTER", "Phase filter is not one of the seven phases.")
    if outcome_key is not None and outcome_key not in (*OUTCOMES, "all"):
        raise HaloError(422, "INVALID_FILTER", "Outcome filter is not recognized.")
    if scope_key is not None and scope_key not in SCOPES:
        raise HaloError(422, "INVALID_FILTER", "Assignment scope is not recognized.")
    if agent_id is not None and agent_id not in {
        "gm",
        "scout",
        "ainge",
        "xavier",
        "mutombo",
        "stockton",
        "sloan",
        "trainer",
        "scorekeeper",
    }:
        raise HaloError(422, "INVALID_FILTER", "Agent filter is not a known specialist.")
    monitor_flag = None
    if monitor is not None and monitor != "":
        if monitor not in {"true", "false"}:
            raise HaloError(422, "INVALID_FILTER", "Monitor filter must be true or false.")
        monitor_flag = monitor == "true"
    company_id = None
    if company_key is not None:
        try:
            company_id = UUID(company_key)
        except ValueError as exc:
            raise HaloError(422, "INVALID_FILTER", "Company filter is not an id.") from exc
    use_funnel = funnel and (outcome_key is None)
    if outcome_key == "all":
        outcome_key = None
        use_funnel = False
    if outcome_key in {"passed", "portfolio"}:
        use_funnel = False
    return CompanyFilter(
        q=blank(q),
        agent_id=agent_id,
        phase=phase_key,
        outcome=outcome_key,
        scope=scope_key,
        monitor=monitor_flag,
        company_id=company_id,
        funnel=use_funnel,
    )
