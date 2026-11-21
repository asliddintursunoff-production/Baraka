"""Q1 on the REAL Lazzat_Lavash_FastFood_2026.xlsx (openpyxl, data_only) — the user's acceptance numbers."""

from decimal import Decimal as D
from pathlib import Path

import pytest

from apps.ai.tools import ToolContext, run_tool
from apps.engine import channels as C
from apps.ingestion.readers import WorkbookData, xlsx_sheets
from apps.tenancy.context import tenant_context
from tests.test_finmodel_golden import connect, no_llm  # noqa: F401

pytestmark = pytest.mark.django_db
XLSX = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "finmodel"
    / "Lazzat_Lavash_FastFood_2026.xlsx"
)
Q = "Yandex va Uzum menga foydalimi yoki o'z dostavkamni kuchaytiraymi?"


@pytest.fixture(scope="module")
def sheets():
    if not XLSX.exists():
        pytest.skip("real workbook not present")
    return xlsx_sheets(XLSX.read_bytes())


def test_real_file_q1(sheets):
    b, src = connect(
        WorkbookData("lz", XLSX.name, "2026-11-21T10:00:00Z", sheets), "Lazzat Lavash (real)"
    )
    s = src.summary
    ch = s["details"]["channels"]
    assert ch["rows"] == 14406 and ch["channel_column"] == "Kanal"
    assert set(ch["months"]["2026-10-01"]) == {
        "Zal",
        "Olib ketish",
        "O'z dostavka",
        "Yandex Eats",
        "Uzum Tezkor",
    }
    assert (
        ch["commission_rate"]["Yandex Eats"] == "0.2"
        and ch["commission_rate"]["Uzum Tezkor"] == "0.18"
    )
    # computed engine (spec order counts) — within the spec's rounding
    e = C.compute(s, C.Params(orders={"Uzum": D(174), "Yandex": D(257), "O'z": D(189)}))
    keep = {c.name: c.keep100k for c in e.channels}
    assert (
        abs(keep["Uzum Tezkor"] - 49420) < 20
        and abs(keep["Yandex Eats"] - 48300) < 20
        and abs(keep["O'z dostavka"] - 43060) < 20
    )
    prof = {c.name: c.profit for c in e.channels}
    assert (
        abs(prof["Yandex Eats"] - 11_520_000) < 10_000
        and abs(prof["Uzum Tezkor"] - 8_560_000) < 10_000
        and abs(prof["O'z dostavka"] - 7_230_000) < 10_000
    )
    sc = {x.key: x.delta for x in e.scenarios}
    assert abs(sc["exit"] + 20_070_000) < 20_000 and abs(sc["shift"] - 990_000) < 10_000
    assert abs(sc["markup"] - 1_460_000) < 10_000 and abs(sc["both"] - 2_010_000) < 10_000
    assert (int(e.orders_now), int(e.orders_plan)) == (189, 318)
    assert abs(sum(e.receivables.values(), D(0)) - 33_300_000) < 50_000
    # the exact question -> the golden report with the spec's values (pinned on this file)
    with tenant_context(b):
        r = run_tool(ToolContext(b, 0, "chat", last_user_text=Q), "channel_economics", {})
    rep = r["ui_blocks"][0]
    data = {d["kanal"]: d["Sizga qoladi"] for d in rep["sections"][0]["chart"]["data"]}
    assert data == {
        "Uzum Tezkor": 49420,
        "Yandex Eats": 48300,
        "O'z dostavka (hozir)": 43060,
        "O'z dostavka (reja)": 49940,
    }
    assert (
        rep["kpis"][2]["value"] == "+2 010 000"
        and rep["kpis"][3]["value"] == "33 300 000"
        and rep.get("source")
    )
