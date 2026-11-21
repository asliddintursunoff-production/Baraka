"""Decimal <-> integer tiyin conversion. Money never passes through float."""

from __future__ import annotations

from decimal import ROUND_FLOOR, ROUND_HALF_EVEN, Decimal

TIYIN = Decimal(100)
CENT = Decimal("0.01")


def to_tiyin(amount: Decimal | int) -> int:
    if isinstance(amount, float):  # pragma: no cover - guarded by types
        raise TypeError("float is not allowed for money")
    value = amount if isinstance(amount, Decimal) else Decimal(amount)
    return int((value * TIYIN).to_integral_value(rounding=ROUND_HALF_EVEN))


def from_tiyin(tiyin: int) -> Decimal:
    return (Decimal(int(tiyin)) / TIYIN).quantize(CENT)


def floor_to_step(amount: Decimal, step: Decimal) -> Decimal:
    """8 815 000 -> 8 000 000 for step 1 000 000 (towards minus infinity)."""
    return ((amount / step).to_integral_value(rounding=ROUND_FLOOR) * step).quantize(CENT)
