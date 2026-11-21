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


# --- date <-> payment pairing (extended fact guard) ---------------------------------------
PAYMENT_WORDS: dict[str, tuple[str, ...]] = {
    "payroll": ("oylik", "ish haqi", "maosh"),
    "loan": ("kredit",),
    "tax": ("soliq",),
    "rent": ("ijara",),
    "kommunal": ("kommunal", "svet", "elektr"),
}


def payment_keys(category: str, counterparty: str, title: str) -> set[str]:
    keys = set(PAYMENT_WORDS.get(category, ()))
    for name in (counterparty, title):
        n = _clean(name).lower().strip()
        if n and category not in PAYMENT_WORDS:  # suppliers etc.: their own name
            keys.add(n.split(" · ")[-1].split("(")[0].strip())
    return {k for k in keys if len(k) >= 4}


def pairing_violations(
    texts: Iterable[str], pairs: Iterable[tuple[tuple[int, int], set[str]]]
) -> list[str]:
    """'soliq 10-dekabr' while the facts say soliq is on 15-dekabr -> violation.

    For every payment word in a sentence, the nearest date in that sentence must be one
    of that payment's real dates."""
    by_key: dict[str, set[tuple[int, int]]] = {}
    for d, keys in pairs:
        for k in keys:
            by_key.setdefault(k, set()).add(d)
    bad: list[str] = []
    for text in texts:
        for sentence in re.split(r"[.!?;\n]", _clean(text).lower()):
            dates = [
                (m.start(), (int(m.group(1)), _month_index(m.group(2))))
                for m in _DATE.finditer(sentence)
            ]
            if not dates:
                continue
            for key, real in by_key.items():
                for m in re.finditer(re.escape(key), sentence):
                    nearest = min(dates, key=lambda d: abs(d[0] - m.start()))[1]
                    if nearest not in real:
                        bad.append(f"{key}≠{nearest[0]}.{nearest[1]}")
    return bad


# --- banned generic steps (advisor) ----------------------------------------------------------
GENERIC = re.compile(
    r"(tekshir|kuzatib bor|kuzating|chora ko'r|e'tibor ber|nazorat qil|o'ylab ko'r|harakat qil|monitoring)",
    re.IGNORECASE,
)
_WHEN = re.compile(
    r"(bugun|ertaga|hafta|oy oxiri|oyda|kunda|dushanba|seshanba|chorshanba|payshanba|juma|shanba|yakshanba|du[–-]pa|sh[–-]ya)",
    re.IGNORECASE,
)


def concrete_step(step: str, names: Iterable[str] = ()) -> bool:
    """A step needs a date, an amount or a concrete object; generic verbs alone fail."""
    t = _clean(step)
    low = t.lower()
    dates, amounts, smalls = extract(t)
    has_when = bool(dates) or bool(_WHEN.search(t))
    has_amount = bool(amounts) or bool(smalls) or "%" in t
    has_object = any(n and n.lower() in low for n in names)
    if len(low.split()) < 3:
        return False
    if GENERIC.search(t) and not (has_when or has_amount):
        return False
    return has_when or has_amount or has_object
