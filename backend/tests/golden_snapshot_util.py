"""Q1–Q4 frozen payloads: build the comparable part of each golden answer on the Lazzat fixture."""

import json
from pathlib import Path
from typing import Any

from apps.ai.tools import ToolContext, run_tool
from apps.tenancy.context import tenant_context

SNAP = Path(__file__).resolve().parent / "golden_snapshots"
CASES = {
    "Q1": (
        "channel_economics",
        {},
        "Yandex va Uzum menga foydalimi yoki o'z dostavkamni kuchaytiraymi? Qaysi biri ko'proq foyda olib keladi?",
    ),
    "Q2": (
        "hire_payback",
        {"role": "ofitsiant"},
        "Yana bitta ofitsiant olsam, o'zini necha oyda oqlaydi?",
    ),
    "Q3": (
        "equipment_investment",
        {"equipment": "lavash apparati", "price": 25_000_000},
        "25 millionga lavash apparat olmoqchiman — bu investitsiya bo'ladimi yoki zarariga ishlaydimi?",
    ),
    "Q4": (
        "revenue_growth_plan",
        {},
        "Korxona daromadini 10 foizga qisqa muddatda oshirish uchun strategiya tuzib ber.",
    ),
}


def payload(business: Any, q: str) -> dict[str, Any]:
    tool, args, text = CASES[q]
    with tenant_context(business):
        r = run_tool(ToolContext(business, 0, "chat", last_user_text=text), tool, dict(args))
    keep = {
        k: r.get(k) for k in ("md", "say", "speech_segments", "speech_short", "ui_blocks", "facts")
    }
    return json.loads(json.dumps(keep, ensure_ascii=False, default=str))
