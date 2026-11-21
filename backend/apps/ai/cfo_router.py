"""Question -> CFO modules (D1), deterministic, no LLM.

The routed tools run before the model is called: their cards show at once, their facts and
ready markdown go to the model, and if the model fails the answer is built from them.
Product and dish names from the workbook are matched in the text ("unga", "kartoshkaning").
"""

from __future__ import annotations

import re
from typing import Any

from apps.integrations.models import DataSource

from .detail_tools import find_names

_APOS = re.compile(r"[‘’ʻʼ`]")
Routes = list[tuple[str, dict[str, Any]]]
REVIEW: Routes = [
    ("kpi_scorecard", {}),
    ("cash_sources", {}),
    ("net_position", {}),
    ("plan_vs_actual", {}),
    ("break_even", {}),
    ("debt_schedule", {}),
]
_TABLE: tuple[tuple[str, Routes], ...] = (
    (
        r"biznesim\s+qanday|umumiy\s+holat|moliyaviy\s+(holat|tahlil)|tahlil\s+qil|baho\s+ber|ahvol|hisobot\s+ber",
        REVIEW,
    ),
    (r"zararsiz|break.?even|nechta\s+chek|minimal\s+savdo", [("break_even", {})]),
    (
        r"(savdo|tushum)\w*\s+.*(tushsa|kamaysa|pasaysa)|stress|chidaydi|inqiroz",
        [("stress_test", {}), ("break_even", {})],
    ),
    (r"pul\w*\s+qayerdan|qayerdan\s+kel|pul\s+manba|ishlab\s+top", [("cash_sources", {})]),
    (
        r"sof\s+pozitsiya|debitor|kreditor|kimga\s+qarz|qarzlarim|majburiyat",
        [("net_position", {}), ("debt_schedule", {})],
    ),
    (r"kredit|bank\s+qarz", [("debt_schedule", {})]),
    (r"\bkpi\b|ko'rsatkich|food\s*cost|marja|rentabel", [("kpi_scorecard", {})]),
    (r"reja.?fakt|rejadan|rejaga\s+nisbatan|reja\s+bajar", [("plan_vs_actual", {})]),
    (
        r"o'rtacha\s+chek|cheklar\s+soni|hafta\s+kun|kanal|agregator|(tushum|savdo)\w*\s+nega|nega\s+.*(tushum|savdo)",
        [("driver_decomposition", {})],
    ),
    (r"trend|haftama|ketma.?ket", [("trend_watch", {})]),
    (r"isrof|kamomad|hisobdan\s+chiqar|buzil|o'g'ri|yo'qot", [("losses", {})]),
    (r"xodim|ish\s+haqi|maosh|ishchi|oshpaz|ofitsiant", [("staff_costs", {})]),
    (r"ombor|zaxira|buyurtma", [("stock_status", {})]),
    (r"asosiy\s+vosita|amortizatsiya", [("fixed_assets", {})]),
    (r"menyu|taom|retsept|porsiya|tannarx", [("menu_analysis", {})]),
    (r"mahsulot|masalliq|ingredient|bozor|xom\s*ashyo", [("product_costs", {})]),
    (r"xarajat|harajat|chiqim", [("get_expenses", {}), ("product_costs", {})]),
)
ROUTES = [(re.compile(p, re.IGNORECASE), tools) for p, tools in _TABLE]
MAX_TOOLS = 6


def route(text: str) -> list[tuple[str, dict[str, Any]]]:
    """Inside the tenant context. Empty when the workbook has no reports or item details."""
    src = DataSource.objects.exclude(summary={}).first()
    summary = (src.summary or {}) if src else {}
    details = summary.get("details") or {}
    if not details and not (summary.get("reports") or {}).get("pl"):
        return []
    t = _APOS.sub("'", text).lower()
    out: list[tuple[str, dict[str, Any]]] = []
    for name in find_names(t, list(details.get("purchases") or {}))[:2]:
        out.append(("product_costs", {"product": name}))
    for name in find_names(t, list(details.get("menu") or {}))[:2]:
        out.append(("menu_analysis", {"dish": name}))
    named = {n for n, _ in out}
    for pattern, tools in ROUTES:
        if pattern.search(t):
            out += [(n, a) for n, a in tools if not (n in named and not a)]
    seen: set[str] = set()
    unique = []
    for n, a in out:
        key = n + repr(sorted(a.items()))
        if key not in seen:
            seen.add(key)
            unique.append((n, a))
    return unique[:MAX_TOOLS]
