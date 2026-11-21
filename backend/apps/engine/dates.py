"""Calendar helpers (pure)."""

from __future__ import annotations

import calendar
from datetime import date


def add_months(d: date, months: int) -> date:
    """21-Nov + 1 -> 21-Dec; 31-Jan + 1 -> 28/29-Feb (clamped to month end)."""
    m = d.month - 1 + months
    year, month = d.year + m // 12, m % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def on_day_of_month(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def in_period(d: date, period: dict[str, str] | None) -> bool:
    """Period matching for rules.

    {"from": "2027-03-14", "to": "2027-03-21"}  absolute dates (inclusive)
    {"from": "03-14", "to": "03-21"}            every year (may wrap the new year)
    None / {}                                   always
    """
    if not period:
        return True
    start, end = period.get("from", ""), period.get("to", "")
    if len(start) == 10 and len(end) == 10:
        return date.fromisoformat(start) <= d <= date.fromisoformat(end)
    if len(start) == 5 and len(end) == 5:
        key = d.strftime("%m-%d")
        return start <= key <= end if start <= end else key >= start or key <= end
    raise ValueError(f"bad period: {period!r}")
