"""P0 golden tests on Restoran_FinModel_Namuna.xlsx (fixture: the reader's own output of the file,
gzip JSON) and the empty Shablon. Numbers must match the workbook's own reports."""

import gzip
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from apps.ai.llm import AllModelsFailed
from apps.ingestion.mapping import heuristic_sheet
from apps.ingestion.readers import FakeReader, SheetData, WorkbookData, set_reader_override
from apps.ingestion.sync import save_mapping, sync_business
from apps.integrations.models import DataSource
from apps.tenancy.context import tenant_context
from apps.tenancy.gate import data_status
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db
FIX = Path(__file__).resolve().parent.parent / "fixtures" / "finmodel"
M = Decimal(1_000_000)


def _decode(v):
    if isinstance(v, dict) and "__dt__" in v:
        return datetime.fromisoformat(v["__dt__"])
    if isinstance(v, dict) and "__d__" in v:
        return date.fromisoformat(v["__d__"])
    return v


def load(name: str) -> WorkbookData:
    with gzip.open(FIX / f"{name}.json.gz", "rt", encoding="utf-8") as f:
        raw = json.load(f)
    sheets = [
        SheetData(s["title"], [[_decode(c) for c in r] for r in s["rows"]]) for s in raw["sheets"]
    ]
    return WorkbookData("fm", raw["name"], "2026-11-21T10:00:00Z", sheets)


def connect(wb: WorkbookData, name: str = "Namuna Burger") -> tuple[Business, DataSource]:
    set_reader_override(FakeReader({"fm": wb}))
    b = Business.objects.create(name=name, kind="restaurant")
    with tenant_context(b):
        src = DataSource.objects.create(
            business=b, spreadsheet_id="fm", title=wb.name, kind="xlsx", confirmed=True
        )
        for s in wb.sheets:
            p = heuristic_sheet(s)
            assert p is not None
            save_mapping(b, src, p)
    sync_business(b, trigger="confirm", force=True, progress=lambda t, p: None, first=True)
    src.refresh_from_db()
    b.refresh_from_db()
    return b, src


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    async def busy(*a, **k):
        raise AllModelsFailed("no LLM in tests")

    monkeypatch.setattr("apps.ai.llm.generate", busy)
    yield
    set_reader_override(None)


@pytest.fixture
def namuna():
    return connect(load("namuna"))


def mln(x) -> Decimal:
    return (Decimal(x) / M).quantize(Decimal("0.1"))


def test_namuna_matches_the_workbooks_own_reports(namuna):
    b, src = namuna
    s = src.summary
    mo = s["months"]
    assert [mln(mo[m]["cash_end"]) for m in ("2026-08-01", "2026-09-01", "2026-10-01")] == [
        Decimal("1321.5"),
        Decimal("1363.3"),
        Decimal("1439.5"),
    ]
    assert abs(Decimal(mo["2026-10-01"]["cash_end"]) - Decimal("1439533314.83")) < 1  # to the so'm
    oct_ = mo["2026-10-01"]
    assert mln(oct_["revenue"]) == Decimal("445.0")
    assert mln(oct_["payroll_accrued"]) == Decimal("70.2") and mln(oct_["payroll_paid"]) == Decimal(
        "63.4"
    )
    assert mln(oct_["transfers"]) == Decimal("152.0")
    assert mln(oct_["supplier_payments"]) == Decimal("162.2")
    assert mln(oct_["utilities"]) == Decimal("8.7")
    loan = s["loan"]
    assert mln(loan["balance"]) == Decimal("260.0") and mln(loan["principal_monthly"]) == Decimal(
        "10.0"
    )
    assert (
        mln(oct_["loan_interest"]) == Decimal("5.4")
        and loan["rate_pct"] == "24"
        and loan["term_months"] == 36
        and loan["grace_months"] == 6
    )
    bal = {x["name"]: mln(x["balance"]) for x in s["balances"]}
    assert bal["Yandex Eats"] == Decimal("-47.9") and bal["Uzum Tezkor"] == Decimal("-30.2")
    assert s["last_date"] == "2026-10-31"
    assert s["recon"] and all(r["ok"] for r in s["recon"]), [r for r in s["recon"] if not r["ok"]]
    q = b.data_quality
    assert q["status"] == "ok" and not q["flags"], q["flags"]
    assert q["last_date"] == "2026-10-31" and q["stale"] and q["missing_from"] == "2026-11-01"
    assert data_status(b) == "ok"


def test_forecast_starts_at_the_last_actual_day_and_projects_fixed_payments(namuna):
    from apps.finance.models import Obligation
    from apps.insights.forecasting import get_forecast

    b, _ = namuna
    f = get_forecast(b).result
    assert f.today == date(2026, 10, 31)
    assert abs(f.close_on(f.today) - Decimal("1439533314.83")) < 1
    assert f.min_balance > 0 and f.verdict == "yes"
    with tenant_context(b):
        nov = {
            o.category: o.amount
            for o in Obligation.objects.filter(due_date__year=2026, due_date__month=11)
        }
    assert {"rent", "payroll", "loan", "tax", "kommunal"} <= set(
        nov
    )  # November's estimates are in the forecast
    assert mln(nov["loan"]) == Decimal("15.2")  # 10 principal + 260 x 24 % / 12 = 5.2 interest
    assert mln(nov["payroll"]) < Decimal("80")  # cash payments, never accrual totals


def test_every_surface_reports_the_same_hardest_day(namuna, client):
    from django.contrib.auth import get_user_model

    from apps.ai.live_api import live_context
    from apps.ai.tools import ToolContext, run_tool
    from apps.insights.forecasting import get_forecast
    from apps.tenancy.models import Membership

    b, _ = namuna
    u = get_user_model().objects.create_user("o@x.uz", "o@x.uz", "parol-12345")
    Membership.objects.create(user=u, business=b)
    client.force_login(u)
    f = get_forecast(b).result
    day, amount = f.min_date, f.min_balance
    dash = client.get("/api/dashboard").json()
    fc = client.get("/api/forecast?days=120").json()
    with tenant_context(b):
        tool = run_tool(ToolContext(b, None, "api"), "get_cash_status", {})
    with tenant_context(b):
        ctx_text = "\n".join(live_context(b))
    from apps.ai import uz_format as uz

    d_txt, a_txt = uz.format_date(day), uz.format_mln(amount)
    assert tool["facts"]["lowest_date"] == day.isoformat()
    assert d_txt in json.dumps(dash, ensure_ascii=False) and d_txt in json.dumps(
        fc, ensure_ascii=False
    )
    assert d_txt in ctx_text and a_txt in ctx_text


def test_empty_template_is_no_data_with_no_numbers(client):
    b, _ = connect(load("shablon"), "Bo'sh shablon")
    assert data_status(b) == "no_data"
    from django.contrib.auth import get_user_model

    from apps.tenancy.models import Membership

    u = get_user_model().objects.create_user("e@x.uz", "e@x.uz", "parol-12345")
    Membership.objects.create(user=u, business=b)
    client.force_login(u)
    assert client.get("/api/dashboard").status_code == 409
    assert client.get("/api/me").json()["data_status"] == "no_data"


def test_unreconciled_data_blocks_forecasts_and_advice(namuna, client):
    from django.contrib.auth import get_user_model

    from apps.tenancy.models import Membership

    b, src = namuna
    summ = src.summary
    summ["recon"][0] = summ["recon"][0] | {"ok": False, "computed": "1.00"}
    DataSource.unscoped.filter(pk=src.pk).update(summary=summ)
    from apps.ingestion.quality import assess

    assess(b)
    b.refresh_from_db()
    assert data_status(b) == "needs_review"
    u = get_user_model().objects.create_user("r@x.uz", "r@x.uz", "parol-12345")
    Membership.objects.create(user=u, business=b)
    client.force_login(u)
    r = client.get("/api/dashboard")
    assert r.status_code == 409 and r.json()["code"] == "needs_review" and r.json()["recon"]
    # chat is never gated (owner decision 2026-11-22): data issues are a badge, not a refusal
    r = client.post(
        "/api/chat/messages",
        data=json.dumps({"text": "Hozir qancha pulim bor?"}),
        content_type="application/json",
    )
    assert r.status_code == 200


def test_backtest_sep_and_oct_within_5_percent(namuna):
    b, src = namuna
    bt = b.data_quality.get("backtest")
    assert bt and [r["target"] for r in bt][-2:] == ["2026-09-30", "2026-10-31"], bt
    for r in bt:
        assert r["ok"] and Decimal(r["error_pct"]) <= 5, r
    rec = {(r["month"], r["metric"]): r for r in src.summary["recon"]}
    print("\nRECON")
    for m in range(1, 11):
        key = f"2026-{m:02d}-01"
        cells = []
        for metric in ("cash_end", "revenue", "payroll_accrued"):
            r = rec.get((key, metric))
            cells.append(
                f"{metric}={mln(r['computed'])}/{mln(r['reported'])}/{'OK' if r['ok'] else 'XX'}"
                if r
                else f"{metric}=-"
            )
        print(key, " ".join(cells))
    print(
        "BACKTEST",
        [
            (
                r["as_of"],
                r["target"],
                str(mln(r["predicted"])),
                str(mln(r["actual"])),
                r["error_pct"],
            )
            for r in bt
        ],
    )
