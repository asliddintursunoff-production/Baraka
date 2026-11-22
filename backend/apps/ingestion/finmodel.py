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
import itertools
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db.models import Max, Q

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


def info_proposal(sheet: SheetData) -> SheetProposal:
    """Analysis-only tab (Sotuv, Ish haqi, Energiya...): every column listed, not added to cash."""
    from apps.workbook.reader import detect_sheet

    from .mapping import ColumnProposal, SheetProposal

    t = detect_sheet(sheet.title, sheet.rows)
    if not t.header_row:
        return SheetProposal(sheet.title, 1, "", len(t.rows), "ignore", 0.95)
    header = sheet.rows[t.header_row - 1]
    keys = _keys(header)
    izoh = next((j for j, k in enumerate(keys) if k.startswith("izoh")), None)
    cols = []
    for c in t.columns:
        if c.name.startswith("col_"):
            continue
        j = c.index
        sample = next(
            (str(r[j - t.first_col])[:40] for r in t.rows if r[j - t.first_col] not in (None, "")),
            "",
        )
        cols.append(
            ColumnProposal(
                j, c.name, sample, "computed" if izoh is not None and j > izoh else "info", 1.0
            )
        )
    return SheetProposal(sheet.title, t.header_row, "", len(t.rows), "ignore", 0.95, cols)


def proposal(sheet: SheetData) -> SheetProposal | None:
    from .mapping import ColumnProposal, SheetProposal

    d = detect(sheet)
    if d is None:
        return None
    if d.kind == "ignore":
        return info_proposal(sheet)
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
    used: set[int] = set()
    for start, field_name in fields:
        i = _col(header, start)
        if i is None:
            continue
        used.add(i)
        sample = next((str(r[i])[:40] for r in data if i < len(r) and r[i] not in (None, "")), "")
        cols.append(ColumnProposal(i, str(header[i]), sample, field_name, 1.0))
    # every other column too: input columns (up to "Izoh") are read; the rest are formulas
    keys = _keys(header)
    izoh = next((j for j, k in enumerate(keys) if k.startswith("izoh")), None)
    for j, v in enumerate(header):
        if j in used or v in (None, ""):
            continue
        sample = next((str(r[j])[:40] for r in data if j < len(r) and r[j] not in (None, "")), "")
        computed = izoh is not None and j > izoh
        if d.kind == SMENA and keys[j].startswith("z hisobot"):
            fld = "revenue"
        else:
            fld = "computed" if computed else "info"
        cols.append(ColumnProposal(j, str(v), sample, fld, 1.0))
    if izoh is not None:
        for c in cols:
            if c.index > izoh and c.field not in ("computed",):
                c.question = "formula"  # derived column used as a check / ledger amount
    cols.sort(key=lambda c: c.index)
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
        if f.startswith(("moliyaviy", "investitsion")):
            return "financing"
        return "agregator" if "agregator" in m else "savdo"
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
            "received": ("qabul so'm",),
            "naqd_pos": ("naqd pos",),
            "naqd_till": ("naqd kassaga",),
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
        fields: dict[str, Any]
        d = _date(cell(row, "date"), ing.today)
        if d is None:
            continue
        if kind == KASSA:
            turi = str(cell(row, "turi") or "")
            signed = parse_amount(cell(row, "signed"))
            if text_key(turi).startswith("o'tkazma"):
                # transfer between own accounts: only a difference (fee / exchange) is real money
                received = parse_amount(cell(row, "received"))
                net = (
                    (received + signed)
                    if (received is not None and signed is not None)
                    else Decimal(0)
                )
                if abs(net) < 1:
                    continue
                fields = {
                    "amount": abs(net),
                    "direction": "in" if net > 0 else "out",
                    "category": "bank komissiyasi",
                    "counterparty": None,
                    "method": str(cell(row, "hisob") or "")[:32],
                    "note": "O'tkazma farqi",
                }
                fields["txn_date"] = d
                out.append((row_no, row, fields))
                continue
            if not signed:
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
            pos, till = parse_amount(cell(row, "naqd_pos")), parse_amount(cell(row, "naqd_till"))
            if total is not None and pos is not None and till is not None:
                total = total - pos + till  # the counted cash that really went into the till
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


def planned_payments(
    as_of: date, source_id: int | None = None, horizon_days: int = 125
) -> list[dict[str, Any]]:
    """Fixed payments seen in >= 2 of the last 3 months before `as_of` (cash payment rows only),
    plus the loan schedule from its terms -> planned payments in (as_of, as_of + horizon]."""
    last = Transaction.objects.filter(is_actual=True, txn_date__lte=as_of).aggregate(
        m=Max("txn_date")
    )["m"]
    if last is None:
        return []
    end_month = last.replace(day=1) if last.day >= 25 else _month_add(last.replace(day=1), -1)
    months = [_month_add(end_month, -k) for k in range(LOOKBACK_MONTHS)]
    lo, hi = months[-1], _month_add(end_month, 1) - timedelta(days=1)
    rows = Transaction.objects.filter(
        direction="out", category__in=FIXED, txn_date__gte=lo, txn_date__lte=min(hi, as_of)
    ).values("category", "counterparty_id", "counterparty__name", "txn_date", "amount")
    groups: dict[tuple[str, int | None], dict[date, list[tuple[int, Decimal]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    names: dict[tuple[str, int | None], str] = {}
    for r in rows:
        key = (r["category"], r["counterparty_id"] if r["category"] in ("rent", "loan") else None)
        groups[key][r["txn_date"].replace(day=1)].append((r["txn_date"].day, r["amount"]))
        names[key] = r["counterparty__name"] or ""
    start = min(as_of, last)
    horizon = start + timedelta(days=horizon_days)
    loan = loan_info(source_id, as_of) if source_id else None
    out: list[dict[str, Any]] = []
    for key, per_month in groups.items():
        if len(per_month) < 2:
            continue
        cat, cp_id = key
        if cat == "loan" and loan:
            continue  # scheduled from the loan terms below
        amount = Decimal(
            statistics.median([sum((a for _, a in v), Decimal(0)) for v in per_month.values()])
        ).quantize(Decimal(1))
        weighted = sorted(
            d for v in per_month.values() for d, a in v for _ in range(max(1, int(a // 1_000_000)))
        )
        day = weighted[len(weighted) // 2] if weighted else 1
        title = FIXED_LABEL[cat] + (f" · {names[key]}" if cp_id and names.get(key) else "")
        m = start.replace(day=1)
        for _ in range(horizon_days // 28 + 2):
            due = m.replace(day=min(day, calendar.monthrange(m.year, m.month)[1]))
            if start < due <= horizon:
                out.append(
                    {
                        "title": title[:160],
                        "amount": amount,
                        "due_date": due,
                        "category": cat,
                        "counterparty_id": cp_id,
                        "counterparty": names.get(key, "") if cp_id else "",
                        "priority": "critical" if cat in CRITICAL else "deferrable",
                        "recurrence": {"pattern": "monthly", "day": day},
                    }
                )
            m = _month_add(m, 1)
    if loan and Decimal(loan["balance"]) > 0:
        balance = Decimal(loan["balance"])
        principal = Decimal(loan["principal_monthly"] or 0)
        grace_end = None
        if loan.get("grace_months") and not principal:
            first = date.fromisoformat(loan["first_date"])
            grace_end = _month_add(first.replace(day=1), int(loan["grace_months"]))
            if loan.get("term_months"):
                principal = (
                    balance / max(1, int(loan["term_months"]) - int(loan["grace_months"]))
                ).quantize(Decimal(1000))
        rate = Decimal(loan["rate_pct"] or 0) / 1200
        last_interest = Decimal(loan["last_interest"] or 0)
        m = start.replace(day=1)
        for _ in range(horizon_days // 28 + 2):
            due = m.replace(day=min(loan["pay_day"], calendar.monthrange(m.year, m.month)[1]))
            if start < due <= horizon and balance > 0:
                interest = (balance * rate).quantize(Decimal(1)) if rate else last_interest
                pay = (
                    min(principal, balance)
                    if (grace_end is None or due >= grace_end)
                    else Decimal(0)
                )
                out.append(
                    {
                        "title": f"Kredit to'lovi · {loan['lender']}"[:160],
                        "amount": pay + interest,
                        "due_date": due,
                        "category": "loan",
                        "counterparty_id": None,
                        "counterparty": loan["lender"],
                        "priority": "critical",
                        "recurrence": {
                            "pattern": "loan",
                            "principal": str(pay),
                            "interest": str(interest),
                        },
                    }
                )
                balance -= pay
            m = _month_add(m, 1)
    return out


def aggregator_payouts(as_of: date, horizon_days: int = 125) -> list[tuple[date, Decimal]]:
    """Aggregator money arrives on its own cadence: per payer, the median payout and the median
    gap between payouts over the last 3 months, projected forward from the last payout."""
    rows = list(
        Transaction.objects.filter(
            direction="in",
            category="agregator",
            txn_date__lte=as_of,
            txn_date__gt=as_of - timedelta(days=95),
        )
        .values("counterparty_id", "txn_date", "amount")
        .order_by("txn_date")
    )
    by_payer: dict[int | None, list[tuple[date, Decimal]]] = defaultdict(list)
    for r in rows:
        by_payer[r["counterparty_id"]].append((r["txn_date"], r["amount"]))
    out: list[tuple[date, Decimal]] = []
    end = as_of + timedelta(days=horizon_days)
    for payouts in by_payer.values():
        if not payouts:
            continue
        amount = Decimal(statistics.median([a for _, a in payouts])).quantize(Decimal(1))
        gaps = [
            (b[0] - a[0]).days for a, b in itertools.pairwise(payouts) if (b[0] - a[0]).days > 0
        ]
        gap = int(statistics.median(gaps)) if gaps else 30
        d = payouts[-1][0] + timedelta(days=gap)
        while d <= end:
            if d > as_of:
                out.append((d, amount))
            d += timedelta(days=gap)
    return sorted(out)


def project_recurring(ing: Ingestor) -> None:
    """Persist planned payments projected from the last actual day (the forecast's day 0)."""
    last = Transaction.objects.filter(is_actual=True).aggregate(m=Max("txn_date"))["m"]
    if last is None:
        return
    specs = planned_payments(min(ing.today, last), ing.source.pk)

    def make() -> list[Obligation]:
        return [
            Obligation(
                business=ing.business,
                title=x["title"],
                amount=x["amount"],
                due_date=x["due_date"],
                category=x["category"],
                counterparty_id=x["counterparty_id"],
                status="planned",
                source="sheet",
                priority=x["priority"],
                recurrence=x["recurrence"],
            )
            for x in specs
        ]

    ing._regenerate("Kassa · takroriy to'lovlar", make)


# --- loan, monthly summary and reconciliation ---------------------------------------------------
MONTH_ABBR = ("yan", "fev", "mar", "apr", "may", "iyun", "iyul", "avg", "sen", "okt", "noy", "dek")
RECON_TOLERANCE = Decimal("0.01")  # 1 %


def _num(v: Any) -> Decimal:
    return parse_amount(v) or Decimal(0)


def loan_info(source_id: int, as_of: date | None = None) -> dict[str, Any] | None:
    """Bank loan from Kassa rows (up to `as_of`): received / repaid / interest, terms from the note."""
    rows = list(
        Transaction.objects.filter(raw_row__source_id=source_id, txn_date__lte=as_of or date.max)
        .filter(Q(note__istartswith="Kredit") | Q(category="loan"))
        .values("txn_date", "direction", "amount", "note", "counterparty__name")
        .order_by("txn_date")
    )
    received = [r for r in rows if r["direction"] == "in" and "olindi" in r["note"].lower()]
    if not received:
        return None
    repaid = [r for r in rows if r["direction"] == "out" and "qaytarildi" in r["note"].lower()]
    interest = [r for r in rows if r["direction"] == "out" and "foiz" in r["note"].lower()]
    note = " ".join(r["note"] for r in received)
    term = re.search(r"(\d+)\s*oy(?!\s*imtiyoz)", note)
    rate = re.search(r"(\d+(?:[.,]\d+)?)\s*%", note)
    grace = re.search(r"(\d+)\s*oy\s*imtiyoz", note)
    total_in = sum((r["amount"] for r in received), Decimal(0))
    total_repaid = sum((r["amount"] for r in repaid), Decimal(0))
    principal = Decimal(statistics.median([r["amount"] for r in repaid])) if repaid else Decimal(0)
    pay_day = (interest[-1] if interest else repaid[-1] if repaid else received[0])["txn_date"].day
    return {
        "lender": received[0]["counterparty__name"] or "Bank",
        "received": str(total_in),
        "repaid": str(total_repaid),
        "balance": str(total_in - total_repaid),
        "principal_monthly": str(principal),
        "rate_pct": rate.group(1).replace(",", ".") if rate else None,
        "term_months": int(term.group(1)) if term else None,
        "grace_months": int(grace.group(1)) if grace else None,
        "last_interest": str(interest[-1]["amount"]) if interest else None,
        "pay_day": pay_day,
        "first_date": received[0]["txn_date"].isoformat(),
    }


def _month_cols(rows: list[list[Any]]) -> tuple[int, dict[int, date]] | None:
    """The header row whose cells are months ("Yan 2026" or dates): row index, {col: month}."""
    import re

    for i, row in enumerate(rows[:8]):
        cols: dict[int, date] = {}
        for j, v in enumerate(row):
            k = text_key(v) if isinstance(v, str) else ""
            m = re.match(r"^(" + "|".join(MONTH_ABBR) + r")\w*\s+(\d{4})$", k)
            if m:
                cols[j] = date(int(m.group(2)), MONTH_ABBR.index(m.group(1)) + 1, 1)
        if len(cols) >= 6:
            return i, cols
    return None


def _report_row(sheet: SheetData | None, *starts: str) -> dict[date, Decimal]:
    """Values by month of the first row whose label starts with one of `starts`."""
    if sheet is None:
        return {}
    found = _month_cols(sheet.rows)
    if not found:
        return {}
    _, cols = found
    for row in sheet.rows:
        label = next((text_key(v) for v in row[:3] if isinstance(v, str) and v.strip()), "")
        if label and any(label.startswith(s) for s in starts):
            return {m: _num(row[j]) for j, m in cols.items() if j < len(row)}
    return {}


def _sheet(sheets: list[SheetData], *prefixes: str) -> SheetData | None:
    return next((s for s in sheets if any(text_key(s.title).startswith(p) for p in prefixes)), None)


# Bump when the summary gains fields: every source is re-read once on its next sync.
SUMMARY_VERSION = 6


def summarize(source_id: int, sheets: list[SheetData], today: date) -> dict[str, Any]:
    """Month-by-month figures from the cash ledger and the journals, reconciled with the
    workbook's own reports (Pul oqimi / Balans / Foyda-zarar), tolerance 1 %."""
    from . import finmodel_details

    txns = list(
        Transaction.objects.filter(raw_row__source_id=source_id, is_actual=True).values(
            "txn_date", "direction", "category", "amount", "note"
        )
    )
    if not txns:
        return {"months": {}, "recon": [], "last_date": None}
    cash = CashAccount.objects.order_by("-as_of_date").first()
    months: dict[date, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for t in txns:
        m = t["txn_date"].replace(day=1)
        a = t["amount"]
        f = months[m]
        f["net"] += a if t["direction"] == "in" else -a
        note = t["note"].lower()
        if t["direction"] == "out":
            if t["category"] == "payroll":
                f["payroll_paid"] += a
            if note.startswith("yetkazib beruvchiga"):
                f["supplier_payments"] += a
            if t["category"] == "kommunal":
                f["utilities"] += a
            if "kredit foizi" in note:
                f["loan_interest"] += a
            if "qaytarildi" in note:
                f["loan_principal"] += a
            if t["category"] == "kunbay":
                f["day_labour"] += a
    last = max(t["txn_date"] for t in txns)
    first = min(t["txn_date"] for t in txns)
    running = Decimal(cash.opening_balance) if cash else Decimal(0)
    for m in sorted(months):
        running += months[m]["net"]
        months[m]["cash_end"] = running
    # journals: revenue (Smena Z-report), payroll accrual (Ish haqi brutto + day labour), transfers
    smena, ish, kassa = _sheet(sheets, "smena"), _sheet(sheets, "ish haqi"), _sheet(sheets, "kassa")
    for sh, date_col, val_col, key in (
        (smena, "sana", "z hisobot", "revenue"),
        (ish, "oy oxiri", "hisoblangan brutto", "payroll_accrued"),
    ):
        if sh is None:
            continue
        hv = _find_header(sh.rows, val_col)
        if hv is None:
            continue
        header = sh.rows[hv]
        ic, iv = _col(header, date_col), _col(header, val_col)
        if ic is None or iv is None:
            continue
        for row in sh.rows[hv + 1 :]:
            dd = _date(row[ic] if ic < len(row) else None, today)
            if dd and iv < len(row):
                months[dd.replace(day=1)][key] += _num(row[iv])
    for m in months:
        months[m]["payroll_accrued"] += months[m]["day_labour"]
    if kassa is not None and (hk := _find_header(kassa.rows, "sana", "turi", "modda")) is not None:
        header = kassa.rows[hk]
        ic, it, ia = (
            _col(header, "sana"),
            _col(header, "turi"),
            _col(header, "summa hisob valyutasida", "summa"),
        )
        for row in kassa.rows[hk + 1 :]:
            dd = _date(row[ic] if ic is not None and ic < len(row) else None, today)
            if (
                dd
                and it is not None
                and it < len(row)
                and text_key(row[it] or "").startswith("o'tkazma")
                and ia is not None
            ):
                months[dd.replace(day=1)]["transfers"] += abs(_num(row[ia]))
    # balances with counterparties (Kontragentlar: positive = we owe, negative = they owe us)
    balances: list[dict[str, str]] = []
    kontr = _sheet(sheets, "kontragent")
    if kontr is not None and (hc := _find_header(kontr.rows, "nomi", "turi")) is not None:
        header = kontr.rows[hc]
        mc = _month_cols(kontr.rows)
        col_last = next(
            (j for j, m in (mc[1].items() if mc else []) if m == last.replace(day=1)), None
        )
        i_name, i_type, i_saldo = _col(header, "nomi"), _col(header, "turi"), _col(header, "saldo")
        for row in kontr.rows[hc + 1 :]:
            name = row[i_name] if i_name is not None and i_name < len(row) else None
            j = col_last if col_last is not None else i_saldo
            if not name or j is None or j >= len(row):
                continue
            bal = _num(row[j])
            if bal:
                balances.append(
                    {
                        "name": str(name),
                        "type": str(row[i_type] or "")
                        if i_type is not None and i_type < len(row)
                        else "",
                        "balance": str(bal),
                    }
                )
    # reports and reconciliation
    reported = {
        "cash_end": _report_row(_sheet(sheets, "pul oqimi"), "hisoblar bo'yicha qoldiq")
        or _report_row(_sheet(sheets, "balans"), "pul mablag"),
        "revenue": _report_row(_sheet(sheets, "foyda"), "sof tushum"),
        "payroll_accrued": _report_row(_sheet(sheets, "foyda"), "ish haqi"),
    }
    recon = []
    for metric, rep_by_month in reported.items():
        for m, rv in sorted(rep_by_month.items()):
            if m > last.replace(day=1) or m < first.replace(day=1):
                continue
            cv = months.get(m, {}).get(metric, Decimal(0))
            ok = abs(cv - rv) <= max(abs(rv) * RECON_TOLERANCE, Decimal(1000))
            recon.append(
                {
                    "month": m.isoformat(),
                    "metric": metric,
                    "computed": str(cv.quantize(Decimal("0.01"))),
                    "reported": str(rv.quantize(Decimal("0.01"))),
                    "ok": ok,
                }
            )
    return {
        "first_date": first.isoformat(),
        "last_date": last.isoformat(),
        "months": {
            m.isoformat(): {k: str(v.quantize(Decimal("0.01"))) for k, v in f.items()}
            for m, f in sorted(months.items())
        },
        "loan": loan_info(source_id),
        "balances": balances,
        "recon": recon,
        "has_reports": any(reported.values()),
        "reports": report_tables(sheets),
        "journals": journal_breakdowns(sheets, today),
        "details": finmodel_details.details(sheets, today),
        "v": SUMMARY_VERSION,
    }


# --- report tables and journal breakdowns for the CFO analysis modules -------------------------
def report_tables(sheets: list[SheetData]) -> dict[str, Any]:
    """Every labelled row with month columns from the P&L, plan-vs-fact and balance sheets,
    plus KPI targets from the dashboard sheet. Values by month ISO: {label: {month: str}}."""

    def rows_by_month(sh: SheetData | None, sections: bool = False) -> dict[str, dict[str, str]]:
        if sh is None:
            return {}
        out: dict[str, dict[str, str]] = {}
        section = ""
        cols: dict[int, date] = {}
        for row in sh.rows:
            mc = None
            if sum(1 for v in row if isinstance(v, str) and _month_cols([row])) >= 1:
                mc = _month_cols([row])
            if mc:
                cols = mc[1]
                continue
            texts = [
                (j, text_key(v)) for j, v in enumerate(row[:4]) if isinstance(v, str) and v.strip()
            ]
            if not texts:
                continue
            _j0, label = texts[0]
            if sections and label in ("reja", "fakt"):
                section = label
                continue
            if not cols or not any(j < len(row) and isinstance(row[j], int | float) for j in cols):
                continue
            key = f"{section}:{label}" if sections and section else label
            out.setdefault(
                key, {m.isoformat(): str(_num(row[j])) for j, m in cols.items() if j < len(row)}
            )
        return out

    targets: dict[str, str] = {}
    dash = _sheet(sheets, "bosh sahifa")
    if dash is not None:
        h = _find_header(dash.rows, "ko'rsatkich")
        if h is not None:
            header = dash.rows[h]
            it = _col(header, "maqsad")
            for row in dash.rows[h + 1 : h + 40]:
                label = next((text_key(v) for v in row[:3] if isinstance(v, str) and v.strip()), "")
                is_month = re.match(r"^(" + "|".join(MONTH_ABBR) + r")\w*\s+\d{4}$", label)
                if (
                    label
                    and not is_month
                    and it is not None
                    and it < len(row)
                    and isinstance(row[it], int | float)
                ):
                    targets[label] = str(_num(row[it]))
    return {
        "pl": rows_by_month(_sheet(sheets, "foyda")),
        "plan_fact": rows_by_month(_sheet(sheets, "reja fakt", "reja-fakt"), sections=True),
        "balans": rows_by_month(_sheet(sheets, "balans")),
        "kpi_targets": targets,
    }


def journal_breakdowns(sheets: list[SheetData], today: date) -> dict[str, Any]:
    """Cash flows by activity, Kassa outflows by item, Smena checks and weekday Z-totals."""
    acts: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    items: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    checks: dict[str, Decimal] = defaultdict(Decimal)
    days: dict[str, set[date]] = defaultdict(set)
    z_by_day: dict[date, Decimal] = {}
    wd_checks: dict[date, Decimal] = {}
    kassa, smena, kirim = _sheet(sheets, "kassa"), _sheet(sheets, "smena"), _sheet(sheets, "kirim")
    if kassa is not None and (hk := _find_header(kassa.rows, "sana", "turi", "modda")) is not None:
        hd = kassa.rows[hk]
        c = {
            k: _col(hd, *v)
            for k, v in {
                "d": ("sana",),
                "t": ("turi",),
                "m": ("modda",),
                "s": ("summa so'm",),
                "f": ("faoliyat",),
                "q": ("qabul so'm",),
            }.items()
        }

        def g(row: list[Any], k: str) -> Any:
            i = c.get(k)
            return row[i] if i is not None and i < len(row) else None

        for row in kassa.rows[hk + 1 :]:
            d = _date(g(row, "d"), today)
            if d is None:
                continue
            m = d.replace(day=1).isoformat()
            signed = _num(g(row, "s"))
            if text_key(g(row, "t") or "").startswith("o'tkazma"):
                diff = _num(g(row, "q")) + signed
                if diff:  # fee / exchange difference: real money, kept apart from the activities
                    acts[m]["other"] += diff
                continue
            f = text_key(g(row, "f") or "")
            act = (
                "investing"
                if f.startswith("investitsion")
                else "financing"
                if f.startswith("moliyaviy")
                else "operating"
            )
            acts[m][act] += signed
            modda = str(g(row, "m") or "boshqa")
            if signed < 0:
                items[m][modda] += -signed
            for key, word in (
                ("owner_in", "ta'sischi"),
                ("loan_in", "olindi"),
                ("loan_repaid", "qaytarildi"),
                ("interest", "kredit foizi"),
                ("dividend", "dividend"),
            ):
                if word in text_key(modda):
                    acts[m][key] += signed
    if smena is not None and (hs := _find_header(smena.rows, "sana", "to'lovlar jami")) is not None:
        hd = smena.rows[hs]
        ids, ic, iz, it_, ip, ik = (
            _col(hd, "sana"),
            _col(hd, "cheklar"),
            _col(hd, "z hisobot"),
            _col(hd, "to'lovlar jami"),
            _col(hd, "naqd pos"),
            _col(hd, "naqd kassaga"),
        )
        for row in smena.rows[hs + 1 :]:
            d = _date(row[ids] if ids is not None and ids < len(row) else None, today)
            if d is None:
                continue
            m = d.replace(day=1).isoformat()

            def v(i: int | None, r: list[Any] = row) -> Decimal:
                return _num(r[i]) if i is not None and i < len(r) else Decimal(0)

            acts[m]["operating"] += (
                v(it_)
                - v(ip)
                + (
                    v(ik)
                    if ik is not None and ik < len(row) and row[ik] not in (None, "")
                    else v(ip)
                )
            )
            checks[m] += v(ic)
            wd_checks[d] = v(ic)
            days[m].add(d)
            z_by_day[d] = z_by_day.get(d, Decimal(0)) + v(iz)
    if (
        kirim is not None
        and (hp := _find_header(kirim.rows, "sana", "darhol to'langan")) is not None
    ):
        hd = kirim.rows[hp]
        idd, ipf, ipd = _col(hd, "sana"), _col(hd, "darhol to'langan"), _col(hd, "to'lov so'm")
        for row in kirim.rows[hp + 1 :]:
            d = _date(row[idd] if idd is not None and idd < len(row) else None, today)
            if d is None or ipf is None or ipf >= len(row) or row[ipf] in (None, ""):
                continue
            acts[d.replace(day=1).isoformat()]["operating"] -= _num(
                row[ipd] if ipd is not None and ipd < len(row) else 0
            )
    # weekday averages of the Z-report over the last 3 months with data
    weekday: dict[int, str] = {}
    weekday_checks: dict[int, str] = {}
    if z_by_day:
        last = max(z_by_day)
        start = _month_add(last.replace(day=1), -2)
        per: dict[int, list[Decimal]] = defaultdict(list)
        for d, z in z_by_day.items():
            if start <= d <= last:
                per[d.weekday()].append(z)
        weekday = {
            w: str((sum(v, Decimal(0)) / len(v)).quantize(Decimal(1))) for w, v in per.items() if v
        }
        per_c: dict[int, list[Decimal]] = defaultdict(list)
        for d, n in wd_checks.items():
            if start <= d <= last:
                per_c[d.weekday()].append(n)
        weekday_checks = {
            w: str((sum(v, Decimal(0)) / len(v)).quantize(Decimal("0.1")))
            for w, v in per_c.items()
            if v
        }
    return {
        "activities": {m: {k: str(v) for k, v in f.items()} for m, f in sorted(acts.items())},
        "outflow_items": {
            m: {k: str(v) for k, v in sorted(f.items(), key=lambda kv: -kv[1])}
            for m, f in sorted(items.items())
        },
        "checks": {m: str(v) for m, v in sorted(checks.items())},
        "smena_days": {m: len(v) for m, v in sorted(days.items())},
        "weekday_z": weekday,
        "weekday_checks": weekday_checks,
        "last_dates": {
            "smena": max(z_by_day).isoformat() if z_by_day else None,
        },
    }
