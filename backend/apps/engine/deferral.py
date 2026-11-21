"""Which non-critical payment to move, and by how many days, to avoid a shortage.

Used when the verdict is `risky` because the balance goes below zero only on days
without a critical payment. For each deferrable/discretionary payment dated on or before
the last negative day, find the smallest delay (1..MAX_DELAY_DAYS) after which no balance
is below zero and no critical day is hurt. The best suggestion is the smallest delay
(ties: the larger payment). If no single move fixes it, the move that helps most is
returned with resolves=False.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from .money import to_tiyin
from .types import BoolArray, Deferral, IntArray, PreparedObligation

MAX_DELAY_DAYS = 45


def suggest_deferrals(
    close: IntArray,
    critical_mask: BoolArray,
    obligations: tuple[PreparedObligation, ...],
    today: date,
) -> tuple[Deferral, ...]:
    negative = np.flatnonzero(close < 0)
    if negative.size == 0 or bool(np.any(close[critical_mask] < 0)):
        return ()
    last_negative = int(negative[-1])
    n = len(close)
    best: tuple[int, int, Deferral] | None = None  # (days, -amount, deferral)
    fallback: tuple[int, Deferral] | None = None  # (min balance after move, deferral)
    for p in obligations:
        if p.priority == "critical":
            continue
        i = max(0, (p.date - today).days)
        if i > last_negative:
            continue
        amount = to_tiyin(p.amount)
        for k in range(1, MAX_DELAY_DAYS + 1):
            j = i + k
            moved = close.copy()
            if j < n:
                moved[i:j] += amount
            else:
                moved[i:] += amount
            new_date = p.date + timedelta(days=k)
            low = int(moved.min())
            critical_ok = not bool(np.any(moved[critical_mask] < 0))
            if low >= 0 and critical_ok:
                cand = Deferral(obligation=p, days=k, new_date=new_date, resolves=True)
                key = (k, -amount)
                if best is None or key < best[:2]:
                    best = (k, -amount, cand)
                break
            if critical_ok and (fallback is None or low > fallback[0]):
                fallback = (low, Deferral(obligation=p, days=k, new_date=new_date, resolves=False))
    if best is not None:
        return (best[2],)
    return (fallback[1],) if fallback else ()
