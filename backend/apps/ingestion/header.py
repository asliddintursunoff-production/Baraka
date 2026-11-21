"""Find the header row of a messy sheet, and fingerprint it (pure, no Django).

Rule: the header is the first row with >= 2 non-empty *text* cells (more text than data)
where most of the following non-empty rows contain at least one number/date/amount-like
cell. Leading empty rows and title rows (a single non-empty cell, e.g.
"Navro'z Kafe — kirimlar") are skipped. Refinements:

- a row with >= 2 known header words ("Kontragent", "Telefon", "Izoh") is accepted even if
  most rows below are text: a supplier list is a table, not notes;
- a two-cell row above a wider table ("Navro'z Kafe | Noyabr", "Manzil | Toshkent") is a
  title / key-value line, not the header, unless both cells are header words;
- a title row directly above the real header is skipped when the next row has more header
  words (or the title has none and the next row is wider);
- once a candidate was turned down for having mostly text below (notes), a later row must
  contain a header word: one dated line at the end of the notes does not make a table.

A sheet holding only a header row (possibly under a title) returns that row.
An all-text notes sheet ("Izohlar": one sentence per row) returns ``None``: there is no
column structure to map, and the caller treats ``None`` as "ignore this sheet". Returning
row 0 instead would invent a header out of the first note.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final

from .heuristics import header_keyword_hits
from .normalize import classify_cell, clean_name, is_blank

_MAX_SCAN: Final = 30  # the header is among the first 30 non-empty rows
_WINDOW: Final = 20  # rows below a candidate that are inspected
_DIGIT: Final = re.compile("[0-9]")


@dataclass(frozen=True, slots=True)
class _Row:
    non_empty: int
    text: int
    data: int

    @property
    def is_candidate(self) -> bool:
        return self.text >= 2 and self.text > self.data


def _digit_heavy(value: object) -> bool:
    """Phone numbers, ids: "+998 90 123 45 67", "INV-00123"."""
    text = clean_name(value).replace(" ", "")
    digits = len(_DIGIT.findall(text))
    return digits >= 3 and digits * 2 >= len(text)


def _row(cells: Sequence[object]) -> _Row:
    non_empty = text = data = 0
    for c in cells:
        kind = classify_cell(c)
        if kind == "empty":
            continue
        non_empty += 1
        if kind == "text" and not _digit_heavy(c):
            text += 1
        else:
            data += 1
    return _Row(non_empty, text, data)


def detect_header(rows: Sequence[Sequence[object]]) -> int | None:
    """0-based index of the header row, or None (no table: notes, titles only, empty)."""
    filled: list[int] = []
    for i, r in enumerate(rows):
        if any(not is_blank(c) for c in r):
            filled.append(i)
            if len(filled) > _MAX_SCAN + _WINDOW:
                break
    cache: dict[int, _Row] = {}

    def info(i: int) -> _Row:
        if i not in cache:
            cache[i] = _row(rows[i])
        return cache[i]

    text_block = False  # a candidate was turned down: we are inside lines of plain text
    for pos, i in enumerate(filled[:_MAX_SCAN]):
        row = info(i)
        if not row.is_candidate:
            continue
        below = filled[pos + 1 : pos + 1 + _WINDOW]
        if not below:  # header-only sheet; but not the last line of a notes sheet
            return None if text_block else i
        hits = header_keyword_hits(rows[i])
        data_rows = [j for j in below if info(j).data]
        if len(data_rows) * 2 <= len(below) and hits < 2:
            text_block = True
            continue
        if text_block and not hits:
            continue  # below notes, a table needs a recognizable header
        widths = sorted(info(j).non_empty for j in data_rows)
        if widths and row.non_empty == 2 and hits < 2 and widths[len(widths) // 2] > 2:
            continue  # "Manzil | Toshkent" or a two-cell title above a wider table
        nxt = info(below[0])
        if nxt.is_candidate and not nxt.data:
            nxt_hits = header_keyword_hits(rows[below[0]])
            if nxt_hits > hits or (hits == 0 and nxt.non_empty > row.non_empty):
                continue  # a title line sitting on top of the real header
        return i
    return None


def _signature_text(value: object) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return clean_name(value).casefold()


def header_signature(headers: Sequence[object]) -> str:
    """Stable sha256 (64 hex chars) of the normalized header texts.

    Case, extra/NBSP spaces, apostrophe variants and trailing empty cells (Sheets trims
    them, openpyxl pads them) do not change it; renaming, adding or moving a column does.
    """
    texts = [_signature_text(h) for h in headers]
    while texts and not texts[-1]:
        texts.pop()
    return hashlib.sha256("\x1f".join(texts).encode("utf-8")).hexdigest()
