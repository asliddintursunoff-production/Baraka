"""Lazzat Lavash (fast food): month-end cash equals the file's Pul oqimi; 0 reconciliation mismatches."""

from decimal import Decimal as D

import pytest

from apps.insights.forecasting import get_forecast
from apps.tenancy.context import tenant_context
from tests.test_finmodel_golden import connect, load, no_llm  # noqa: F401

pytestmark = pytest.mark.django_db
GOLDEN = {
    "01": 66.3,
    "02": 58.9,
    "03": 58.3,
    "04": 54.8,
    "05": 46.7,
    "06": 56.6,
    "07": 53.0,
    "08": 62.4,
    "09": 52.6,
    "10": 59.3,
}


def test_lazzat_cash_and_gate() -> None:
    b, src = connect(load("lazzat"), "Lazzat Lavash")
    s = src.summary
    for mm, v in GOLDEN.items():
        assert round(float(s["months"][f"2026-{mm}-01"]["cash_end"]) / 1e6, 1) == v, mm
    assert not [r for r in s["recon"] if not r.get("ok")]
    assert s["months"]["2026-10-01"]["revenue"] == "156187000.00"
    assert s["journals"]["checks"]["2026-10-01"] == "1931.00"
    with tenant_context(b):
        from apps.finance.models import Transaction

        f = get_forecast(b).result
        assert abs(f.close_on(f.today) - D("71121525.62")) < 1
        assert not Transaction.objects.filter(txn_date__year=2025).exists()
