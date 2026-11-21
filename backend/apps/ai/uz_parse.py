"""Deterministic parsing of amounts / percents / counts from Uzbek (and mixed RU/EN) text.

"25 million", "25 mln", "yigirma besh million", "25 000 000", "4,35 mln", "10 millionlik",
"2,5 млн", "500 ming", "20%", "20 foiz", "2 ta xodim", "ikki ta". Pure Python.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_ONES = {
    "bir": 1,
    "ikki": 2,
    "uch": 3,
    "to'rt": 4,
    "tort": 4,
    "besh": 5,
    "olti": 6,
    "yetti": 7,
    "sakkiz": 8,
    "to'qqiz": 9,
    "toqqiz": 9,
}
_TENS = {
    "o'n": 10,
    "on": 10,
    "yigirma": 20,
    "o'ttiz": 30,
    "ottiz": 30,
    "qirq": 40,
    "ellik": 50,
    "oltmish": 60,
    "yetmish": 70,
    "sakson": 80,
    "to'qson": 90,
    "toqson": 90,
}
_SCALE_WORDS = {
    "ming": 1_000,
    "k": 1_000,
    "тысяч": 1_000,
    "тыс": 1_000,
    "million": 1_000_000,
    "mln": 1_000_000,
    "millon": 1_000_000,
    "миллион": 1_000_000,
    "млн": 1_000_000,
    "mlrd": 1_000_000_000,
    "milliard": 1_000_000_000,
    "млрд": 1_000_000_000,
}
_APOS = re.compile(r"[‘’ʻʼ`´]")
# a number with optional thousands separators/decimal comma, then an optional scale word
_NUM = re.compile(
    r"(?<![\w.,])(-?\d{1,3}(?:[  .,]\d{3})+|-?\d+(?:[.,]\d+)?)\s*"
    r"(mlrd|milliard|млрд|million\w*|millon\w*|mln|млн|миллион\w*|ming\w*|тыс\w*|k\b)?",
    re.IGNORECASE,
)
_PCT = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*(%|foiz|процент)", re.IGNORECASE)
_COUNT = re.compile(r"(\d+|[a-z']+)\s*(?:ta|nafar)\b", re.IGNORECASE)


def _clean(text: str) -> str:
    return _APOS.sub("'", text).lower()


def _to_decimal(raw: str) -> Decimal | None:
    s = raw.replace(" ", " ").strip()
    if re.fullmatch(r"-?\d{1,3}(?:[ .,]\d{3})+", s):
        s = re.sub(r"[ .,]", "", s)  # thousands separators
    else:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _scale(word: str | None) -> int:
    if not word:
        return 1
    w = word.lower()
    for key, value in _SCALE_WORDS.items():
        if w.startswith(key):
            return value
    return 1


def parse_number_words(text: str) -> list[Decimal]:
    """'yigirma besh million' -> 25000000; 'olti million ikki yuz ming' -> 6200000."""
    tokens = re.findall(r"[a-z']+|[а-я]+", _clean(text))
    results: list[Decimal] = []
    total = current = 0
    seen = False
    for tok in [*tokens, "<end>"]:
        if tok in _ONES:
            current += _ONES[tok]
            seen = True
        elif tok in _TENS:
            current += _TENS[tok]
            seen = True
        elif tok == "yuz":
            current = (current or 1) * 100
            seen = True
        elif any(tok.startswith(k) for k in ("ming", "million", "mln", "milliard", "миллион")):
            scale = _scale(tok)
            total += (current or 1) * scale
            current = 0
            seen = True
        else:
            if seen:
                results.append(Decimal(total + current))
            total = current = 0
            seen = False
    return results


def parse_amounts(text: str) -> list[Decimal]:
    """All money amounts (so'm) found in the text, in order."""
    t = _clean(text)
    t_no_pct = _PCT.sub(" ", t)
    out: list[Decimal] = []
    for m in _NUM.finditer(t_no_pct):
        value = _to_decimal(m.group(1))
        if value is None:
            continue
        scale = _scale(m.group(2))
        amount = value * scale
        # bare small numbers without a scale word are not money ("2 ta", "3 oyga")
        if scale == 1 and abs(amount) < 10_000:
            continue
        out.append(amount.quantize(Decimal(1)))
    if not out:
        out = [a for a in parse_number_words(t_no_pct) if a >= 10_000]
    return out


def parse_percent(text: str) -> Decimal | None:
    m = _PCT.search(_clean(text))
    return _to_decimal(m.group(1)) if m else None


def parse_count(text: str) -> int | None:
    m = _COUNT.search(_clean(text))
    if not m:
        return None
    word = m.group(1)
    if word.isdigit():
        return int(word)
    nums = parse_number_words(word)
    return int(nums[0]) if nums else None


PURCHASE_WORDS = (
    "olsam",
    "sotib",
    "sarflasam",
    "xarid",
    "harid",
    "to'lasam",
    "qilsam",
    "olaman",
    "olmoqchi",
    "kupit",
    "куплю",
    "купить",
)


def looks_like_purchase(text: str) -> bool:
    t = _clean(text)
    return any(w in t for w in PURCHASE_WORDS) and bool(parse_amounts(text))
