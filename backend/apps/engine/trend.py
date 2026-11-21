"""trend_watch: a weekly metric moving the wrong way for N+ consecutive weeks (pure)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

MIN_WEEKS = 3
MIN_CHANGE = Decimal("0.05")  # ignore streaks that move less than 5 % in total


@dataclass(frozen=True)
class Trend:
    metric: str
    bad: str  # "down" | "up": the wrong direction for this metric
    weeks: int  # consecutive week-over-week moves the wrong way
    start: date  # the week the streak started from
    end: date  # the last complete week
    first: Decimal
    last: Decimal
    change_pct: Decimal  # signed, last vs first


def trailing_streak(
    metric: str, points: Sequence[tuple[date, Decimal]], bad: str, min_weeks: int = MIN_WEEKS
) -> Trend | None:
    """The streak ending at the last point, if it has >= min_weeks wrong-way moves."""
    n = 0
    for i in range(len(points) - 1, 0, -1):
        prev, cur = points[i - 1][1], points[i][1]
        if (cur < prev) if bad == "down" else (cur > prev):
            n += 1
        else:
            break
    if n < min_weeks:
        return None
    first, last = points[-1 - n][1], points[-1][1]
    change = (last - first) / abs(first) if first else Decimal(0)
    if abs(change) < MIN_CHANGE:
        return None
    return Trend(
        metric,
        bad,
        n,
        points[-1 - n][0],
        points[-1][0],
        first,
        last,
        change.quantize(Decimal("0.0001")),
    )


def trend_watch(
    series: Mapping[str, Sequence[tuple[date, Decimal]]], bad: Mapping[str, str]
) -> list[Trend]:
    out = []
    for metric, points in series.items():
        t = trailing_streak(metric, points, bad[metric])
        if t is not None:
            out.append(t)
    return out
