"""Retention math that keeps logo and dollar definitions from collapsing into one number."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from halo.calculations.errors import CalculationError

_RATE = Decimal("0.0001")


def _rate(value: Decimal) -> Decimal:
    return value.quantize(_RATE, rounding=ROUND_HALF_UP)


def gross_revenue_retention(
    *,
    starting_arr: Decimal,
    contraction: Decimal,
    churn: Decimal,
) -> Decimal:
    """Dollar GRR excludes expansion and reactivation."""
    if starting_arr <= 0:
        raise CalculationError("starting ARR must be positive")
    if contraction < 0 or churn < 0:
        raise CalculationError("contraction and churn cannot be negative")
    retained = starting_arr - contraction - churn
    if retained < 0:
        raise CalculationError("retained revenue cannot be negative")
    return _rate(retained / starting_arr)


def net_revenue_retention(
    *,
    starting_arr: Decimal,
    contraction: Decimal,
    churn: Decimal,
    expansion: Decimal,
    reactivation: Decimal,
) -> Decimal:
    if starting_arr <= 0:
        raise CalculationError("starting ARR must be positive")
    for name, value in (
        ("contraction", contraction),
        ("churn", churn),
        ("expansion", expansion),
        ("reactivation", reactivation),
    ):
        if value < 0:
            raise CalculationError(f"{name} cannot be negative")
    ending = starting_arr - contraction - churn + expansion + reactivation
    if ending < 0:
        raise CalculationError("ending revenue cannot be negative")
    return _rate(ending / starting_arr)


def retention_definitions_conflict(
    *,
    stated_rate: Decimal | None,
    computed_rate: Decimal | None,
) -> bool:
    """Two populated rates that differ are a conflict, not an average."""
    if stated_rate is None or computed_rate is None:
        return False
    return stated_rate != computed_rate
