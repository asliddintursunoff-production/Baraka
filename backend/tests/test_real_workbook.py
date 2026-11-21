"""A restaurant financial-model workbook (29 tabs: ledgers + reports + reference): the
sync never crashes, report tabs are never ingested, sentences never become counterparties."""

from datetime import timedelta

import pytest

from apps.ai.llm import AllModelsFailed
from apps.finance.models import Counterparty, Transaction
from apps.ingestion import sync as sync_mod
from apps.ingestion.mapping import heuristic_sheet, is_report_title
from apps.ingestion.models import DataIssue
from apps.ingestion.readers import FakeReader, SheetData, WorkbookData, set_reader_override
from apps.ingestion.sync import save_mapping, sync_business
from apps.integrations.models import DataSource
from apps.tenancy.context import tenant_context, today_for

pytestmark = pytest.mark.django_db
TABS = [
    "Bosh sahifa",
    "Qo'llanma",
    "Sozlamalar",
    "Smena",
    "Sotuv",
    "Kirim",
    "Kassa",
    "Hisoblash",
    "Ish haqi",
    "Hisobdan chiqarish",
    "Inventarizatsiya",
    "Spravochnik",
    "Kontragentlar",
    "Mahsulotlar",
    "Menyu",
    "Texkarta",
    "Yarim tayyor",
    "YT retsept",
    "Asosiy vositalar",
    "Foyda-zarar",
    "Pul oqimi",
    "Balans",
    "Kunlik hisobot",
    "Ombor hisoboti",
    "Menyu tahlili",
    "Reja-fakt",
    "Fin reja",
    "Tekshiruv",
    "Zaxira",
]
LONG = (
    "Spravochnik: pul hisoblari (yil boshidagi qoldiq bilan), kurslar, savdo kanallari va agregator "
    "komissiyalari, kerak bo'lsa yangi moddalar (har bir xarajat modda)"
)


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    async def busy(*a, **k):
        raise AllModelsFailed("tests never call Gemini")

    monkeypatch.setattr("apps.ai.llm.generate", busy)
    yield
    set_reader_override(None)


def _book(today):
    sheets = []
    for t in TABS:
        rows = [
            [t + " — hisobot"],
            [],
            ["Ko'rsatkich", "Tanlangan oy", "Yil boshidan"],
            ["Sof tushum", 0, 0],
        ]
        if t == "Kirim":
            rows = [["Kirim"], [], ["Sana", "Summa", "Izoh"]] + [
                [(today - timedelta(days=i)).strftime("%d.%m.%Y"), 1_500_000 + i * 1000, "savdo"]
                for i in range(30)
            ]
        if t == "Kontragentlar":
            rows = [
                ["Kontragent", "Telefon"],
                [LONG, ""],
                [LONG, ""],
                ["Agro Go'sht", "+998"],
                ["Agro Go'sht", "+998"],
                ["Jami", ""],
            ]
        if t == "Spravochnik":
            rows = [[LONG], ["Kontragent", "Turi"], [LONG, "x"], [LONG, "y"]]
        sheets.append(SheetData(t, rows))
    return WorkbookData("fm", "Restoran_FinModel_Shablon", "2026-11-21T10:00:00Z", sheets)


def test_report_tabs_are_ignored_and_listed_last():
    assert (
        is_report_title("Bosh sahifa")
        and is_report_title("Foyda-zarar")
        and is_report_title("Kunlik hisobot")
    )
    assert not any(
        is_report_title(t)
        for t in ("Kirim", "Sotuv", "Kassa", "Ish haqi", "Kontragentlar", "Chiqim", "NBU kredit")
    )


def test_financial_model_workbook_never_crashes(owner_client, demo, monkeypatch):
    today = today_for(demo)
    wb = _book(today)
    set_reader_override(FakeReader({"fm": wb}))
    with tenant_context(demo):
        src = DataSource.objects.create(
            business=demo, spreadsheet_id="fm", title=wb.name, kind="xlsx", confirmed=True
        )
        for s in wb.sheets:
            p = heuristic_sheet(s)
            if s.title == "Bosh sahifa":  # a careless confirm mapped a report tab as data
                p.kind = "transactions_mixed"
            save_mapping(demo, src, p)
    real_payroll = sync_mod.Ingestor.ingest_payroll

    def boom(self, sheet, mapping):
        raise ValueError("broken sheet")

    monkeypatch.setattr(sync_mod.Ingestor, "ingest_payroll", boom)
    with tenant_context(demo):
        from apps.ingestion.models import SheetMapping

        SheetMapping.objects.filter(source=src, sheet_title="Ish haqi").update(sheet_kind="payroll")
    s = sync_business(demo, trigger="confirm", force=True, progress=lambda t, p: None, first=True)
    monkeypatch.setattr(sync_mod.Ingestor, "ingest_payroll", real_payroll)
    assert not s.errors, s.errors
    with tenant_context(demo):
        names = set(Counterparty.objects.values_list("name", flat=True))
        assert LONG not in names and not any(len(n) > 80 for n in names)
        assert "Agro Go'sht" in names and "Jami" not in names
        assert Transaction.objects.filter(raw_row__sheet_title="Kirim").count() == 30
        assert not Transaction.objects.filter(raw_row__sheet_title="Bosh sahifa").exists()
        assert DataIssue.objects.filter(
            kind="sheet_failed", status="open"
        ).exists()  # broken sheet reported
        src.refresh_from_db()
        assert src.status == DataSource.Status.ACTIVE
    d = owner_client.post(f"/api/sources/{src.pk}/remap").json()
    kinds = [sh["kind"] for sh in d["sources"][0]["sheets"]]
    assert kinds[0] != "ignore" and kinds[-1] == "ignore"  # data tabs first in the review
