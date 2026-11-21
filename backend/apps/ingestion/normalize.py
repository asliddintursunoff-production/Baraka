"""Pure normalizers for messy spreadsheet cells (no Django imports, fast to test).

Cells arrive from two readers:
- Google Sheets (UNFORMATTED_VALUE + SERIAL_NUMBER): ``str | int | float | bool`` or ``""``;
  dates are serial numbers (days since 1899-12-30).
- openpyxl (``data_only=True``): ``str | int | float | datetime | date | None``.

Money always comes back as a 2-decimal ``Decimal`` (floats go through ``str`` first, never
binary arithmetic); dates as ``date``. Names are compared through ``name_key``, which folds
case, Uzbek/Russian Cyrillic -> Latin, apostrophe variants, quotes and legal forms.
"""

from __future__ import annotations

import calendar
import math
import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Final, Literal

from apps.ai.uz_format import MONTHS, MONTHS_SHORT

Direction = Literal["in", "out"]
CellKind = Literal["empty", "bool", "number", "date", "amount", "text"]

CENT: Final = Decimal("0.01")
SERIAL_EPOCH: Final = date(1899, 12, 30)  # Sheets / Excel day 0 (absorbs the 1900 leap bug)
SERIAL_MIN: Final = 20_000  # 1954-10-03
SERIAL_MAX: Final = 80_000  # 2119-01-11
_MIN_YEAR: Final = 1900
_MAX_YEAR: Final = 2100


class InvalidDate(ValueError):
    """A date-shaped value naming a day its month does not have, e.g. "31.11.2026".

    ``text`` is the cleaned original cell text, ``suggestion`` the last valid day of that
    month (here 2026-11-30), so the caller can offer "30.11 deb olish".
    """

    def __init__(self, text: str, suggestion: date) -> None:
        super().__init__(text, suggestion)
        self.text = text
        self.suggestion = suggestion

    def __str__(self) -> str:
        return f"{self.text!r} is not a real date (nearest valid: {self.suggestion.isoformat()})"


# --- text cleaning ----------------------------------------------------------------------

_APOSTROPHES: Final = re.compile("[ʻʼ‘’`´′ʹʽ]")
_INVISIBLE: Final = re.compile("[­​‌‍⁠﻿]")
_SPACES: Final = re.compile(r"\s+")  # includes NBSP, narrow NBSP, thin space, tabs, newlines
_NON_WORD: Final = re.compile(r"[^\w']+|_")

_CYR_LAT: Final = (
    ("а", "a"), ("б", "b"), ("в", "v"), ("г", "g"), ("д", "d"), ("е", "e"), ("ё", "yo"),
    ("ж", "j"), ("з", "z"), ("и", "i"), ("й", "y"), ("к", "k"), ("л", "l"), ("м", "m"),
    ("н", "n"), ("о", "o"), ("п", "p"), ("р", "r"), ("с", "s"), ("т", "t"), ("у", "u"),
    ("ф", "f"), ("х", "x"), ("ц", "ts"), ("ч", "ch"), ("ш", "sh"), ("щ", "sh"), ("ъ", "'"),
    ("ы", "i"), ("ь", ""), ("э", "e"), ("ю", "yu"), ("я", "ya"), ("ў", "o'"), ("қ", "q"),
    ("ғ", "g'"), ("ҳ", "h"), ("і", "i"),
)  # fmt: skip
_TRANSLIT: Final = str.maketrans(
    {**{c: lat for c, lat in _CYR_LAT}, **{c.upper(): lat.capitalize() for c, lat in _CYR_LAT}}
)
# Cyrillic "е" is "ye" at the start of a word and after a vowel or a hard/soft sign.
_YE: Final = re.compile(r"(?<![^\W\d_])е|(?<=[аеёиоуўэюяыъь])е", re.IGNORECASE)

_LEGAL_FORMS: Final = frozenset(
    {
        "mchj", "ooo", "xk", "yatt", "ytt", "aj", "oaj", "ao", "oao", "zao", "pao", "qk",
        "xf", "fx", "chp", "ip", "duk", "uk", "atb", "llc", "ltd", "inc",
    }
)  # fmt: skip
_LEGAL_PHRASES: Final = (
    "mas'uliyati cheklangan jamiyati",
    "mas'uliyati cheklangan jamiyat",
    "masuliyati cheklangan jamiyati",
    "xususiy korxonasi",
    "xususiy korxona",
    "yakka tartibdagi tadbirkor",
    "obshestvo s ogranichennoy otvetstvennostyu",
)


def clean_name(value: object) -> str:
    """Trim, collapse whitespace (NBSP too) and unify apostrophes (ʻ ʼ ‘ ’ ` -> ')."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        text = str(int(value))
    else:
        text = str(value)
    text = unicodedata.normalize("NFC", text)
    text = _INVISIBLE.sub("", text)
    text = _APOSTROPHES.sub("'", text)
    return _SPACES.sub(" ", text).strip()


def to_latin(text: str) -> str:
    """Uzbek (and Russian) Cyrillic -> Uzbek Latin: ш->sh, ў->o', ғ->g', ҳ->h, ц->ts, ..."""
    text = _YE.sub(lambda m: "Ye" if m.group().isupper() else "ye", text)
    return text.translate(_TRANSLIT)


def _tidy_apostrophes(token: str) -> str:
    """Keep o'/g' and the tutuq belgisi between letters (ta'minot); drop quote-like ones."""
    out: list[str] = []
    for i, ch in enumerate(token):
        if ch != "'":
            out.append(ch)
            continue
        prev = token[i - 1] if i else ""
        nxt = token[i + 1] if i + 1 < len(token) else ""
        if prev == "g" or (prev.isalpha() and nxt.isalpha()):
            out.append(ch)
    return "".join(out)


def text_key(value: object) -> str:
    """Casefolded, Latin, punctuation-free text for keyword matching ("Ф.И.Ш." -> "f i sh")."""
    text = to_latin(clean_name(value).casefold())
    tokens = (_tidy_apostrophes(t) for t in _NON_WORD.sub(" ", text).split())
    return " ".join(t for t in tokens if t)


def name_key(value: object) -> str:
    """Comparable counterparty key: 'ООО «Агро Гўшт»' == '"Agro Go‘sht" MChJ' -> "agro go'sht"."""
    key = f" {text_key(value)} "
    for phrase in _LEGAL_PHRASES:
        key = key.replace(f" {phrase} ", " ")
    return " ".join(t for t in key.split() if t not in _LEGAL_FORMS)


# --- amounts ----------------------------------------------------------------------------

_UNITS: Final = re.compile(r"(?<![^\W\d_])(?:so'?m|sum|сўм|сум|uzs)(?![^\W\d_])\.?")
_EMPTY_PARENS: Final = re.compile(r"\(\s*\)")
_AMOUNT: Final = re.compile(r"(?P<num>[0-9][0-9 .,']*?)\s*(?P<scale>[^\W\d_]+\.?)?")
_SCALE_EXACT: Final = {
    "k": 1_000,
    "к": 1_000,
    "тыс": 1_000,
    "mln": 1_000_000,
    "млн": 1_000_000,
    "mlrd": 1_000_000_000,
    "млрд": 1_000_000_000,
}
_SCALE_STEMS: Final = (
    ("ming", 1_000),
    ("минг", 1_000),
    ("тысяч", 1_000),
    ("milliard", 1_000_000_000),
    ("миллиард", 1_000_000_000),
    ("million", 1_000_000),
    ("millon", 1_000_000),
    ("миллион", 1_000_000),
)


def _money(value: Decimal) -> Decimal | None:
    try:
        return value.quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:  # beyond Decimal precision: not a real amount
        return None


def _scale_of(word: str) -> int | None:
    w = word.rstrip(".")
    if w in _SCALE_EXACT:
        return _SCALE_EXACT[w]
    for stem, scale in _SCALE_STEMS:
        if w.startswith(stem):
            return scale
    return None


def _grouped(sep: str) -> str:
    """Regex for 1-3 leading digits followed by groups of exactly 3: 4<sep>350<sep>000."""
    return rf"[0-9]{{1,3}}(?:{re.escape(sep)}[0-9]{{3}})+"


def _parse_number(s: str, *, has_scale: bool) -> Decimal | None:
    if " " in s or "'" in s:
        if " " in s and "'" in s:
            return None
        sep = " " if " " in s else "'"
        m = re.fullmatch(rf"({_grouped(sep)})(?:[.,]([0-9]+))?", s)
        if not m:
            return None  # e.g. a phone number "998 90 123 45 67"
        whole = m.group(1).replace(sep, "")
        return Decimal(f"{whole}.{m.group(2)}" if m.group(2) else whole)
    dots, commas = s.count("."), s.count(",")
    if dots and commas:  # the last separator is the decimal one: 4,350,000.50 / 4.350.000,50
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        m = re.fullmatch(rf"({_grouped(thou)}){re.escape(dec)}([0-9]+)", s)
        return Decimal(f"{m.group(1).replace(thou, '')}.{m.group(2)}") if m else None
    if not dots and not commas:
        return Decimal(s) if re.fullmatch("[0-9]+", s) else None
    sep = "." if dots else ","
    if dots + commas > 1:  # 4,350,000 / 4.350.000
        return Decimal(s.replace(sep, "")) if re.fullmatch(_grouped(sep), s) else None
    whole, frac = s.split(sep)
    if not re.fullmatch("[0-9]+", whole) or not re.fullmatch("[0-9]+", frac):
        return None
    # "4,500" is 4500 (thousands); "4,5" / "4350000.0" / "4,35 mln" are decimals
    if not has_scale and len(frac) == 3 and len(whole) <= 3 and whole != "0":
        return Decimal(whole + frac)
    return Decimal(f"{whole}.{frac}")


def _parse_amount_text(raw: str) -> Decimal | None:
    text = clean_name(raw).casefold()
    if not text or text[0] in "=#":  # formulas / #REF!, #N/A
        return None
    text = _UNITS.sub(" ", text)
    text = _EMPTY_PARENS.sub(" ", text).strip().rstrip(".,;:").strip()
    negative = False
    if len(text) > 1 and text[0] == "(" and text[-1] == ")":  # accounting negative
        negative, text = True, text[1:-1].strip()
    if text and text[0] in "-−–+":
        negative = negative or text[0] != "+"
        text = text[1:].strip()
    m = _AMOUNT.fullmatch(text)
    if not m:
        return None
    scale = 1
    if m.group("scale"):
        found = _scale_of(m.group("scale"))
        if found is None:
            return None  # "$100", "20 ta", "100 rubl": not so'm
        scale = found
    number = _parse_number(m.group("num").strip(), has_scale=m.group("scale") is not None)
    if number is None:
        return None
    amount = number * scale
    return _money(-amount if negative else amount)


def parse_amount(value: object) -> Decimal | None:
    """Money in so'm as a 2-decimal Decimal; None for empty / unparseable.

    "4 350 000" (also NBSP), "4,350,000", "4.350.000", "4350000 so'm", "4 350 000 сўм/сум/UZS",
    "4,35 mln", "4.35 млн", "500 ming", "-4 350 000", "(4 350 000)", 4350000, 4350000.0.
    A single separator followed by exactly three digits is a thousands separator ("4,500" ->
    4500) unless a scale word follows ("1,250 mln" -> 1 250 000); otherwise it is decimal.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return _money(Decimal(value))
    if isinstance(value, float):
        return _money(Decimal(str(value))) if math.isfinite(value) else None
    if isinstance(value, Decimal):
        return _money(value) if value.is_finite() else None
    if isinstance(value, str):
        return _parse_amount_text(value)
    return None


# --- dates ------------------------------------------------------------------------------

_TIME_SUFFIX: Final = re.compile(
    r"(?:[\st]|,\s*)[0-9]{1,2}:[0-9]{2}(?::[0-9]{2}(?:[.,][0-9]+)?)?"  # 10:30[:00[.5]]
    r"\s*(?:z|[+-][0-9]{2}:?[0-9]{2})?$"  # Z / +05:00
)
_YEAR_SUFFIX: Final = re.compile(r"(?<=[0-9])\s*-?\s*(?:yil\w*|y|йил\w*|й|года|год|г)\.?$")
_SERIAL_TEXT: Final = re.compile(r"[0-9]{5}(?:\.[0-9]+)?")
_ISO: Final = re.compile(r"([0-9]{4})[-./]([0-9]{1,2})[-./]([0-9]{1,2})")
_DMY: Final = re.compile(r"([0-9]{1,2})[-./]([0-9]{1,2})[-./]([0-9]{4}|[0-9]{2})")
_DM: Final = re.compile(r"([0-9]{1,2})[-./]([0-9]{1,2})")
_D_MON_Y: Final = re.compile(r"([0-9]{1,2})[-\s./,]*([^\W\d_]+)\.?(?:[-\s./,]*([0-9]{4}))?")
_MON_D_Y: Final = re.compile(r"([^\W\d_]+)\.?[-\s./,]*([0-9]{1,2})(?:[-\s./,]+([0-9]{4}))?")
_Y_D_MON: Final = re.compile(
    r"([0-9]{4})[-\s]*(?:yil\w*|йил\w*|y)?[-\s./,]*([0-9]{1,2})[-\s]*([^\W\d_]+)"
)

_MONTH_EXTRA: Final = (
    ("january",),
    ("february",),
    ("march",),
    ("april",),
    (),
    ("june",),
    ("july",),
    ("august",),
    ("sentabr", "september"),
    ("oktabr", "october"),
    ("november",),
    ("december",),
)
_MONTH_ABBR_EXTRA: Final = (
    ("yanv", "jan"),
    ("fevr", "feb"),
    (),
    (),
    (),
    ("jun",),
    ("jul",),
    ("aug",),
    ("sent", "sep", "sept"),
    ("oct",),
    ("noya", "nov"),
    ("dec",),
)
# Russian case endings after transliteration (ноября -> noyabrya, марта -> marta,
# ноябре -> noyabre) and Uzbek suffixes (noyabrda, dekabrgacha).
_MONTH_SUFFIXES: Final = ("", "a", "ya", "e", "da", "ga", "dan", "gacha", "ning", "dagi")


def _month_forms() -> dict[str, int]:
    forms: dict[str, int] = {}
    for i in range(12):
        for stem in (MONTHS[i], *_MONTH_EXTRA[i]):
            for suffix in _MONTH_SUFFIXES:
                forms.setdefault(stem + suffix, i + 1)
        for abbr in (MONTHS_SHORT[i], *_MONTH_ABBR_EXTRA[i]):
            forms[abbr] = i + 1
    return forms


_MONTH_FORMS: Final = _month_forms()


def _month_of(word: str) -> int | None:
    return _MONTH_FORMS.get(to_latin(word.casefold()).rstrip("."))


def from_serial(value: float | int | Decimal) -> date | None:
    """Sheets/Excel serial day number -> date, only inside 20000..80000 (1954..2119)."""
    x = float(value)
    if not math.isfinite(x) or not SERIAL_MIN <= x <= SERIAL_MAX:
        return None
    return SERIAL_EPOCH + timedelta(days=math.floor(x))


def _last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _nearest_year(text: str, day: int, month: int, today: date) -> date:
    """No year written: the year that puts the date nearest to today (ties -> the past)."""
    years = (today.year - 1, today.year, today.year + 1)
    valid = [date(y, month, day) for y in years if day <= _last_day(y, month)]
    if valid:
        return min(valid, key=lambda d: (abs((d - today).days), d))
    clamped = [date(y, month, _last_day(y, month)) for y in years]
    raise InvalidDate(text, min(clamped, key=lambda d: (abs((d - today).days), d)))


def _make_date(text: str, day: int, month: int, year: int | None, today: date) -> date | None:
    if not 1 <= month <= 12:
        if 13 <= month <= 31 and 1 <= day <= 12:  # unambiguous US order: 11/14/2026
            day, month = month, day
        else:
            return None
    if not 1 <= day <= 31:
        return None
    if year is None:
        return _nearest_year(text, day, month, today)
    if year < 100:
        year += 2000
    if not _MIN_YEAR <= year <= _MAX_YEAR:
        return None
    last = _last_day(year, month)
    if day > last:
        raise InvalidDate(text, date(year, month, last))
    return date(year, month, day)


def _parse_date_text(text: str, today: date) -> date | None:
    s = _TIME_SUFFIX.sub("", text.casefold()).strip()
    s = _YEAR_SUFFIX.sub("", s).strip()
    if _SERIAL_TEXT.fullmatch(s):
        return from_serial(float(s))
    if m := _ISO.fullmatch(s):
        return _make_date(text, int(m[3]), int(m[2]), int(m[1]), today)
    if m := _DMY.fullmatch(s):
        return _make_date(text, int(m[1]), int(m[2]), int(m[3]), today)
    if m := _DM.fullmatch(s):
        return _make_date(text, int(m[1]), int(m[2]), None, today)
    for pattern, d_i, m_i, y_i in ((_D_MON_Y, 1, 2, 3), (_MON_D_Y, 2, 1, 3), (_Y_D_MON, 2, 3, 1)):
        if m := pattern.fullmatch(s):
            month = _month_of(m[m_i])
            if month is None:
                return None
            year = int(m[y_i]) if m[y_i] else None
            return _make_date(text, int(m[d_i]), month, year, today)
    return None


def parse_date(value: object, *, today: date) -> date | None:
    """A cell -> date; None for empty or garbage; InvalidDate for e.g. "31.11.2026".

    14.11.2026, 14/11/2026, 14-11-2026, 14.11.26, 2026-11-14 (time part ignored),
    14 noyabr 2026, 14-noyabr, 14 ноября 2026 г., 14 ноябр, 2026 yil 14 noyabr, Nov 14 2026,
    Sheets serials (20000..80000, also as digit-only text) and date/datetime objects.
    Without a year the year nearest to ``today`` is used.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, int | float | Decimal):
        return from_serial(value)
    if not isinstance(value, str):
        return None
    text = clean_name(value)
    return _parse_date_text(text, today) if text else None


# --- direction / day of month -----------------------------------------------------------

_IN_EXACT: Final = frozenset({"in", "plus", "kirdi", "tushdi"})
_OUT_EXACT: Final = frozenset({"out", "minus", "chiqdi"})
_IN_STEMS: Final = (
    "kirim", "tushum", "daromad", "savdo", "sotuv", "prixod", "doxod", "postuplen",
    "viruchka", "prodaj", "income", "inflow", "revenue", "receipt", "deposit",
)  # fmt: skip
_OUT_STEMS: Final = (
    "chiqim", "xarajat", "harajat", "sarf", "rasxod", "zatrat", "spisan", "expense",
    "outflow", "spend", "spent", "withdraw", "payout",
)  # fmt: skip


def parse_direction(value: object) -> Direction | None:
    """'kirim'/'приход'/'+'/'income' -> "in"; 'chiqim'/'расход'/'-'/'xarajat' -> "out".

    Works on headers too ("Kirim (so'm)" -> "in"); text naming both ("Kirim/chiqim") -> None.
    """
    if not isinstance(value, str):
        return None
    raw = clean_name(value).casefold()
    if raw in ("+", "++"):
        return "in"
    if raw in ("-", "−", "–", "--"):
        return "out"
    tokens = text_key(raw).split()
    is_in = any(t in _IN_EXACT or t.startswith(_IN_STEMS) for t in tokens)
    is_out = any(t in _OUT_EXACT or t.startswith(_OUT_STEMS) for t in tokens)
    if is_in == is_out:
        return None
    return "in" if is_in else "out"


def parse_day_of_month(value: object) -> int | None:
    """Payment day 1..31 from "10", 10, 10.0, "har oy 25", "25-sana", "ҳар ой 10-санада"."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float | Decimal):
        x = float(value)
        return int(x) if x.is_integer() and 1 <= x <= 31 else None
    if not isinstance(value, str):
        return None
    text = clean_name(value)
    if re.fullmatch(r"[0-9]+(?:[.,]0+)?", text):
        n = int(re.split(r"[.,]", text)[0])
    else:
        numbers = re.findall(r"[0-9]+", text)
        if len(numbers) != 1:
            return None
        n = int(numbers[0])
    return n if 1 <= n <= 31 else None


# --- cell classification (header detection / column sniffing) --------------------------

_REF_DAY: Final = date(2000, 1, 1)  # year inference is irrelevant for "is it a date?"
_PLAIN_NUMBER: Final = re.compile(r"[-+]?[0-9]+(?:\.0+)?")


def classify_cell(value: object) -> CellKind:
    """Rough cell type: numbers stay "number" (a 46000 may be a serial or an amount)."""
    if value is None:
        return "empty"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, date):
        return "date"
    if isinstance(value, int | float | Decimal):
        return "number"
    text = clean_name(value)
    if not text:
        return "empty"
    if _PLAIN_NUMBER.fullmatch(text):
        return "amount"
    try:
        if parse_date(text, today=_REF_DAY) is not None:
            return "date"
    except InvalidDate:
        return "date"
    if parse_amount(text) is not None:
        return "amount"
    return "text"


def is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not clean_name(value))
