"""Guess what each column of a sheet means and what kind of sheet it is (pure, no Django).

Headers are matched against keyword dictionaries written in Uzbek Latin, Uzbek Cyrillic,
Russian and English. Keywords and headers both go through ``text_key`` (casefold +
Cyrillic -> Latin + punctuation -> space), so "Сана", "сана" and "Sana" are the same word and
"Ф.И.Ш." becomes "f i sh". A keyword of 4+ characters matches at the start of a word
("sanasi", "kontragentlar"); shorter ones must be the whole word.

The header guess is then checked against the sample values (numbers -> amount, dates and
serials -> date, kirim/chiqim -> direction, naqd/karta -> method). Confidence is 0..1 and
deliberately below CONFIRM_THRESHOLD (0.8) whenever the meaning needs the person to confirm,
e.g. every "Holati" column: we cannot tell "paid" from "planned" semantics on our own.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final

from .normalize import (
    SERIAL_MAX,
    SERIAL_MIN,
    Direction,
    classify_cell,
    clean_name,
    parse_amount,
    parse_day_of_month,
    parse_direction,
    text_key,
)

CONFIRM_THRESHOLD: Final = 0.8
FIELDS: Final = (
    "date",
    "amount",
    "direction",
    "category",
    "counterparty",
    "due_date",
    "method",
    "status",
    "note",
    "ignore",
)
SHEET_KINDS: Final = (
    "transactions_in",
    "transactions_out",
    "transactions_mixed",
    "obligations_schedule",
    "payroll",
    "loan_schedule",
    "counterparties",
    "cash_balance",
    "ignore",
)
TRANSACTION_KINDS: Final = frozenset({"transactions_in", "transactions_out", "transactions_mixed"})


@dataclass(frozen=True, slots=True)
class ColumnGuess:
    index: int
    header: str
    field: str
    confidence: float
    # Set on amount columns whose header names the flow ("Kirim" / "Chiqim" sums in one
    # sheet); None for a plain "Summa" column.
    direction: Direction | None = None


@dataclass(frozen=True, slots=True)
class MappingGuess:
    sheet_kind: str
    kind_confidence: float
    columns: list[ColumnGuess] = field(default_factory=list)

    def column_for(self, field_name: str) -> ColumnGuess | None:
        """The first column mapped to ``field_name``."""
        return next((c for c in self.columns if c.field == field_name), None)

    def needs_confirmation(self, threshold: float = CONFIRM_THRESHOLD) -> list[ColumnGuess]:
        return [c for c in self.columns if c.header and c.confidence < threshold]


# --- keyword dictionaries ---------------------------------------------------------------
# (keyword, weight). Several languages per field; Cyrillic is transliterated on import.

_KEYWORDS: Final[dict[str, tuple[tuple[str, float], ...]]] = {
    "date": (
        ("sana", 0.9),
        ("сана", 0.9),
        ("дата", 0.9),
        ("date", 0.9),
        ("operatsiya sanasi", 0.95),
        ("kun", 0.6),
        ("число", 0.7),
        ("день", 0.6),
        ("vaqt", 0.6),
        ("day", 0.6),
    ),
    "amount": (
        ("summa", 0.9),
        ("сумма", 0.9),
        ("amount", 0.9),
        ("to'lov summasi", 0.95),
        ("jami to'lov", 0.92),
        ("qoldiq", 0.75),
        ("остаток", 0.75),
        ("balans", 0.7),
        ("balance", 0.7),
        ("maosh", 0.9),
        ("oklad", 0.85),
        ("оклад", 0.85),
        ("зарплата", 0.85),
        ("ish haqi", 0.85),
        ("иш ҳақи", 0.85),
        ("oylik", 0.75),
        ("salary", 0.85),
        ("narx", 0.7),
        ("цена", 0.7),
        ("стоимость", 0.7),
        ("price", 0.7),
        ("jami", 0.75),
        ("итого", 0.75),
        ("total", 0.75),
        ("to'lov", 0.6),
        ("платеж", 0.7),
        ("pul", 0.6),
        ("so'm", 0.7),
        ("сўм", 0.7),
        ("sum", 0.7),
        ("uzs", 0.7),
        ("asosiy qarz", 0.55),
    ),
    "direction": (
        ("kirim chiqim", 0.9),
        ("kirim", 0.85),
        ("chiqim", 0.85),
        ("кирим", 0.85),
        ("чиқим", 0.85),
        ("приход расход", 0.9),
        ("приход", 0.85),
        ("расход", 0.85),
        ("yo'nalish", 0.85),
        ("направление", 0.85),
        ("direction", 0.9),
        ("operatsiya turi", 0.8),
        ("turi", 0.6),
        ("tur", 0.55),
        ("тип", 0.6),
        ("вид", 0.5),
        ("type", 0.6),
        ("daromad", 0.7),
        ("xarajat", 0.7),
        ("harajat", 0.7),
        ("tushum", 0.7),
        ("income", 0.7),
        ("expense", 0.7),
        ("in out", 0.85),
    ),
    "category": (
        ("nima uchun", 0.85),
        ("kategoriya", 0.9),
        ("категория", 0.9),
        ("category", 0.9),
        ("статья", 0.85),
        ("toifa", 0.85),
        ("turkum", 0.8),
        ("xarajat turi", 0.88),
        ("harajat turi", 0.88),
        ("xarajat moddasi", 0.9),
        ("назначение", 0.75),
        ("maqsad", 0.7),
        ("purpose", 0.7),
        ("nima", 0.6),
        ("mahsulot", 0.6),
        ("tovar", 0.6),
        ("товар", 0.6),
        ("наименование", 0.6),
    ),
    "counterparty": (
        ("kimga", 0.9),
        ("kimdan", 0.9),
        ("kim", 0.6),
        ("kontragent", 0.95),
        ("контрагент", 0.95),
        ("counterparty", 0.95),
        ("ta'minotchi", 0.9),
        ("таъминотчи", 0.9),
        ("поставщик", 0.9),
        ("yetkazib beruvchi", 0.9),
        ("supplier", 0.9),
        ("vendor", 0.9),
        ("payee", 0.9),
        ("mijoz", 0.85),
        ("клиент", 0.85),
        ("customer", 0.85),
        ("xaridor", 0.85),
        ("покупатель", 0.85),
        ("получатель", 0.85),
        ("ф.и.ш.", 0.9),
        ("f.i.sh.", 0.9),
        ("ф.и.о.", 0.9),
        ("фио", 0.9),
        ("fio", 0.9),
        ("xodim", 0.85),
        ("сотрудник", 0.85),
        ("ishchi", 0.8),
        ("employee", 0.85),
        ("ism familiya", 0.9),
        ("ism", 0.75),
        ("имя", 0.7),
        ("name", 0.6),
        ("tashkilot", 0.7),
        ("организация", 0.7),
        ("kompaniya", 0.6),
        ("firma", 0.6),
    ),
    "due_date": (
        ("muddat", 0.9),
        ("to'lash muddati", 0.95),
        ("oxirgi muddat", 0.95),
        ("to'lov sanasi", 0.92),
        ("to'lov kuni", 0.92),
        ("срок", 0.9),
        ("срок оплаты", 0.95),
        ("дата платежа", 0.92),
        ("reja sanasi", 0.85),
        ("due", 0.9),
        ("due date", 0.95),
        ("deadline", 0.9),
    ),
    "method": (
        ("naqd karta", 0.9),
        ("naqd", 0.85),
        ("karta", 0.8),
        ("to'lov turi", 0.9),
        ("to'lov usuli", 0.95),
        ("usul", 0.8),
        ("способ оплаты", 0.95),
        ("вид оплаты", 0.9),
        ("тип оплаты", 0.9),
        ("форма оплаты", 0.9),
        ("способ", 0.8),
        ("наличные", 0.8),
        ("method", 0.9),
        ("payment method", 0.95),
        ("payment type", 0.9),
    ),
    "status": (
        ("holati", 0.7),
        ("holat", 0.7),
        ("статус", 0.7),
        ("status", 0.7),
        ("состояние", 0.7),
        ("to'langanmi", 0.7),
        ("оплачено", 0.7),
        ("paid", 0.7),
        ("state", 0.6),
    ),
    "note": (
        ("izoh", 0.9),
        ("изоҳ", 0.9),
        ("примечание", 0.9),
        ("комментарий", 0.9),
        ("note", 0.9),
        ("comment", 0.9),
        ("description", 0.8),
        ("tavsif", 0.85),
        ("описание", 0.85),
        ("eslatma", 0.85),
        ("batafsil", 0.7),
        ("lavozim", 0.6),
        ("должность", 0.6),
    ),
    "ignore": (
        ("telefon", 0.85),
        ("phone", 0.85),
        ("manzil", 0.85),
        ("адрес", 0.85),
        ("address", 0.85),
        ("stir", 0.85),
        ("инн", 0.85),
        ("hisob raqam", 0.8),
        ("foiz", 0.65),
        ("процент", 0.65),
        ("interest", 0.65),
        ("qoldiq qarz", 0.8),
        ("qarz qoldig'i", 0.8),
        ("остаток долга", 0.8),
    ),
}

_ROW_NUMBER_HEADERS: Final = frozenset(
    {"№", "#", "n", "no", "no.", "n°", "№ п/п", "п/п", "t/r", "т/р", "т/р.", "t/r."}
)
_BALANCE_WORDS: Final = ("qoldiq", "ostatok", "balans", "balance")

_METHOD_WORDS: Final = (
    "naqd", "naqt", "cash", "nalichn", "nal", "karta", "plastik", "plastic", "card",
    "uzcard", "humo", "visa", "mastercard", "terminal", "bank", "o'tkazma", "perechislen",
    "beznal", "click", "payme", "uzum", "apelsin", "p2p",
)  # fmt: skip
_STATUS_WORDS: Final = (
    "to'landi", "to'langan", "to'lanmagan", "to'lanadi", "kutil", "kutyapti", "reja",
    "bajarildi", "oplachen", "ne oplachen", "ojida", "plan", "paid", "unpaid", "pending",
    "planned", "done",
)  # fmt: skip
_SCHEDULE_WORDS: Final = ("har kuni", "har oy", "har hafta", "yejednevno", "yejemesyachno")

# Words in headers that point at a specific sheet kind (counted once per header cell).
_KIND_HEADER_WORDS: Final[dict[str, tuple[str, ...]]] = {
    "payroll": (
        "maosh", "oylik", "ish haqi", "иш ҳақи", "oklad", "оклад", "зарплата", "lavozim",
        "должность", "ф.и.ш.", "ф.и.о.", "фио", "xodim", "сотрудник", "tabel", "salary",
    ),
    "loan_schedule": (
        "foiz", "процент", "asosiy qarz", "qoldiq qarz", "qarz qoldig'i", "kredit",
        "погашение", "основной долг", "остаток долга", "principal", "interest", "loan",
    ),
    "counterparties": (
        "telefon", "phone", "manzil", "адрес", "address", "stir", "инн", "kontakt",
        "email", "hisob raqam",
    ),
}  # fmt: skip

# Title hints, checked in this order (the first group that matches wins).
_TITLE_HINTS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    (
        "transactions_mixed",
        ("kirim chiqim", "kirim va chiqim", "kassa daftar", "kassa kitob", "кассовая книга",
         "pul oqimi", "движение", "cash flow", "cashflow", "приход расход", "доходы и расходы"),
    ),
    (
        "payroll",
        ("ish haqi", "иш ҳақи", "зарплата", "maosh", "payroll", "xodimlar", "сотрудники",
         "ведомость", "tabel"),
    ),
    ("loan_schedule", ("kredit", "кредит", "loan", "lizing", "лизинг", "qarz", "заём", "займ")),
    (
        "ignore",
        ("izoh", "eslatma", "notes", "note", "примечан", "заметк", "readme", "yo'riqnoma",
         "qoralama", "draft"),
    ),
    (
        "counterparties",
        ("ta'minotchi", "таъминотчи", "поставщик", "kontragent", "контрагент", "supplier",
         "mijoz", "клиент", "yetkazib beruvchi", "kontakt"),
    ),
    (
        "transactions_in",
        ("kirim", "tushum", "daromad", "savdo", "sotuv", "приход", "доход", "выручка",
         "продаж", "income", "sales", "revenue"),
    ),
    (
        "transactions_out",
        ("chiqim", "xarajat", "harajat", "sarf", "расход", "затрат", "expense", "costs",
         "spending", "xarid"),
    ),
    ("payroll", ("oylik", "ойлик")),  # weak: "Oylik xarajatlar" are monthly expenses
    ("cash_balance", ("kassa", "касса", "qoldiq", "остаток", "balans", "баланс", "balance")),
    (
        "obligations_schedule",
        ("to'lovlar", "to'lov jadval", "jadval", "reja", "grafik", "график", "majburiyat",
         "schedule", "kalendar"),
    ),
)  # fmt: skip
_TITLE_WEIGHT: Final = 0.75
_TXN_SUPPORT: Final = 0.5


def _pattern(keyword: str) -> re.Pattern[str]:
    key = text_key(keyword)
    tail = r"(?![\w'])" if len(key) <= 3 else ""
    return re.compile(rf"(?<![\w']){re.escape(key)}{tail}")


_COMPILED: Final = [
    (fld, _pattern(kw), weight, len(text_key(kw)))
    for fld, keywords in _KEYWORDS.items()
    for kw, weight in keywords
]
_KIND_WORDS_COMPILED: Final = {k: [_pattern(w) for w in ws] for k, ws in _KIND_HEADER_WORDS.items()}
_TITLE_COMPILED: Final = [(kind, [_pattern(w) for w in ws]) for kind, ws in _TITLE_HINTS]
_METHOD_RE: Final = [_pattern(w) for w in _METHOD_WORDS]
_STATUS_RE: Final = [_pattern(w) for w in _STATUS_WORDS]
_SCHEDULE_RE: Final = [_pattern(w) for w in _SCHEDULE_WORDS]
_BALANCE_RE: Final = [_pattern(w) for w in _BALANCE_WORDS]


def _any(patterns: Sequence[re.Pattern[str]], key: str) -> bool:
    return any(p.search(key) for p in patterns)


def _is_row_number_header(header: str) -> bool:
    return clean_name(header).casefold() in _ROW_NUMBER_HEADERS


def keyword_field(header: object) -> tuple[str, float] | None:
    """Best (field, weight) for a header text by keywords alone; None if nothing matches."""
    text = clean_name(header)
    if not text:
        return None
    if _is_row_number_header(text):
        return ("ignore", 0.95)
    key = text_key(text)
    best: tuple[float, int, str] | None = None
    for fld, pattern, weight, length in _COMPILED:
        if pattern.search(key) and (best is None or (weight, length) > best[:2]):
            best = (weight, length, fld)
    return (best[2], best[0]) if best else None


def header_keyword_hits(cells: Sequence[object]) -> int:
    """How many cells of a row look like known column headers (used by header detection)."""
    return sum(1 for c in cells if isinstance(c, str) and keyword_field(c) is not None)


# --- sample profiling -------------------------------------------------------------------


@dataclass(slots=True)
class _Profile:
    n: int = 0  # non-empty sample cells
    dates: int = 0  # date objects and date-like text
    serials: int = 0  # numbers inside the Sheets serial range (could be dates or amounts)
    round_serials: int = 0  # ... of which multiples of 100 (more likely so'm)
    amounts: int = 0  # other numbers and amount-like text
    negatives: int = 0
    directions: int = 0
    methods: int = 0
    statuses: int = 0
    schedules: int = 0  # "10", "har oy 25", "har kuni"
    texts: int = 0
    distinct: set[str] = field(default_factory=set)
    ints: list[int] = field(default_factory=list)

    def share(self, count: int) -> float:
        return count / self.n if self.n else 0.0

    def date_share(self, *, prefer_date: bool) -> float:
        serials = self.serials if prefer_date else self.serials - self.round_serials
        return self.share(self.dates + serials)

    def amount_share(self, *, prefer_amount: bool) -> float:
        serials = self.serials if prefer_amount else self.round_serials
        return self.share(self.amounts + serials)

    @property
    def row_numbers(self) -> bool:
        """1, 2, 3, ... (a "№" column without a header)."""
        ints = self.ints
        return (
            len(ints) >= 2
            and len(ints) == self.n
            and ints[0] in (0, 1)
            and ints == list(range(ints[0], ints[0] + len(ints)))
        )


def _profile(values: Sequence[object]) -> _Profile:
    p = _Profile()
    for v in values:
        kind = classify_cell(v)
        if kind == "empty":
            continue
        p.n += 1
        if kind == "bool":
            p.statuses += 1
        elif kind == "date":
            p.dates += 1
        elif isinstance(v, int | float | Decimal):  # kind == "number"
            x = float(v)
            if SERIAL_MIN <= x <= SERIAL_MAX:
                p.serials += 1
                p.round_serials += x % 100 == 0
            else:
                p.amounts += 1
            p.negatives += x < 0
            if x.is_integer():
                p.ints.append(int(x))
                p.schedules += 1 <= x <= 31
        elif kind == "amount":
            p.amounts += 1
            amount = parse_amount(v)
            p.negatives += amount is not None and amount < 0
            p.schedules += parse_day_of_month(v) is not None and len(str(v).strip()) <= 2
        else:
            key = text_key(v)
            p.texts += 1
            p.distinct.add(key)
            p.directions += parse_direction(v) is not None
            p.methods += _any(_METHOD_RE, key)
            p.statuses += _any(_STATUS_RE, key)
            p.schedules += parse_day_of_month(v) is not None or _any(_SCHEDULE_RE, key)
    return p


# --- per-column decision ----------------------------------------------------------------


@dataclass(slots=True)
class _Col:
    index: int
    header: str
    key: str
    field: str
    confidence: float
    direction: Direction | None
    profile: _Profile


def _cap(value: float, top: float = 0.97) -> float:
    return round(max(0.0, min(top, value)), 2)


def _from_values(p: _Profile) -> tuple[str, float]:
    if p.share(p.directions) >= 0.7:
        return ("direction", 0.75)
    if p.date_share(prefer_date=False) >= 0.7:
        return ("date", 0.65)
    if p.share(p.methods) >= 0.7:
        return ("method", 0.7)
    if p.share(p.statuses) >= 0.7:
        return ("status", 0.6)
    if p.row_numbers:
        return ("ignore", 0.7)
    if p.amount_share(prefer_amount=False) >= 0.7:
        return ("amount", 0.6)
    if p.share(p.texts) >= 0.7:
        if len(p.distinct) <= max(2, p.texts // 2):
            return ("category", 0.45)  # few repeated words: looks like categories
        return ("note", 0.4)
    return ("ignore", 0.4)


def _decide(header: str, p: _Profile) -> tuple[str, float, Direction | None]:
    """(field, confidence, direction) for one column."""
    kw = keyword_field(header)
    hdir = parse_direction(header) if header else None
    if p.n == 0:  # header only (or an empty column): trust the words a bit less
        if kw is None:
            return ("ignore", 0.9 if not header else 0.5, None)
        fld, w = kw
        if fld == "direction" and hdir:  # "Kirim" alone names one flow: its sums, probably
            return ("amount", 0.7, hdir)
        top = 0.7 if fld == "status" else 0.85
        return (fld, _cap(w - 0.1, top), hdir if fld == "amount" else None)
    if kw is None:
        fld, conf = _from_values(p)
        return (fld, _cap(conf, 0.5 if not header else 0.97), None)

    fld, w = kw
    amounts = p.amount_share(prefer_amount=True)
    if fld == "direction":
        if amounts >= 0.6 and hdir:  # a "Kirim" / "Chiqim" column full of sums
            return ("amount", 0.9, hdir)
        if p.share(p.directions) >= 0.6:
            return ("direction", _cap(max(w, 0.85) + 0.05), None)
        if p.share(p.methods) >= 0.6:  # "Turi": Naqd / Karta
            return ("method", 0.75, None)
        if amounts >= 0.6:
            return ("amount", 0.6, None)
        return ("direction", _cap(w * 0.7), None)
    if fld == "amount":
        if amounts >= 0.6:
            return ("amount", _cap(w + 0.05), hdir)
        if p.date_share(prefer_date=False) >= 0.6:
            return ("date", 0.5, None)
        return ("amount", _cap(w * 0.6), hdir)
    if fld in ("date", "due_date"):
        if p.date_share(prefer_date=True) >= 0.6:
            return (fld, _cap(w + 0.05), None)
        if fld == "due_date" and p.share(p.schedules) >= 0.6:  # "10", "har oy 25"
            return (fld, _cap(w - 0.05, 0.9), None)
        if p.amount_share(prefer_amount=False) >= 0.6:
            return (fld, 0.4, None)
        return (fld, _cap(w * 0.6), None)
    if fld == "status":
        return ("status", _cap(w, 0.7), None)  # paid vs planned: always confirm
    if fld == "method":
        if p.share(p.methods) >= 0.5:
            return ("method", _cap(w + 0.05), None)
        if amounts >= 0.6:  # "Naqd" / "Karta" columns holding sums
            return ("amount", 0.7, hdir)
        if p.share(p.texts) >= 0.6:
            return ("method", _cap(w - 0.1), None)
        return ("method", _cap(w * 0.6), None)
    if fld == "ignore":
        return ("ignore", _cap(w), None)
    # category / counterparty / note: free text expected
    if p.share(p.texts) >= 0.6:
        return (fld, _cap(w), None)
    return (fld, _cap(w * 0.6), None)


def _loser_confidence(winner: float, loser: float) -> float:
    """How sure we are that a weaker duplicate column should be ignored."""
    return _cap(min(0.85, max(0.5, winner - loser + 0.5)))


def _resolve(cols: list[_Col]) -> None:
    """One column per field (split Kirim/Chiqim amount columns are the exception)."""
    amounts = [c for c in cols if c.field == "amount"]
    flows = [c for c in amounts if c.direction is not None]
    plain = [c for c in amounts if c.direction is None]
    if flows and plain:
        top = max(c.confidence for c in flows)
        for c in plain:  # a running "Qoldiq" next to Kirim/Chiqim is not a flow
            balance = _any(_BALANCE_RE, c.key)
            c.field = "ignore"
            c.confidence = 0.8 if balance else _loser_confidence(top, c.confidence)
    elif len(plain) > 1:
        _keep_best(plain, "ignore")
    for fld in ("date", "due_date", "direction", "method", "status", "category", "counterparty"):
        same = [c for c in cols if c.field == fld]
        if len(same) > 1:
            _keep_best(same, "note" if fld in ("category", "counterparty") else "ignore")


def _keep_best(cols: list[_Col], fallback: str) -> None:
    best = max(cols, key=lambda c: (c.confidence, -c.index))
    for c in cols:
        if c is not best:
            loser = c.confidence
            c.field, c.direction = fallback, None
            c.confidence = (
                _loser_confidence(best.confidence, loser)
                if fallback == "ignore"
                else min(loser, 0.5)
            )


# --- sheet kind -------------------------------------------------------------------------


def _noisy_or(*ps: float) -> float:
    miss = 1.0
    for p in ps:
        miss *= 1.0 - p
    return 1.0 - miss


def title_kind(title: str | None) -> str | None:
    """Sheet kind hinted by the tab title ("Kirim", "Oylik", "NBU kredit", "Izohlar"...)."""
    key = text_key(title or "")
    if not key:
        return None
    in_word = any(_any(ps, key) for kind, ps in _TITLE_COMPILED if kind == "transactions_in")
    out_word = any(_any(ps, key) for kind, ps in _TITLE_COMPILED if kind == "transactions_out")
    if in_word and out_word:
        return "transactions_mixed"
    for kind, patterns in _TITLE_COMPILED:
        if _any(patterns, key):
            return kind
    return None


def _kind_scores(cols: list[_Col]) -> tuple[dict[str, float], bool]:
    """Structural evidence per sheet kind from the mapped columns, plus "looks like txns"."""
    by_field: dict[str, list[_Col]] = {}
    for c in cols:
        by_field.setdefault(c.field, []).append(c)
    hits = {
        kind: sum(1 for c in cols if c.key and _any(ps, c.key))
        for kind, ps in _KIND_WORDS_COMPILED.items()
    }
    amounts = by_field.get("amount", [])
    flows_in = [c for c in amounts if c.direction == "in"]
    flows_out = [c for c in amounts if c.direction == "out"]
    plain = [c for c in amounts if c.direction is None]
    dates = by_field.get("date", [])
    dues = by_field.get("due_date", [])
    direction = by_field.get("direction", [])
    has_date = bool(dates)
    due_dates = any(c.profile.date_share(prefer_date=True) >= 0.6 for c in dues)
    counterparty = "counterparty" in by_field

    scores: dict[str, float] = {}
    if hits["payroll"]:
        scores["payroll"] = 0.85 if hits["payroll"] >= 2 else 0.55
    if hits["loan_schedule"]:
        scores["loan_schedule"] = 0.85 if hits["loan_schedule"] >= 2 else 0.55
    if flows_in and flows_out:
        scores["transactions_mixed"] = 0.9
    elif direction and any(c.profile.share(c.profile.directions) >= 0.6 for c in direction):
        scores["transactions_mixed"] = 0.85
    elif flows_in and not plain:
        scores["transactions_in"] = 0.7
    elif flows_out and not plain:
        scores["transactions_out"] = 0.7
    if plain and not flows_in and not flows_out and not direction:
        if any(_any(_BALANCE_RE, c.key) for c in plain) and not hits["loan_schedule"]:
            scores["cash_balance"] = 0.7
    specific = hits["payroll"] >= 2 or hits["loan_schedule"] >= 1
    if counterparty and not has_date and not due_dates and not specific:
        if hits["counterparties"] or not amounts:
            scores["counterparties"] = 0.75
    if due_dates and amounts and not has_date and not specific and not hits["payroll"]:
        scores["obligations_schedule"] = 0.65
    if not amounts and not has_date and not dues and not counterparty:
        scores["ignore"] = 0.6
    return scores, has_date and bool(amounts)


def _guess_kind(cols: list[_Col], title: str | None) -> tuple[str, float]:
    scores, txn_like = _kind_scores(cols)
    hinted = title_kind(title)
    if hinted:
        support = _TXN_SUPPORT if hinted in TRANSACTION_KINDS and txn_like else 0.0
        scores[hinted] = _noisy_or(scores.get(hinted, 0.0), _TITLE_WEIGHT, support)
    elif txn_like and max(scores.values(), default=0.0) < 0.6:
        negatives = any(c.profile.negatives for c in cols if c.field == "amount")
        if negatives:
            scores["transactions_mixed"] = 0.6
        elif any(c.field in ("category", "counterparty") for c in cols):
            scores["transactions_out"] = 0.5  # categories / payees: usually an expense log
        else:
            scores["transactions_mixed"] = 0.45  # sign decides; the person confirms
    if not scores:
        return ("ignore", 0.5)
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], SHEET_KINDS.index(kv[0])))
    best, top = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    return best, _cap(max(0.3, top - 0.3 * second))


# --- entry point ------------------------------------------------------------------------


def guess_mapping(
    headers: Sequence[object],
    samples: Sequence[Sequence[object]],
    title: str | None = None,
) -> MappingGuess:
    """Column fields + sheet kind from the header row, sample data rows and the tab title."""
    width = max([len(headers), *(len(r) for r in samples)], default=0)
    cols: list[_Col] = []
    for i in range(width):
        header = clean_name(headers[i]) if i < len(headers) else ""
        p = _profile([r[i] if i < len(r) else None for r in samples])
        fld, conf, direction = _decide(header, p)
        cols.append(_Col(i, header, text_key(header), fld, conf, direction, p))
    _resolve(cols)
    kind, kind_conf = _guess_kind(cols, title)
    return MappingGuess(
        sheet_kind=kind,
        kind_confidence=kind_conf,
        columns=[ColumnGuess(c.index, c.header, c.field, c.confidence, c.direction) for c in cols],
    )
