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
    ("growth_plan", {}),
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
    (
        r"nima\s+qilish\s+kerak|nima\s+qilay|roadmap|yo'l\s+xarita|foyda\w*\s+(qanday\s+)?oshir|o'sish|rivojlan|ko'proq\s+foyda|daromad\w*\s+oshir",
        [("growth_plan", {})],
    ),
    (
        r"nega\s+.*(tushdi|kamaydi|kamayib|kam\b|ozaydi)|qayerga\s+ketdi|pul\w*\s+qayerga|qancha\s+edi|summa\w*\s+tush|kassa\w*\s+(nega|kamay)",
        [("cash_change", {})],
    ),
    (
        r"bozor\w*\s+narx|raqobatchi|oqtepa|evos|max\s*way|boshqalar\w*\s+(qancha|narx)|nech\s*pul|qanchaga\s+(sot|qo'y)|narx\w*\s+(qancha|qo'y|kutar|oshir)",
        [("market_prices", {})],
    ),
    (
        r"rentabel|foydali\w*\s+(tovar|taom|mahsulot)|zarar\w*\s+(tovar|taom)|oshirayotgan|pasaytirayotgan",
        [("profitability", {})],
    ),
    (
        r"reklama|savdosini\s+kuchaytir|qanchaga\s+oshirsam|punkt\w*\s+yet|qaysi\s+(tovar|taom)\w*\s+(sot|kuchaytir)",
        [("promote_target", {})],
    ),
    (
        r"kontragent|pastavchik|postavshik|yetkazib\s+beruvchi\w*\s+qarz|qarzdorlig|kimga\s+qarz",
        [("payables", {})],
    ),
    (
        r"ishchi\s+olsam|xodim\s+olsam|yangi\s+(ishchi|xodim|ofitsiant|oshpaz|kassir)|o'zini\s+(necha\s+oyda\s+)?oqla",
        [("hire_payback", {})],
    ),
    (
        r"qayerga\s+tik|qayerga\s+(sarfla|qo'y|investitsiya)|qo'shimcha\s+\d+\s*mln|investitsiya\w*\s+reja",
        [("allocate_capital", {"amount": 50_000_000})],
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
_MLN = re.compile(r"(\d+(?:[.,]\d+)?)\s*(mln|million|ming)")
_BUY = re.compile(
    r"(?:yana\s+)?(?:bitta\s+|ikkinchi\s+|yangi\s+)?([a-z'\-]{3,30}(?:\s+[a-z'\-]{3,30})?)\s+(?:sotib\s+)?(?:olsam|olmoqchiman|olaymi|olishim|xarid\s+qilsam|sarflasam)"
)
_AMOUNT = re.compile(r"\d[\d\s.,]*\s*(mln|million|ming|so'm|som|\$|usd)|\d{5,}")
_STOP = {"yana", "bitta", "yangi", "ikkinchi", "pul", "kredit", "qarz", "sotib", "uchun", "som"}
_NOT_ITEM = ("ishchi", "xodim", "ofitsiant", "oshpaz", "kassir", "odam", "bank", "kredit", "qarz")


def route(text: str, prev_intent: str | None = None) -> list[tuple[str, dict[str, Any]]]:
    """Inside the tenant context. Empty when the workbook has no reports or item details."""
    src = DataSource.objects.exclude(summary={}).first()
    summary = (src.summary or {}) if src else {}
    details = summary.get("details") or {}
    if not details and not (summary.get("reports") or {}).get("pl"):
        return []
    t = _APOS.sub("'", text).lower()
    from .golden_tools import match as golden_match

    g = golden_match(t, prev_intent)
    if g is not None:  # a golden report owns this question: one deterministic tool, full report
        return [(g[0].tool, g[1])]
    from .catalog import is_bad_intent, route_catalog

    if is_bad_intent(t):  # "biznesni qulatmoqchiman" etc.: one-line refusal + a legal alternative
        return [("bad_intent", {})]
    from .policy_tools import policy_route

    cat = route_catalog(t)
    pr = policy_route(t)
    if (
        pr
        and cat is not None
        and cat[0].intent == "salary_raise"
        and re.search(r"barobar|baravar|marta|\+\s*\d|ming|mln", t.lower())
    ):
        return pr  # concrete salary what-if (factor / sum) is served by the salary_change tool
    if cat is not None:  # Tier 2: catalogue (only when no golden intent matched)
        return [("catalog", {"intent": cat[0].intent})]
    if pr:  # salaries: look up / compute, never "jadvalda yo'q"
        return pr
    out: list[tuple[str, dict[str, Any]]] = []
    for name in find_names(t, list(details.get("purchases") or {}))[:2]:
        out.append(("product_costs", {"product": name}))
    for name in find_names(t, list(details.get("menu") or {}))[:2]:
        out.append(("menu_analysis", {"dish": name}))
    # "fritur olsam" without a price -> look the price up on the web first
    amt = _MLN.search(t)
    buy = _BUY.search(t)
    if buy and any(w in buy.group(1) for w in _NOT_ITEM):
        buy = None
    amt = _MLN.search(t)
    gen = re.search(r"\b(jihoz|uskuna|aparat|apparat)\w*", t)
    if amt and gen and re.search(r"sarfla|olsam|olay|xarid|sotib", t):
        price = int(
            float(amt.group(1).replace(",", "."))
            * (1_000_000 if amt.group(2).startswith(("mln", "mil")) else 1000)
        )
        out.insert(0, ("evaluate_investment", {"price": price, "item": gen.group(1)}))
        buy = None
    if buy and amt:
        item = " ".join(
            w
            for w in buy.group(1).split()
            if w not in _STOP and not w.isdigit() and w not in ("mln", "ga", "so'm")
        )
        price = int(
            float(amt.group(1).replace(",", "."))
            * (1_000_000 if amt.group(2).startswith(("mln", "mil")) else 1000)
        )
        out.insert(0, ("evaluate_investment", {"price": price, "item": item or "uskuna"}))
    elif buy and not _AMOUNT.search(t):
        item = " ".join(w for w in buy.group(1).split() if w not in _STOP)
        if item:
            out.insert(0, ("web_price_lookup", {"item": item}))
    named = {n for n, _ in out}
    for pattern, tools in ROUTES:
        if pattern.search(t):
            out += [(n, a) for n, a in tools if not (n in named and not a)]
    amt = _MLN.search(t)
    if amt:
        val = int(
            float(amt.group(1).replace(",", "."))
            * (1_000_000 if amt.group(2).startswith(("mln", "mil")) else 1000)
        )
        out = [(n, {**a, "amount": val} if n == "allocate_capital" else a) for n, a in out]
    seen: set[str] = set()
    unique = []
    for n, a in out:
        key = n + repr(sorted(a.items()))
        if key not in seen:
            seen.add(key)
            unique.append((n, a))
    return unique[:MAX_TOOLS]
