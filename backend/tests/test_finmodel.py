"""Restaurant financial-model workbooks: Kassa/Smena/Kirim/Spravochnik read as cash, accrual and
report tabs ignored, transfers skipped, fixed payments projected, financing never counted as sales."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from apps.ai.llm import AllModelsFailed
from apps.ai.tools import ToolContext, run_tool
from apps.finance.models import CashAccount, Obligation, Transaction
from apps.ingestion.mapping import heuristic_sheet
from apps.ingestion.readers import FakeReader, SheetData, WorkbookData, set_reader_override
from apps.ingestion.sync import save_mapping, sync_business
from apps.integrations.models import DataSource
from apps.tenancy.context import tenant_context, today_for
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db
TITLE: list[list[Any]] = [["Model"], ["izoh"], []]


def _wb(today: date) -> WorkbookData:
    d0 = (today - timedelta(days=95)).replace(day=1)
    kassa: list[list[Any]] = [
        *TITLE,
        [
            "",
            "Sana",
            "Hisob",
            "Turi",
            "Modda",
            "Kontragent",
            "Summa",
            "Izoh",
            "Valyuta",
            "Summa so'm (±)",
            "Faoliyat",
        ],
    ]
    kassa.append(
        [
            "",
            datetime.combine(d0, datetime.min.time()),
            "Bank",
            "Kirim",
            "Ta'sischi kiritmasi",
            "Sherik",
            500_000_000,
            "",
            "so'm",
            500_000_000,
            "Moliyaviy",
        ]
    )
    kassa.append(
        [
            "",
            datetime.combine(d0, datetime.min.time()),
            "Naqd",
            "O'tkazma",
            None,
            "",
            9_000_000,
            "",
            "so'm",
            -9_000_000,
            None,
        ]
    )
    kassa.append(
        [
            "",
            datetime.combine(d0 + timedelta(days=1), datetime.min.time()),
            "Bank",
            "Chiqim",
            "Asosiy vosita uchun to'lov",
            "Usta",
            100_000_000,
            "",
            "so'm",
            -100_000_000,
            "Investitsion",
        ]
    )
    for k in range(4):  # rent on the 3rd, payroll on the 5th, every month
        m = (d0 + timedelta(days=32 * k)).replace(day=1)
        if m > today:
            break
        kassa.append(
            [
                "",
                datetime.combine(m.replace(day=3), datetime.min.time()),
                "Bank",
                "Chiqim",
                "Hisoblangan xarajat to'lovi",
                "Ijara beruvchi",
                25_000_000,
                "",
                "so'm",
                -25_000_000,
                "Operatsion",
            ]
        )
        kassa.append(
            [
                "",
                datetime.combine(m.replace(day=5), datetime.min.time()),
                "Naqd",
                "Chiqim",
                "Ish haqi to'lovi",
                "Oshpaz",
                40_000_000,
                "",
                "so'm",
                -40_000_000,
                "Operatsion",
            ]
        )
    smena: list[list[Any]] = [
        *TITLE,
        [
            "",
            "Sana",
            "Cheklar soni",
            "Z-hisobot jami",
            "Naqd (POS)",
            "Terminal",
            "Click",
            "Payme",
            "To'lovlar jami",
        ],
    ]
    d = d0
    while d <= today - timedelta(days=1):
        smena.append(
            [
                "",
                datetime.combine(d, datetime.min.time()),
                50,
                6_000_000,
                2_000_000,
                3_000_000,
                500_000,
                500_000,
                6_000_000,
            ]
        )
        d += timedelta(days=1)
    kirim: list[list[Any]] = [
        *TITLE,
        [
            "",
            "Sana",
            "Mahsulot",
            "Miqdor",
            "Yetkazib beruvchi",
            "Darhol to'langan hisob",
            "To'lov (so'm)",
        ],
    ]
    kirim.append(
        [
            "",
            datetime.combine(today - timedelta(days=3), datetime.min.time()),
            "Kartoshka",
            10,
            "Bozor",
            "Naqd kassa",
            500_000,
        ]
    )
    kirim.append(
        [
            "",
            datetime.combine(today - timedelta(days=3), datetime.min.time()),
            "Go'sht",
            10,
            "Go'sht MChJ",
            None,
            4_000_000,
        ]
    )
    sprav: list[list[Any]] = [
        ["Spravochnik"],
        [],
        ["", "Sana", "USD kursi", "", "Hisob nomi", "Valyuta", "Boshl. qoldiq (valyutada)"],
        ["", d0, 12000, "", "Naqd kassa", "so'm", 10_000_000],
        ["", None, None, "", "Naqd USD", "USD", 1000],
    ]
    sotuv: list[list[Any]] = [
        *TITLE,
        ["", "Sana", "Taom", "Miqdor (porsiya)", "Narx", "Summa"],
        ["", d0, "Burger", 10, 45000, 450000],
    ]
    ish: list[list[Any]] = [
        *TITLE,
        ["", "Oy", "Xodim", "Oklad (so'm)", "JShDS", "Jami xarajat"],
        ["", d0, "Oshpaz", 7_000_000, 840_000, 7_840_000],
    ]
    sheets = [
        SheetData("Bosh sahifa", [["Hisobot"], ["Sof tushum", 1]]),
        SheetData("Smena", smena),
        SheetData("Sotuv", sotuv),
        SheetData("Kirim", kirim),
        SheetData("Kassa", kassa),
        SheetData("Ish haqi", ish),
        SheetData("Spravochnik", sprav),
    ]
    return WorkbookData("fm", "Restoran_FinModel", "2026-11-21T10:00:00Z", sheets)


def test_finmodel_reads_cash_and_projects_fixed_payments(monkeypatch):
    async def busy(*a, **k):
        raise AllModelsFailed("no LLM")

    monkeypatch.setattr("apps.ai.llm.generate", busy)
    b = Business.objects.create(name="Burger", kind="restaurant")
    today = today_for(b)
    wb = _wb(today)
    set_reader_override(FakeReader({"fm": wb}))
    try:
        kinds = {s.title: heuristic_sheet(s).kind for s in wb.sheets}
        assert kinds == {
            "Bosh sahifa": "ignore",
            "Smena": "finmodel_smena",
            "Sotuv": "ignore",
            "Kirim": "finmodel_purchases",
            "Kassa": "finmodel_kassa",
            "Ish haqi": "ignore",
            "Spravochnik": "finmodel_accounts",
        }
        with tenant_context(b):
            src = DataSource.objects.create(
                business=b, spreadsheet_id="fm", title="fm", kind="xlsx", confirmed=True
            )
            for s in wb.sheets:
                save_mapping(b, src, heuristic_sheet(s))
        summary = sync_business(
            b, trigger="confirm", force=True, progress=lambda t, p: None, first=True
        )
        assert not summary.errors
        with tenant_context(b):
            assert CashAccount.objects.get().opening_balance == Decimal(
                "22000000.00"
            )  # 10 mln + 1000 USD x 12 000
            assert not Transaction.objects.filter(note__icontains="o'tkazma").exists()
            assert Transaction.objects.filter(category="financing", direction="in").count() == 1
            assert Transaction.objects.filter(category="capex").count() == 1
            assert (
                Transaction.objects.filter(category="xom ashyo").count() == 1
            )  # only the row paid at once
            assert not Transaction.objects.filter(
                raw_row__sheet_title__in=["Sotuv", "Ish haqi"]
            ).exists()
            planned = {
                (o.category, o.due_date.day, o.amount)
                for o in Obligation.objects.filter(status="planned")
            }
            assert ("rent", 3, Decimal("25000000.00")) in planned and (
                "payroll",
                5,
                Decimal("40000000.00"),
            ) in planned
            ctx = ToolContext(b, None, "api")
            exp = run_tool(ctx, "get_expenses", {})
            assert exp["facts"]["income"] != "0.00" and exp["answer"]["headline"]
            up = run_tool(ctx, "get_upcoming_payments", {})
            assert up["facts"]["count"] >= 2
        from apps.insights.forecasting import get_forecast

        r = get_forecast(b).result
        assert (
            not r.insufficient_data and r.weekday_revenue[0] > 0
        )  # 6 mln/day sales, capital not counted
        assert max(r.weekday_revenue) < Decimal("7000000")
    finally:
        set_reader_override(None)
