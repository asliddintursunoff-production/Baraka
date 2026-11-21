"""Intent router (rules first): `quick` lookups keep the fast path, `advisor` questions
(plans, goals, debts, loans, investments, growth, "what should I do") get the advisor loop.

No LLM here: an unclear question stays `quick`, whose tools still answer with engine
numbers, and the model may still call advisor tools from there.
"""

from __future__ import annotations

import re

_APOS = re.compile(r"[‘’ʻʼ`]")
ADVISOR = re.compile(
    r"(qachon\s+(ola|olaman|topaman|yig|to'play|sotib)|o'zini\s+qopla|qoplaydi|qarz|kredit\s*ol|"
    r"qarzga|yopa\s+olaman|oshirmoqchi|oshirsam|oshirish|o'sish|daromad\w*\s+.*osh|savdo\w*\s+.*osh|"
    r"reja|yo'l\s*xarita|nima\s+qilsam|nima\s+qilay|qanday\s+qilsam|maslahat|biznesim\s+qanday|"
    r"investitsiya|sarmoya|narx\w*\s+.*(osh|ko'tar|tushir)|lizing|uzsam|taqqosla|solishtir|"
    r"yig'moqchi|jamg'ar|maqsad)",
    re.IGNORECASE,
)


def classify(text: str) -> str:
    t = _APOS.sub("'", text).lower()
    return "advisor" if ADVISOR.search(t) else "quick"


def advisor_hint(text: str) -> tuple[str, dict[str, object]] | None:
    """A deterministic first tool for common advisor questions (cards before the LLM)."""
    from .uz_parse import parse_amounts, parse_percent

    t = _APOS.sub("'", text).lower()
    amounts = parse_amounts(text)
    pct = parse_percent(text)
    if re.search(r"biznesim\s+qanday|biznes(im)?\s+holat", t):
        return "business_snapshot", {}
    if amounts and re.search(r"qachon\s+(topaman|yig|to'play|jamg)", t):
        return "savings_goal", {"amount": int(amounts[0])}
    if amounts and re.search(r"qachon\s+(ola|olaman|sotib)", t):
        return "when_can_afford", {"amount": int(amounts[0])}
    if pct is not None and re.search(r"osh", t):
        return "revenue_growth_target", {"pct": str(pct)}
    return None
