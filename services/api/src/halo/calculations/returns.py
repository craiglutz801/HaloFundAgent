"""Gross company return math. These are not fund net returns and not forecasts."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from halo.calculations.errors import CalculationError

_OWNERSHIP = Decimal("0.000001")
_MONEY = Decimal("0.01")
_MOIC = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY, rounding=ROUND_HALF_UP)


def entry_ownership(entry_check: Decimal, post_money: Decimal) -> Decimal:
    if post_money <= 0:
        raise CalculationError("post-money must be positive")
    if entry_check < 0:
        raise CalculationError("entry check cannot be negative")
    if entry_check > post_money:
        raise CalculationError("entry check cannot exceed post-money")
    return (entry_check / post_money).quantize(_OWNERSHIP, rounding=ROUND_HALF_UP)


def apply_dilution(ownership: Decimal, modeled_dilution: Decimal) -> Decimal:
    if ownership < 0:
        raise CalculationError("ownership cannot be negative")
    if modeled_dilution < 0 or modeled_dilution >= 1:
        raise CalculationError("modeled dilution must be in [0, 1)")
    return (ownership * (Decimal(1) - modeled_dilution)).quantize(
        _OWNERSHIP, rounding=ROUND_HALF_UP
    )


def gross_proceeds(exit_equity_value: Decimal, ownership: Decimal) -> Decimal:
    if exit_equity_value < 0:
        raise CalculationError("exit equity value cannot be negative")
    if ownership < 0:
        raise CalculationError("ownership cannot be negative")
    return _money(exit_equity_value * ownership)


def gross_moic(proceeds: Decimal, invested: Decimal) -> Decimal:
    if invested <= 0:
        raise CalculationError("invested capital must be positive")
    if proceeds < 0:
        raise CalculationError("proceeds cannot be negative")
    return (proceeds / invested).quantize(_MOIC, rounding=ROUND_HALF_UP)


def gross_irr_or_unavailable(*, cash_flow_dates_present: bool) -> Decimal | None:
    """IRR is unavailable unless real cash-flow dates exist. This function does not invent one."""
    if not cash_flow_dates_present:
        return None
    raise CalculationError("dated IRR is not implemented for this policy version")
