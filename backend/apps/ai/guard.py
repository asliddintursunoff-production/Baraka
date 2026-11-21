"""Number guard (spec §5.5): every number/date the LLM writes must come from tool facts,
display/speech strings, the context or the user's own question."""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

from .uz_format import MONTHS
from .uz_parse import parse_number_words

_APOS = re.compile(r"[‘’ʻʼ`]")
_MONTH = "|".join((*MONTHS, "yan", "fev", "mar", "apr", "avg", "sen", "okt", "noy", "dek"))
_DATE = re.compile(rf"\b(\d{{1,2}})-({_MONTH})", re.IGNORECASE)
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_AMOUNT = re.compile(
    r"(?<![\w-])([−-]?\d{1,3}(?:[  ]\d{3})+|[−-]?\d+(?:[.,]\d+)?)\s*(mlrd|milliard|mln|million\w*|ming\w*)?",
    re.IGNORECASE,
)
TOLERANCE = Decimal(60_000)  # 0,1 mln rounding of display values


def _clean(text: str) -> str:
    return _APOS.sub("'", text).replace("**", "")


def _month_index(token: str) -> int:
    t = token.lower()
    for i, m in enumerate(MONTHS):
        if t.startswith(m[:3]):
            return i + 1
    return 0


def extract(text: str) -> tuple[set[tuple[int, int]], list[Decimal], list[Decimal]]:
    """(dates as (day, month), amounts in so'm, small bare numbers)."""
    t = _clean(text)
    dates = {(int(d), _month_index(m)) for d, m in _DATE.findall(t)}
    dates |= {(int(d), int(m)) for _, m, d in _ISO.findall(t)}
    t_wo = _ISO.sub(" ", _DATE.sub(" ", t))
    amounts: list[Decimal] = []
    smalls: list[Decimal] = []
    for raw, scale in _AMOUNT.findall(t_wo):
        s = raw.replace("−", "-").replace(" ", "").replace(" ", "")
        try:
            v = Decimal(s.replace(",", "."))
        except InvalidOperation:
            continue
        sc = scale.lower()
        if sc.startswith(("mln", "million")):
            amounts.append(v * 1_000_000)
        elif sc.startswith(("mlrd", "milliard")):
            amounts.append(v * 1_000_000_000)
        elif sc.startswith("ming"):
            amounts.append(v * 1000)
        elif abs(v) >= 10_000:
            amounts.append(v)
        else:
            smalls.append(v)
    amounts += [a for a in parse_number_words(t) if a >= 10_000]
    return dates, amounts, smalls


def allowed_from(texts: Iterable[str]) -> tuple[set[tuple[int, int]], list[Decimal], set[Decimal]]:
    dates: set[tuple[int, int]] = set()
    amounts: list[Decimal] = []
    smalls: set[Decimal] = set()
    for t in texts:
        d, a, s = extract(t)
        dates |= d
        amounts += a
        smalls |= set(s) | {abs(x) for x in s}
    return dates, amounts, smalls


def violations(answer_texts: Iterable[str], allowed_texts: Iterable[str]) -> list[str]:
    ok_dates, ok_amounts, ok_small = allowed_from(allowed_texts)
    ok_small |= {Decimal(n) for n in range(0, 4)}  # "1", "2", "3" (step numbers, "bir kun")
    bad: list[str] = []
    for text in answer_texts:
        dates, amounts, smalls = extract(text)
        for d in dates - ok_dates:
            bad.append(f"date {d[0]}-{d[1]}")
        for a in amounts:
            if not any(abs(abs(a) - abs(b)) <= TOLERANCE for b in ok_amounts):
                bad.append(f"amount {a}")
        for s in smalls:
            if abs(s) not in ok_small:
                bad.append(f"number {s}")
    return bad
