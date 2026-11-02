"""Capacity released is an estimate until volume, adoption, and spend are verified."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from halo.calculations.errors import CalculationError


def estimated_capacity_hours(
    *,
    baseline_minutes: Decimal,
    future_minutes: Decimal,
    monthly_cases: Decimal,
) -> Decimal:
    if baseline_minutes < 0 or future_minutes < 0 or monthly_cases < 0:
        raise CalculationError("minutes and case volume cannot be negative")
    released = baseline_minutes - future_minutes
    if released < 0:
        raise CalculationError("future minutes cannot exceed the baseline")
    hours = (released * monthly_cases) / Decimal(60)
    return hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def classification_for_capacity() -> str:
    return "estimated"
