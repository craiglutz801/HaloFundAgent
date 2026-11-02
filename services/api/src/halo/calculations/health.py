"""Portfolio health. Unknown wins when a required observation is missing or stale."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class DefinitionView:
    slug: str
    required: bool
    freshness_limit_days: int


@dataclass(frozen=True)
class ObservationView:
    period_end: datetime
    value: Decimal | None
    completeness: str
    observed_at: datetime | None


def evaluate_health(
    definitions: list[DefinitionView],
    observations_by_slug: dict[str, list[ObservationView]],
    as_of: datetime,
) -> tuple[str, list[str]]:
    missing: list[str] = []
    for definition in definitions:
        if not definition.required:
            continue
        series = observations_by_slug.get(definition.slug, [])
        current = max(series, key=lambda item: item.period_end, default=None)
        if (
            current is None
            or current.completeness != "complete"
            or current.value is None
            or current.observed_at is None
            or as_of - current.observed_at > timedelta(days=definition.freshness_limit_days)
        ):
            missing.append(definition.slug)
    if missing:
        return "unknown", missing
    return "on_plan", []
