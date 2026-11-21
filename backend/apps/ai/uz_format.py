"""Deterministic Uzbek (Latin) formatting for display and speech.

The LLM never formats numbers: every `display` / `speech` string in a tool response
is built here. Pure Python, no Django imports.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Literal

MINUS = "−"  # typographic minus, as in the design ("−6,2 mln")
NBSP = " "
MLN = Decimal(1_000_000)

MONTHS = (
    "yanvar",
    "fevral",
    "mart",
    "aprel",
    "may",
    "iyun",
    "iyul",
    "avgust",
    "sentyabr",
    "oktyabr",
    "noyabr",
    "dekabr",
)
MONTHS_SHORT = (
    "yan",
    "fev",
    "mar",
    "apr",
    "may",
    "iyun",
    "iyul",
    "avg",
    "sen",
    "okt",
    "noy",
    "dek",
)
WEEKDAYS = ("dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba")
WEEKDAYS_SHORT = ("Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya")

_ONES = ("", "bir", "ikki", "uch", "to'rt", "besh", "olti", "yetti", "sakkiz", "to'qqiz")
_TENS = ("", "o'n", "yigirma", "o'ttiz", "qirq", "ellik", "oltmish", "yetmish", "sakson", "to'qson")
_SCALES = ((10**9, "milliard"), (10**6, "million"), (10**3, "ming"))

Case = Literal["da", "ga", "dan", "gacha"]


def _to_decimal(value: Decimal | int | str) -> Decimal:
    if isinstance(value, float):  # pragma: no cover - guarded by type hints
        raise TypeError("float is not allowed for money")
    return value if isinstance(value, Decimal) else Decimal(value)


def group_digits(n: int) -> str:
    """4350000 -> '4 350 000' (non-breaking spaces)."""
    sign = MINUS if n < 0 else ""
    return sign + f"{abs(n):,}".replace(",", NBSP)


def format_som(amount: Decimal | int | str) -> str:
    """Exact amount: '4 350 000 so'm'."""
    value = _to_decimal(amount).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return f"{group_digits(int(value))} so'm"


def round_mln(amount: Decimal | int | str) -> Decimal:
    """Amount in millions, rounded half-up to one decimal: 6185000 -> Decimal('6.2')."""
    value = _to_decimal(amount) / MLN
    return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def format_mln_number(amount: Decimal | int | str) -> str:
    """'48,2' (number only, as in KPI cards)."""
    value = round_mln(amount)
    text = f"{abs(value):.1f}".replace(".", ",")
    return (MINUS + text) if value < 0 else text


def format_mln(amount: Decimal | int | str, *, signed: bool = False, short: bool = False) -> str:
    """6200000 -> '6,2 mln'; -6200000 -> '−6,2 mln'; signed -> '+18,8 mln'.

    `short=True` drops a trailing ',0' ('22 mln' instead of '22,0 mln').
    """
    value = round_mln(amount)
    text = f"{abs(value):.1f}".replace(".", ",")
    if short and text.endswith(",0"):
        text = text[:-2]
    if value < 0:
        sign = MINUS
    elif signed and value > 0:
        sign = "+"
    else:
        sign = ""
    return f"{sign}{text} mln"


def floor_to(amount: Decimal | int | str, step: Decimal | int) -> Decimal:
    """Round down to a multiple of `step` (8 815 000 -> 8 000 000 for step 1 mln)."""
    value = _to_decimal(amount)
    step_d = _to_decimal(step)
    return (value / step_d).to_integral_value(rounding=ROUND_FLOOR) * step_d


def _words_below_1000(n: int) -> list[str]:
    words: list[str] = []
    hundreds, rest = divmod(n, 100)
    if hundreds:
        if hundreds > 1:
            words.append(_ONES[hundreds])
        words.append("yuz")
    tens, ones = divmod(rest, 10)
    if tens:
        words.append(_TENS[tens])
    if ones:
        words.append(_ONES[ones])
    return words


def uz_number_words(n: int | Decimal) -> str:
    """6200000 -> 'olti million ikki yuz ming'; -5 -> 'minus besh'; 0 -> 'nol'."""
    value = int(n)
    if value == 0:
        return "nol"
    if value < 0:
        return "minus " + uz_number_words(-value)
    words: list[str] = []
    rest = value
    for scale, name in _SCALES:
        count, rest = divmod(rest, scale)
        if count:
            words.extend(_words_below_1000(count))
            words.append(name)
    words.extend(_words_below_1000(rest))
    return " ".join(words)


def speech_amount(amount: Decimal | int | str) -> str:
    """Spoken amount, rounded like the display (0,1 mln) for amounts >= 1 mln.

    -6185000 -> "minus olti million ikki yuz ming so'm".
    Smaller amounts are spoken to the nearest thousand.
    """
    value = _to_decimal(amount)
    if abs(value) >= MLN:
        rounded = round_mln(value) * MLN
    else:
        rounded = (value / 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP) * 1000
    return f"{uz_number_words(int(rounded))} so'm"


def _ends_with_vowel(word: str) -> bool:
    return word[-1] in "aeiou"


def uz_ordinal_words(n: int) -> str:
    """10 -> "o'ninchi", 12 -> "o'n ikkinchi", 20 -> 'yigirmanchi'."""
    if n <= 0:
        raise ValueError("ordinals start at 1")
    cardinal = uz_number_words(n)
    suffix = "nchi" if _ends_with_vowel(cardinal) else "inchi"
    return cardinal + suffix


def add_case(word: str, case: Case) -> str:
    """Attach a case suffix: dekabr+da, dekabr+ga, Agro Go'sht+ga, kredit+ga, ..."""
    if case == "ga" or case == "gacha":
        last = word[-1].lower()
        head = "ka" if last == "k" else "qa" if last == "q" else "ga"
        return word + head + ("cha" if case == "gacha" else "")
    return word + case


def format_date(d: date, case: Case | None = None) -> str:
    """'10-dekabr', with case: '10-dekabrda', '10-dekabrgacha'."""
    text = f"{d.day}-{MONTHS[d.month - 1]}"
    return add_case(text, case) if case else text


def format_date_short(d: date) -> str:
    """'25-noy' (tables)."""
    return f"{d.day}-{MONTHS_SHORT[d.month - 1]}"


def format_date_long(d: date) -> str:
    """'21-noyabr, shanba'."""
    return f"{format_date(d)}, {WEEKDAYS[d.weekday()]}"


def uz_ordinal_date(d: date, case: Case | None = None) -> str:
    """date(2026, 12, 10) -> "o'ninchi dekabr"; with case 'da' -> "o'ninchi dekabrda"."""
    month = MONTHS[d.month - 1]
    text = f"{uz_ordinal_words(d.day)} {add_case(month, case) if case else month}"
    return text
