"""P0 forecast golden, P1 growth plan golden, P2 investment advisor (synthetic + namuna)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from apps.ai.tools import ToolContext, run_tool
from apps.engine.growth import evaluate_investment
from apps.insights.forecasting import get_forecast
from apps.tenancy.context import tenant_context
from tests.test_finmodel_golden import connect, load, no_llm  # noqa: F401

pytestmark = pytest.mark.django_db


def test_investment_synthetic() -> None:
    r = evaluate_investment(D(30_000_000), D(40), D(14742), extra_opex=D(1_500_000))
    assert [round(x / 1_000_000, 2) for x in r.monthly[:3]] == [D("7.35"), D("11.77"), D("16.19")]
    assert r.payback_months == D("2.7")


@pytest.fixture
def namuna():
    return connect(load("namuna"))


def test_namuna_forecast_golden(namuna) -> None:
    b, _ = namuna
    with tenant_context(b):
        f = get_forecast(b).result
        assert f.today == date(2026, 10, 31)
        dec31 = f.close_on(date(2026, 12, 31))
        assert D(1_550_000_000) <= dec31 <= D(1_620_000_000), dec31
        assert min(f.close_on(f.today + timedelta(days=i)) for i in range(90)) >= D(1_300_000_000)
        assert f.close_on(date(2027, 2, 15)) > 0


def test_namuna_growth_and_fritur(namuna) -> None:
    b, _ = namuna
    with tenant_context(b):
        ctx = ToolContext(b, 0, "chat")
        g = run_tool(ctx, "growth_plan", {})
        assert g["facts"]["verdict"] in ("E'TIBOR", "BARQAROR")
        assert "Sezar salat" in g["md"] and "Gazli ichimlik" in g["md"] and "Shanba" in g["md"]
        assert g["facts"]["net_profit"] == "95,8 mln"
        inv = run_tool(ctx, "evaluate_investment", {"price": 30_000_000, "item": "fritur"})
        assert inv["facts"]["verdict"] in ("OLING", "KUTING")
        assert "### Foyda" in inv["md"] and "### Kassa" in inv["md"]
