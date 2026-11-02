"""Runway is unavailable when burn or cash restriction is not known."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from halo.calculations.errors import CalculationError


def runway_months(
    *,
    cash: Decimal | None,
    monthly_burn: Decimal | None,
    cash_restriction_unknown: bool,
) -> Decimal | None:
    if cash_restriction_unknown:
        return None
    if cash is None or monthly_burn is None:
        return None
    if monthly_burn <= 0:
        return None
    if cash < 0:
        raise CalculationError("cash cannot be negative")
    return (cash / monthly_burn).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
