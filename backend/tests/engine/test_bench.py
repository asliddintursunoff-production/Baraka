"""Spec §5.3 / §6: one `simulate` must take < 5 ms."""

import statistics
import time
from datetime import date
from decimal import Decimal

from apps.engine import Change, evaluate_purchase, forecast, simulate

from .golden import golden_input, history, mln


def _median_ms(fn, runs=200):
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    return statistics.median(times), max(sorted(times)[: int(runs * 0.95)])


def test_simulate_under_5ms():
    inp = golden_input(hist=history())
    base = forecast(inp, 90)
    changes = [
        Change(kind="revenue_pct", value=Decimal(-20)),
        Change(kind="new_staff", value=Decimal(2)),
        Change(kind="extra_expense", value=mln("25"), start_date=date(2027, 1, 12)),
        Change(kind="payment_delay", value=Decimal(15), counterparty="Agro Go'sht"),
    ]
    for ch in changes:
        p50, p95 = _median_ms(lambda ch=ch: simulate(base, inp, ch))
        assert p95 < 5, f"{ch.kind}: p50={p50:.3f} ms p95={p95:.3f} ms"


def test_forecast_and_purchase_are_fast():
    inp = golden_input()
    f50, _ = _median_ms(lambda: forecast(inp, 90), runs=50)
    base = forecast(inp, 90)
    p50, _ = _median_ms(lambda: evaluate_purchase(inp, mln("25"), base=base), runs=50)
    assert f50 < 25, f"forecast p50 {f50:.2f} ms"
    assert p50 < 25, f"evaluate_purchase p50 {p50:.2f} ms"
