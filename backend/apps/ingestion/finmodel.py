"""Restaurant financial-model workbooks ("Restoran FinModel": Kassa, Smena, Kirim, Spravochnik…).

Such a workbook is a full accounting model, not a simple ledger. Cash really moves only in:
  Kassa        every money movement: Kirim / Chiqim / O'tkazma, item (Modda), signed amount.
               O'tkazma = transfer between own accounts -> skipped (net zero).
  Smena        daily Z-report: payments received (cash + terminal + Click + Payme).
  Kirim        product purchases; only rows paid immediately ("Darhol to'langan hisob") move cash
               (credit purchases are paid later through Kassa "Yetkazib beruvchiga to'lov").
  Spravochnik  cash accounts with their opening balances ("Boshl. qoldiq").
Sotuv (dish-level sales) and Ish haqi (payroll accruals) are accruals already paid through
Smena/Kassa: reading them too would double count, so they are ignored, like all report tabs.

Detection is per sheet, by header names, so the mapping survives re-syncs and reordering.
Future fixed payments (payroll, rent, utilities, tax, loan, fixed services) are projected
from the last three months of Kassa history, because such workbooks have no payment plan.
"""

from __future__ import annotations

import calendar
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db.models import Max

from apps.finance.models import CashAccount, Obligation, Transaction

from .header import header_signature
from .models import DataIssue, RawRow
from .normalize import InvalidDate, parse_amount, parse_date, text_key
from .readers import SheetData

if TYPE_CHECKING:
    from .mapping import SheetProposal
    from .pipeline import Ingestor

KASSA, SMENA, PURCHASES, ACCOUNTS = (
    "finmodel_kassa",
    "finmodel_smena",
    "finmodel_purchases",
    "finmodel_accounts",
)
FINMODEL_KINDS = {
    KASSA: "Kassa — barcha pul harakatlari",
    SMENA: "Smena — kunlik savdo tushumi",
    PURCHASES: "Kirim — darhol to'langan xaridlar",
    ACCOUNTS: "Pul hisoblari — boshlang'ich qoldiq",
}
# fixed monthly payments projected forward (also excluded from the variable-cost ratio)
FIXED = ("payroll", "rent", "kommunal", "tax", "loan", "doimiy")
FIXED_LABEL = {
    "payroll": "Ish haqi",
    "rent": "Ijara",
    "kommunal": "Kommunal xizmatlar",
    "tax": "Soliq",
    "loan": "Kredit to'lovi",
    "doimiy": "Doimiy xarajat",
}
CRITICAL = {"payroll", "rent", "tax", "loan"}
# cash that is neither sales nor operating cost: never in the revenue model or the cost ratio
NON_OPERATING = ("financing", "capex", "dividend", "avans")
PROJECT_MONTHS = 4
LOOKBACK_MONTHS = 3

# Kassa "Modda" (item) -> category; first match wins (text_key form)
MODDA_CATEGORY: tuple[tuple[str, str], ...] = (
    ("ish haqi", "payroll"),
    ("kunbay", "kunbay"),
    ("ijara", "rent"),
    ("kommunal", "kommunal"),
    ("internet", "doimiy"),
    ("aloqa", "doimiy"),
    ("marketing", "doimiy"),
    ("reklama", "doimiy"),
    ("soliq", "tax"),
    ("kredit", "loan"),
    ("qarz qaytar", "loan"),
    ("yetkazib beruvchi", "xom ashyo"),
    ("qadoq", "qadoq"),
    ("taksi", "yetkazish"),
    ("yetkazish", "yetkazish"),
    ("xo'jalik", "xo'jalik"),
    ("bank komiss", "bank komissiyasi"),
    ("ta'mir", "ta'mirlash"),
    ("asosiy vosita", "capex"),
    ("dividend", "dividend"),
    ("avans", "avans"),
    ("hisoblangan xarajat", "doimiy"),
)


# --- detection -------------------------------------------------------------------------------
def _keys(row: list[Any]) -> list[str]:
    return [text_key(c) if c not in (None, "") else "" for c in row]


def _find_header(rows: list[list[Any]], *needles: str, scan: int = 15) -> int | None:
    for i, row in enumerate(rows[:scan]):
        keys = _keys(row)
        if all(any(k.startswith(n) for k in keys) for n in needles):
            return i
    return None


def _col(header: list[Any], *starts: str) -> int | None:
    keys = _keys(header)
    for s in starts:
        for i, k in enumerate(keys):
            if k == s:
                return i
    for s in starts:
        for i, k in enumerate(keys):
            if k.startswith(s):
                return i
    return None


@dataclass(frozen=True)
class Detected:
    kind: str  # one of FINMODEL_KINDS or "ignore"
    header_row: int  # 0-based


def detect(sheet: SheetData) -> Detected | None:
    rows = sheet.rows
    if (h := _find_header(rows, "sana", "turi", "modda", "summa so'm")) is not None:
        return Detected(KASSA, h)
    if (h := _find_header(rows, "sana", "to'lovlar jami")) is not None or (
        h := _find_header(rows, "sana", "z hisobot", "terminal")
    ) is not None:
        return Detected(SMENA, h)
    if (h := _find_header(rows, "sana", "darhol to'langan")) is not None:
        return Detected(PURCHASES, h)
    for i, row in enumerate(rows[:15]):
        keys = _keys(row)
        if "hisob nomi" in keys and any(k.startswith("boshl") for k in keys):
            return Detected(ACCOUNTS, i)
    # accruals already paid through Smena / Kassa: reading them would double count
    if (
        _find_header(rows, "sana", "taom", "miqdor") is not None
        or _find_header(rows, "oklad", "jshds") is not None
    ):
        return Detected("ignore", 0)
    return None


def proposal(sheet: SheetData) -> SheetProposal | None:
    from .mapping import ColumnProposal, SheetProposal

    d = detect(sheet)
    if d is None:
        return None
    if d.kind == "ignore":
        return SheetProposal(sheet.title, 1, "", 0, "ignore", 0.95)
    header = sheet.rows[d.header_row]
    data = [r for r in sheet.rows[d.header_row + 1 :] if any(c not in (None, "") for c in r)]
    fields = {
        KASSA: (
            ("sana", "date"),
            ("turi", "direction"),
            ("modda", "category"),
            ("kontragent", "counterparty"),
            ("summa so'm", "amount"),
        ),
        SMENA: (("sana", "date"), ("to'lovlar jami", "amount")),
        PURCHASES: (
            ("sana", "date"),
            ("yetkazib beruvchi", "counterparty"),
            ("to'lov so'm", "amount"),
            ("darhol to'langan", "method"),
        ),
        ACCOUNTS: (("hisob nomi", "note"), ("boshl", "amount")),
    }[d.kind]
    cols = []
    for start, field_name in fields:
        i = _col(header, start)
        if i is None:
            continue
        sample = next((str(r[i])[:40] for r in data if i < len(r) and r[i] not in (None, "")), "")
        cols.append(ColumnProposal(i, str(header[i]), sample, field_name, 1.0))
    return SheetProposal(
        sheet.title,
        d.header_row + 1,
        header_signature([str(c or "") for c in header]),
        len(data),
        d.kind,
        1.0,
        cols,
    )


# --- ingestion -------------------------------------------------------------------------------
def _date(v: Any, today: date) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return parse_date(v, today=today)
    except InvalidDate:
        return None


def kassa_category(modda: str, turi: str, faoliyat: str, kontragent: str) -> str:
    m, f, k = text_key(modda), text_key(faoliyat), text_key(kontragent)
    if text_key(turi).startswith("kirim"):
        return "financing" if f.startswith(("moliyaviy", "investitsion")) else "savdo"
    if "ijara" in k and "hisoblangan" in m:
        return "rent"
    for needle, cat in MODDA_CATEGORY:
        if needle in m:
            return cat
    return "financing" if f.startswith(("moliyaviy", "investitsion")) else "boshqa"


def _facts(
    ing: Ingestor, kind: str, sheet: SheetData, h: int
) -> list[tuple[int, list[Any], dict[str, Any]]]:
    """[(sheet row number, raw row, transaction fields)] for one finmodel sheet."""
    header = sheet.rows[h]
    out: list[tuple[int, list[Any], dict[str, Any]]] = []
    c = {
        name: _col(header, *starts)
        for name, starts in {
            "date": ("sana",),
            "turi": ("turi",),
            "modda": ("modda",),
            "kontragent": ("kontragent",),
            "signed": ("summa so'm",),
            "faoliyat": ("faoliyat",),
            "izoh": ("izoh",),
            "hisob": ("hisob",),
            "total": ("to'lovlar jami",),
            "supplier": ("yetkazib beruvchi",),
            "paid_from": ("darhol to'langan",),
            "paid": ("to'lov so'm",),
            "product": ("mahsulot",),
        }.items()
    }

    def cell(row: list[Any], key: str) -> Any:
        i = c.get(key)
        return row[i] if i is not None and i < len(row) else None

    pay_cols = [
        i
        for i, k in enumerate(_keys(header))
        if k.startswith(("naqd pos", "terminal", "click", "payme", "boshqa"))
    ]
    for offset, row in enumerate(sheet.rows[h + 1 :]):
        row_no = h + 2 + offset
        d = _date(cell(row, "date"), ing.today)
        if d is None:
            continue
        if kind == KASSA:
            turi = str(cell(row, "turi") or "")
            signed = parse_amount(cell(row, "signed"))
            if text_key(turi).startswith("o'tkazma") or not signed:
                continue
            modda = str(cell(row, "modda") or "")
            fields = {
                "amount": abs(signed),
                "direction": "in" if signed > 0 else "out",
                "category": kassa_category(
                    modda,
                    turi,
                    str(cell(row, "faoliyat") or ""),
                    str(cell(row, "kontragent") or ""),
                ),
                "counterparty": cell(row, "kontragent"),
                "method": str(cell(row, "hisob") or "")[:32],
                "note": " · ".join(x for x in (modda, str(cell(row, "izoh") or "")) if x)[:255],
            }
        elif kind == SMENA:
            total = parse_amount(cell(row, "total"))
            if total is None:
                total = sum(
                    (parse_amount(row[i]) or Decimal(0) for i in pay_cols if i < len(row)),
                    Decimal(0),
                )
            if not total or total <= 0:
                continue
            fields = {
                "amount": total,
                "direction": "in",
                "category": "savdo",
                "counterparty": None,
                "method": "kassa",
                "note": "Smena tushumi",
            }
        else:  # PURCHASES: only rows paid at once move cash
            paid = parse_amount(cell(row, "paid"))
            if cell(row, "paid_from") in (None, "") or not paid or paid <= 0:
                continue
            fields = {
                "amount": paid,
                "direction": "out",
                "category": "xom ashyo",
                "counterparty": cell(row, "supplier"),
                "method": str(cell(row, "paid_from"))[:32],
                "note": str(cell(row, "product") or "")[:255],
            }
        fields["txn_date"] = d
        out.append((row_no, row, fields))
    return out


def ingest(ing: Ingestor, sheet: SheetData, kind: str, header_row_1based: int) -> None:
    """Row-diffed ingestion (same contract as Ingestor.ingest_rows_sheet)."""
    from .pipeline import json_safe, row_hash

    h = max(0, header_row_1based - 1)
    if kind == ACCOUNTS:
        ingest_accounts(ing, sheet, h)
        return
    facts = _facts(ing, kind, sheet, h)
    ing.stats.data_rows += len(facts)
    existing = {
        r.row_hash: r
        for r in RawRow.objects.filter(
            source=ing.source, sheet_title=sheet.title, status=RawRow.Status.ACTIVE
        )
    }
    seen: set[str] = set()
    added = 0
    new_txns: list[Transaction] = []
    for row_no, row, f in facts:
        hsh = row_hash(sheet.title, [row_no, *row])
        seen.add(hsh)
        if hsh in existing:
            continue
        raw = RawRow.objects.create(
            business=ing.business,
            source=ing.source,
            sheet_title=sheet.title,
            row_index=row_no,
            row_hash=hsh,
            values=[json_safe(v) for v in row],
        )
        cp = ing.counterparty(f.pop("counterparty")) if f.get("counterparty") else None
        f.pop("counterparty", None)
        new_txns.append(Transaction(business=ing.business, counterparty=cp, raw_row=raw, **f))
        added += 1
    Transaction.objects.bulk_create(new_txns, batch_size=500)
    gone = [r.pk for hsh, r in existing.items() if hsh not in seen]
    if gone:
        Transaction.objects.filter(raw_row_id__in=gone).delete()
        DataIssue.objects.filter(raw_row_id__in=gone, status=DataIssue.Status.OPEN).update(
            status=DataIssue.Status.RESOLVED
        )
        RawRow.objects.filter(pk__in=gone).update(status=RawRow.Status.DELETED)
    ing.stats.rows_added += added
    ing.stats.rows_deleted += len(gone)
    ing.stats.per_sheet[sheet.title] = {"added": added, "deleted": len(gone)}
    ing.finmodel = True


def _year_start(ing: Ingestor) -> date | None:
    """Sozlamalar: "Hisobot yili boshlanishi"; else the first Kassa/Smena date."""
    for s in getattr(ing, "workbook_sheets", []):
        if not text_key(s.title).startswith("sozlama"):
            continue
        for row in s.rows[:40]:
            keys = _keys(row)
            if any(k.startswith("hisobot yili boshlan") for k in keys):
                for v in row:
                    d = _date(v, ing.today) if isinstance(v, datetime | date) else None
                    if d:
                        return d
    return None


def ingest_accounts(ing: Ingestor, sheet: SheetData, h: int) -> None:
    """Opening balances of all cash accounts (USD at the sheet's latest rate) -> CashAccount."""
    rows = sheet.rows
    header = rows[h]
    i_name = _col(header, "hisob nomi")
    i_cur = _col(header, "valyuta")
    i_bal = _col(header, "boshl")
    if i_name is None or i_bal is None:
        return
    i_rate = _col(header, "usd kursi")
    rate = None
    if i_rate is not None:
        rates = [
            parse_amount(r[i_rate])
            for r in rows[h + 1 :]
            if i_rate < len(r) and r[i_rate] not in (None, "")
        ]
        rates = [x for x in rates if x]
        rate = rates[-1] if rates else None
    total = Decimal(0)
    found = False
    for r in rows[h + 1 :]:
        name = r[i_name] if i_name < len(r) else None
        if name in (None, ""):
            if found:
                break
            continue
        found = True
        bal = parse_amount(r[i_bal] if i_bal < len(r) else None) or Decimal(0)
        cur = text_key(r[i_cur]) if i_cur is not None and i_cur < len(r) and r[i_cur] else "so'm"
        if cur.startswith("usd"):
            bal = bal * rate if rate else Decimal(0)
        total += bal
    if not found:
        return
    first = (
        Transaction.objects.filter(raw_row__source=ing.source)
        .order_by("txn_date")
        .values_list("txn_date", flat=True)
        .first()
    )
    start = _year_start(ing) or first or ing.today
    if first and start > first:  # the year-start setting is later than the data: start at the data
        start = first
    CashAccount.objects.all().delete()
    CashAccount.objects.create(
        business=ing.business,
        opening_balance=total.quantize(Decimal("0.01")),
        as_of_date=start - timedelta(days=1),
    )
    ing.stats.cash_found = True
    ing.finmodel = True


# --- recurring fixed payments -------------------------------------------------------------------
def _month_add(d: date, k: int) -> date:
    y, m = divmod(d.month - 1 + k, 12)
    return date(d.year + y, m + 1, 1)


def project_recurring(ing: Ingestor) -> None:
    """Fixed payments seen in >= 2 of the last 3 months -> planned obligations ahead."""
    last = Transaction.objects.filter(is_actual=True).aggregate(m=Max("txn_date"))["m"]
    if last is None:
        return
    # the last complete month (the current one counts if the data reaches its last week)
    end_month = last.replace(day=1) if last.day >= 25 else _month_add(last.replace(day=1), -1)
    months = [_month_add(end_month, -k) for k in range(LOOKBACK_MONTHS)]
    lo, hi = months[-1], _month_add(end_month, 1) - timedelta(days=1)
    rows = Transaction.objects.filter(
        direction="out", category__in=FIXED, txn_date__gte=lo, txn_date__lte=hi
    ).values("category", "counterparty_id", "counterparty__name", "txn_date", "amount")
    groups: dict[tuple[str, int | None], dict[date, list[tuple[int, Decimal]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    names: dict[tuple[str, int | None], str] = {}
    for r in rows:
        key = (r["category"], r["counterparty_id"] if r["category"] in ("rent", "loan") else None)
        groups[key][r["txn_date"].replace(day=1)].append((r["txn_date"].day, r["amount"]))
        names[key] = r["counterparty__name"] or ""
    today = ing.today
    horizon = today + timedelta(days=125)

    def make() -> list[Obligation]:
        out: list[Obligation] = []
        for key, per_month in groups.items():
            if len(per_month) < 2:
                continue
            cat, cp_id = key
            amount = Decimal(
                statistics.median([sum((a for _, a in v), Decimal(0)) for v in per_month.values()])
            ).quantize(Decimal(1))
            weighted = sorted(
                d
                for v in per_month.values()
                for d, a in v
                for _ in range(max(1, int(a // 1_000_000)))
            )
            day = weighted[len(weighted) // 2] if weighted else 1
            title = FIXED_LABEL[cat] + (f" · {names[key]}" if cp_id and names.get(key) else "")
            m = today.replace(day=1)
            for _ in range(PROJECT_MONTHS + 1):
                due = m.replace(day=min(day, calendar.monthrange(m.year, m.month)[1]))
                if today < due <= horizon:
                    out.append(
                        Obligation(
                            business=ing.business,
                            title=title[:160],
                            amount=amount,
                            due_date=due,
                            category=cat,
                            counterparty_id=cp_id,
                            status="planned",
                            source="sheet",
                            priority=("critical" if cat in CRITICAL else "deferrable"),
                            recurrence={"pattern": "monthly", "day": day},
                        )
                    )
                m = _month_add(m, 1)
        return out

    ing._regenerate("Kassa · takroriy to'lovlar", make)
