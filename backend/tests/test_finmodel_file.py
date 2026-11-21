"""Optional check against a real "Restoran FinModel" workbook (not in the repo):
FINMODEL_XLSX=/path/to/Restoran_FinModel_Namuna.xlsx pytest tests/test_finmodel_file.py -s"""

import os
from datetime import date
from decimal import Decimal

import pytest
from django.db.models import Q, Sum

from apps.ai.llm import AllModelsFailed
from apps.ai.tools import ToolContext, run_tool
from apps.finance.models import CashAccount, Obligation, Transaction
from apps.ingestion.mapping import heuristic_sheet
from apps.ingestion.readers import FakeReader, WorkbookData, set_reader_override, xlsx_sheets
from apps.ingestion.sync import save_mapping, sync_business
from apps.insights.forecasting import get_forecast
from apps.integrations.models import DataSource
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Business

PATH = os.environ.get("FINMODEL_XLSX", "")
pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(not os.path.isfile(PATH), reason="FINMODEL_XLSX not set"),
]


def test_real_finmodel_workbook(monkeypatch):
    async def busy(*a, **k):
        raise AllModelsFailed("no LLM in tests")

    monkeypatch.setattr("apps.ai.llm.generate", busy)
    sheets = xlsx_sheets(open(PATH, "rb").read())
    wb = WorkbookData("fm", os.path.basename(PATH), "2026-11-21T10:00:00Z", sheets)
    set_reader_override(FakeReader({"fm": wb}))
    b = Business.objects.create(name="FinModel", kind="restaurant")
    try:
        with tenant_context(b):
            src = DataSource.objects.create(
                business=b, spreadsheet_id="fm", title=wb.name, kind="xlsx", confirmed=True
            )
            props = [heuristic_sheet(s) for s in sheets]
            for p in props:
                save_mapping(b, src, p)
        print("\nkinds:", {p.title: p.kind for p in props if p.kind != "ignore"})
        s = sync_business(b, trigger="confirm", force=True, progress=lambda t, p: None, first=True)
        print("sync:", s.rows_added, "rows; errors:", s.errors, "issues:", s.issues)
        assert not s.errors
        with tenant_context(b):
            cash = CashAccount.objects.first() or CashAccount(
                opening_balance=0, as_of_date=date(2026, 1, 1)
            )
            f = Transaction.objects.filter(
                txn_date__gt=cash.as_of_date, txn_date__lte=date(2026, 10, 31)
            ).aggregate(
                i=Sum("amount", filter=Q(direction="in")),
                o=Sum("amount", filter=Q(direction="out")),
            )
            oct31 = cash.opening_balance + (f["i"] or 0) - (f["o"] or 0)
            print(
                f"opening {cash.opening_balance:,.0f} @ {cash.as_of_date}; cash 31-Oct {oct31:,.0f} (model 1,439,533,315)"
            )
            for o in Obligation.objects.filter(status="planned").order_by("due_date")[:16]:
                print("  planned:", o.due_date, o.title, f"{o.amount:,.0f}", o.priority)
        if not Transaction.unscoped.filter(business=b).exists():
            print("empty template: no transactions, nothing to forecast")
            return
        fc = get_forecast(b).result
        print(
            "forecast: vcr",
            fc.variable_cost_ratio,
            "weekday",
            [f"{x / 1_000_000:.1f}" for x in fc.weekday_revenue],
            "min",
            f"{fc.min_balance:,.0f}",
            fc.min_date,
            fc.verdict,
            "insufficient",
            fc.insufficient_data,
        )
        with tenant_context(b):
            ctx = ToolContext(b, None, "api")
            for name in ("get_cash_status", "get_upcoming_payments", "get_expenses"):
                a = run_tool(ctx, name, {}).get("answer") or {}
                print(f"[{name}] {a.get('headline')} | {str(a.get('reason'))[:220]}")
        if "Namuna" in PATH:  # the filled sample: its own report says 1 439 533 314,83 on 31-Oct
            assert abs(oct31 - Decimal("1439533314.83")) < Decimal("1000000")
    finally:
        set_reader_override(None)
