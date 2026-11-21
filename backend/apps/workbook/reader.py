"""Shared workbook reader: every sheet (hidden too), layout + header detection, full data range.

Used by ingestion (inventory on the Sources page) and by Fayl tahlili (DuckDB tables).
Deterministic, no LLM. No row caps: data ends after 50 consecutive empty key cells.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

SCAN_ROWS = 15
SCAN_COLS = 12
EMPTY_STOP = 50
_MONTH = re.compile(
    r"^(yan|fev|mar|apr|may|iyun|iyul|avg|sen|okt|noy|dek|jan|feb|jun|jul|aug|sep|oct|nov|dec)\w*\.?\s+\d{4}$",
    re.I,
)

# "Restoran moliyaviy modeli" family: sheet title -> (role, layout)
TEMPLATE: dict[str, tuple[str, str]] = {
    "bosh sahifa": ("report", "wide_period + key_value"),
    "qo'llanma": ("ignore", "text"),
    "sozlamalar": ("master_data", "key_value + multi_table"),
    "smena": ("journal_cash", "row_table"),
    "sotuv": ("journal_sales", "row_table"),
    "kirim": ("journal_purchase", "row_table"),
    "kassa": ("journal_cash", "row_table"),
    "hisoblash": ("journal_accrual", "row_table"),
    "ish haqi": ("journal_accrual", "row_table"),
    "hisobdan chiqarish": ("journal_writeoff", "row_table"),
    "inventarizatsiya": ("journal_inventory", "row_table"),
    "spravochnik": ("master_data", "multi_table"),
    "kontragentlar": ("master_data", "row_table + wide_period"),
    "mahsulotlar": ("master_data", "row_table"),
    "menyu": ("master_data", "row_table + wide_period"),
    "texkarta": ("master_data", "row_table"),
    "yarim tayyor": ("master_data", "row_table + wide_period"),
    "yt retsept": ("master_data", "row_table"),
    "asosiy vositalar": ("master_data", "row_table + wide_period"),
    "foyda-zarar": ("report", "wide_period"),
    "pul oqimi": ("report", "wide_period"),
    "balans": ("report", "wide_period"),
    "kunlik hisobot": ("report", "wide_period"),
    "ombor hisoboti": ("report", "row_table"),
    "menyu tahlili": ("report", "row_table"),
    "reja-fakt": ("report", "multi_table"),
    "fin reja": ("plan", "multi_table"),
    "tekshiruv": ("ignore", "row_table"),
    "zaxira": ("ignore", "row_table"),
}
ROLE_LABELS = {
    "report": "Hisobot",
    "ignore": "E'tiborsiz",
    "master_data": "Ma'lumotnoma",
    "journal_cash": "Pul jurnali",
    "journal_sales": "Sotuv jurnali",
    "journal_purchase": "Xarid jurnali",
    "journal_accrual": "Hisoblash jurnali",
    "journal_writeoff": "Hisobdan chiqarish",
    "journal_inventory": "Inventarizatsiya",
    "plan": "Reja",
    "journal": "Jurnal",
    "table": "Jadval",
}


def norm_title(t: str) -> str:
    return re.sub(r"[‘’ʻʼ`]", "'", t).strip().lower()


def col_letter(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _empty(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _is_text(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip()) and not re.fullmatch(r"[\d\s.,%-]+", v.strip())


def _is_date(v: Any) -> bool:
    return isinstance(v, (date, datetime)) or (isinstance(v, str) and bool(_MONTH.match(v.strip())))


@dataclass
class Column:
    name: str
    index: int
    type: str = "text"  # text | number | date
    is_computed: bool = False


@dataclass
class DetectedTable:
    sheet: str
    name: str
    layout: str
    role: str
    header_row: int  # 1-based, 0 = none
    first_col: int  # 0-based
    columns: list[Column] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    hidden: bool = False
    period_axis: dict[int, str] | None = None  # column index -> ISO period start
    note: str = ""

    @property
    def first_col_letter(self) -> str:
        return col_letter(self.first_col)


@dataclass
class WorkbookModel:
    name: str
    tables: list[DetectedTable]
    sheet_names: list[str]
    template: str = ""
    notes: list[str] = field(default_factory=list)


def _header_row(rows: list[list[Any]]) -> int | None:
    best, best_n = None, 0
    for i, r in enumerate(rows[:SCAN_ROWS]):
        n = sum(1 for v in r[: SCAN_COLS + 20] if _is_text(v) and len(str(v)) < 60)
        if n >= 3 and n > best_n:
            best, best_n = i, n
    return best


def _period_axis(rows: list[list[Any]], h: int) -> dict[int, str]:
    axis: dict[int, str] = {}
    for rr in range(max(0, h - 3), h + 1):
        for j, v in enumerate(rows[rr]):
            if isinstance(v, (date, datetime)):
                axis.setdefault(j, (v.date() if isinstance(v, datetime) else v).isoformat())
    if len(axis) < 3:
        hdr = rows[h]
        n = sum(1 for v in hdr if isinstance(v, str) and _MONTH.match(v.strip()))
        if n < 3:
            return {}
    return axis


def _col_type(values: list[Any]) -> str:
    vals = [v for v in values[:300] if not _empty(v)]
    if not vals:
        return "number"
    d = sum(1 for v in vals if isinstance(v, (date, datetime)))
    n = sum(1 for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool))
    if d >= len(vals) * 0.6:
        return "date"
    if n >= len(vals) * 0.6:
        return "number"
    return "text"


def detect_sheet(title: str, rows: list[list[Any]], hidden: bool = False) -> DetectedTable:
    tmpl = TEMPLATE.get(norm_title(title))
    h = _header_row(rows)
    if h is None:
        nonempty = [r for r in rows if any(not _empty(c) for c in r)]
        longtext = sum(1 for r in nonempty for c in r if isinstance(c, str) and len(c) > 60)
        layout = "text" if longtext > len(nonempty) * 0.3 else "key_value"
        role, layout = tmpl if tmpl else ("ignore" if layout == "text" else "master_data", layout)
        return DetectedTable(title, title, layout, role, 0, 1, rows=nonempty, hidden=hidden)
    header = rows[h]
    first_col = next((j for j, v in enumerate(header) if not _empty(v)), 0)
    last = max((j for j, v in enumerate(header) if not _empty(v)), default=first_col)
    names: list[str] = []
    seen: dict[str, int] = {}
    for j in range(first_col, last + 1):
        v = header[j]
        base = str(v).strip() if not _empty(v) else f"col_{col_letter(j)}"
        if isinstance(v, (date, datetime)):
            base = (v.date() if isinstance(v, datetime) else v).isoformat()
        k = seen.get(base, 0)
        seen[base] = k + 1
        names.append(base if k == 0 else f"{base}_{k + 1}")
    # data: until 50 consecutive empty key cells (key = first header column)
    data: list[list[Any]] = []
    empty_run = 0
    for r in rows[h + 1 :]:
        key = r[first_col] if first_col < len(r) else None
        if _empty(key):
            empty_run += 1
            if empty_run >= EMPTY_STOP:
                break
            continue
        empty_run = 0
        data.append([r[j] if j < len(r) else None for j in range(first_col, last + 1)])
    cols = []
    for k, nm in enumerate(names):
        cols.append(Column(nm, first_col + k, _col_type([row[k] for row in data])))
    # computed columns heuristic: template sheets have inputs left, formulas right; mark
    # columns whose header holds "(tanl" / "jami" / "%" after the first blank gap
    axis = _period_axis(rows, h)
    if tmpl:
        role, layout = tmpl
    else:
        layout = "wide_period" if axis else "row_table"
        types = {c.type for c in cols}
        role = "journal" if "date" in types and "number" in types else "table"
    return DetectedTable(
        title, title, layout, role, h + 1, first_col, cols, data, hidden, axis or None
    )


def read_xlsx(blob: bytes, name: str = "") -> WorkbookModel:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
    tables, names, notes = [], [], []
    try:
        for ws in wb.worksheets:
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            names.append(ws.title)
            hidden = ws.sheet_state != "visible"
            tables.append(detect_sheet(ws.title, rows, hidden))
    finally:
        wb.close()
    return _model(name, tables, names, notes)


def read_csv(blob: bytes, name: str = "") -> WorkbookModel:
    import csv

    text = blob.decode("utf-8-sig", errors="replace")
    dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t") if text else csv.excel
    rows: list[list[Any]] = []
    for r in csv.reader(io.StringIO(text), dialect):
        out: list[Any] = []
        for c in r:
            c2 = c.replace("\xa0", "").replace(" ", "")
            try:
                out.append(
                    float(c2.replace(",", ".")) if c2 and re.fullmatch(r"-?[\d.,]+", c2) else c
                )
            except ValueError:
                out.append(c)
        rows.append(out)
    t = detect_sheet(name or "CSV", rows)
    return _model(name, [t], [t.sheet], [])


def read_sheets(sheets: list[Any], name: str = "") -> WorkbookModel:
    """From ingestion SheetData (title, rows)."""
    tables = [detect_sheet(s.title, s.rows) for s in sheets]
    return _model(name, tables, [s.title for s in sheets], [])


def read_any(blob: bytes, filename: str) -> WorkbookModel:
    low = filename.lower()
    if low.endswith(".csv"):
        return read_csv(blob, filename)
    if low.endswith(".xls"):
        try:
            import xlrd  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ValueError("xls_unsupported") from exc
        book = xlrd.open_workbook(file_contents=blob)
        tables, names = [], []
        for sh in book.sheets():
            rows = [sh.row_values(i) for i in range(sh.nrows)]
            names.append(sh.name)
            tables.append(detect_sheet(sh.name, rows))
        return _model(filename, tables, names, [])
    return read_xlsx(blob, filename)


def _model(
    name: str, tables: list[DetectedTable], names: list[str], notes: list[str]
) -> WorkbookModel:
    known = sum(1 for n in names if norm_title(n) in TEMPLATE)
    template = "Restoran moliyaviy modeli" if known >= max(8, len(names) * 0.7) else ""
    for t in tables:
        if t.header_row and not t.rows:
            notes.append(f"{t.sheet}: sarlavha bor, ma'lumot qatori yo'q")
        if t.hidden:
            notes.append(f"{t.sheet}: yashirin varaq")
    return WorkbookModel(name, tables, names, template, notes)


def inventory(model: WorkbookModel) -> list[dict[str, Any]]:
    out = []
    for t in model.tables:
        dates = [
            row[c.index - t.first_col]
            for c in t.columns
            if c.type == "date"
            for row in t.rows
            if isinstance(row[c.index - t.first_col], (date, datetime))
        ][:100000]
        out.append(
            {
                "sheet": t.sheet,
                "role": t.role,
                "role_label": ROLE_LABELS.get(t.role, t.role),
                "layout": t.layout,
                "header": f"{t.header_row} / {t.first_col_letter}" if t.header_row else "—",
                "rows": len(t.rows),
                "hidden": t.hidden,
                "from": min(dates).date().isoformat()
                if dates and isinstance(min(dates), datetime)
                else (min(dates).isoformat() if dates else None),
                "to": max(dates).date().isoformat()
                if dates and isinstance(max(dates), datetime)
                else (max(dates).isoformat() if dates else None),
            }
        )
    return out
