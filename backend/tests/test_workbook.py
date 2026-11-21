"""Shared reader golden inventory (Namuna), no row cap, DuckDB load and wb_sql safety."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from apps.ai.cfo_router import _AMOUNT, _BUY
from apps.workbook import analyst, reader, store
from tests.test_finmodel_golden import load

GOLDEN = {
    "Smena": ("journal_cash", "4 / B", 304),
    "Sotuv": ("journal_sales", "4 / B", 2080),
    "Kirim": ("journal_purchase", "4 / B", 1535),
    "Kassa": ("journal_cash", "4 / B", 629),
    "Hisoblash": ("journal_accrual", "4 / B", 20),
    "Ish haqi": ("journal_accrual", "4 / B", 110),
    "Hisobdan chiqarish": ("journal_writeoff", "4 / B", 42),
    "Inventarizatsiya": ("journal_inventory", "4 / B", 70),
    "Kontragentlar": ("master_data", "4 / B", 28),
    "Mahsulotlar": ("master_data", "4 / B", 25),
    "Menyu": ("master_data", "4 / B", 11),
    "Texkarta": ("master_data", "4 / B", 61),
    "Asosiy vositalar": ("master_data", "4 / B", 6),
}


def test_golden_inventory() -> None:
    wb = load("namuna")
    model = reader.read_sheets(wb.sheets, wb.name)
    inv = {r["sheet"]: r for r in reader.inventory(model)}
    assert len(inv) == len(wb.sheets) == 29
    assert model.template == "Restoran moliyaviy modeli"
    for sheet, (role, header, rows) in GOLDEN.items():
        assert (inv[sheet]["role"], inv[sheet]["header"], inv[sheet]["rows"]) == (
            role,
            header,
            rows,
        ), sheet
    assert inv["Tekshiruv"]["role"] == "ignore"
    assert inv["Foyda-zarar"]["role"] == "report"


def test_no_row_cap() -> None:
    rows: list[list[Any]] = [["Jadval"], [], ["Sana", "Summa", "Izoh"]]
    rows += [[date(2026, 1, 1), i, "x"] for i in range(12_000)]
    t = reader.detect_sheet("Katta", rows)
    assert len(t.rows) == 12_000 and t.header_row == 3


def test_sql_safety() -> None:
    for bad in (
        "insert into kassa values (1)",
        "select * from read_csv('/etc/passwd')",
        "select 1; select 2",
        "attach 'x.db'",
        "copy kassa to 'x.csv'",
        "with a as (select 1) select * from read_parquet('x')",
    ):
        with pytest.raises(store.SqlRejected):
            store.check_sql(bad)
    assert store.check_sql("SELECT sum(x) FROM t;") == "SELECT sum(x) FROM t"


def test_duckdb_load(tmp_path: Any, monkeypatch: Any) -> None:
    import openpyxl

    monkeypatch.setattr(store, "ROOT", tmp_path)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Kassa"
    ws.append(["Kassa"])
    ws.append([])
    ws.append(["Sana", "Turi", "Summa"])
    for i in range(1, 31):
        ws.append([date(2026, 10, i), "Kirim", 1000 * i])
    import io

    buf = io.BytesIO()
    wb.save(buf)
    cat = store.build(1, buf.getvalue(), "t.xlsx")
    assert cat["tables"][0]["rows"] == 30
    r = store.run_sql(1, cat["id"], "SELECT sum(summa) AS s FROM kassa")
    assert r["rows"][0][0] == 465000
    assert "kassa" in analyst.catalog_text(cat)
    assert analyst.calculate("1439533314.83 - 1000000000") == "439533314.8300"


def test_buy_route() -> None:
    m = _BUY.search("yana bitta fritur olsam qancha pul ketadi")
    assert m and m.group(1) == "fritur"
    assert _AMOUNT.search("fritur 15 mln bo'lsa")
    assert analyst.is_deep(analyst.SUMMARY_Q) and not analyst.is_deep("Eng ko'p sotilgan taom?")
