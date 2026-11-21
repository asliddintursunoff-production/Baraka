"""Mapped sheets -> facts (spec §5.7). No LLM here: pure parsing + rules, every doubt is a
DataIssue (Uzbek message + suggestion) instead of a silent guess.

Row-level diff by row_hash: new rows are added, vanished rows deleted (with their facts),
a changed row = delete + add. Schedule-like sheets (payroll, loan) are regenerated on each
sync. The variable-cost ratio is re-estimated from the data after every ingest.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Q, Sum

from apps.engine.dates import add_months, on_day_of_month
from apps.finance.models import CashAccount, Counterparty, Obligation, Transaction
from apps.integrations.models import DataSource
from apps.knowledge.models import ForecastParams
from apps.tenancy.models import Business

from .models import DataIssue, RawRow, SheetMapping
from .normalize import (
    InvalidDate,
    clean_name,
    name_key,
    parse_amount,
    parse_date,
    parse_day_of_month,
    parse_direction,
)
from .readers import SheetData

OBLIGATION_CATEGORIES = ("payroll", "loan", "rent", "tax", "supplier", "kommunal")
CATEGORY_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "payroll",
        ("ish haqi", "oylik", "maosh", "zarplata", "зарплата", "иш ҳақи", "ойлик", "ish xaqi"),
    ),
    ("loan", ("kredit", "кредит", "qarz to'lovi", "lizing")),
    ("rent", ("ijara", "аренда", "ижара")),
    ("tax", ("soliq", "налог", "солиқ", "qqs", "ндс")),
    ("kommunal", ("svet", "elektr", "свет", "электр", "suv to'lovi", "kommunal", "коммунал")),
    ("supplier", ("ta'minotchi", "taminotchi", "поставщик", "таъминотчи")),
)
PLANNED_WORDS = (
    "kutil",
    "reja",
    "to'lanmagan",
    "to'lanadi",
    "ожида",
    "план",
    "не оплач",
    "kutyapti",
)
DEFERRABLE_WORDS = ("kechiks", "kechiktir", "keyinroq", "отлож")
SCHEDULE_MONTHS = 5


class RowIssue(Exception):
    def __init__(
        self, kind: str, short: str, message: str, suggestion: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.kind, self.short, self.message, self.suggestion = (
            kind,
            short,
            message,
            suggestion or {},
        )


@dataclass
class IngestStats:
    rows_added: int = 0
    rows_deleted: int = 0
    issues: int = 0
    sheets: int = 0
    data_rows: int = 0
    cash_found: bool = False
    per_sheet: dict[str, dict[str, int]] = field(default_factory=dict)


def infer_category(*texts: str) -> str:
    t = " ".join(texts).lower().replace("’", "'").replace("ʻ", "'")
    for cat, words in CATEGORY_WORDS:
        if any(w in t for w in words):
            return cat
    return ""


def json_safe(v: Any) -> Any:
    if isinstance(v, datetime | date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, int | float | str | bool) or v is None:
        return v
    return str(v)


def row_hash(sheet: str, cells: list[Any]) -> str:
    raw = json.dumps(
        [sheet, [json_safe(c) for c in cells]], ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class Ingestor:
    def __init__(self, business: Business, source: DataSource, today: date) -> None:
        self.business, self.source, self.today = business, source, today
        self._cps: dict[str, Counterparty] = {
            name_key(c.name): c for c in Counterparty.objects.all()
        }
        self.stats = IngestStats()

    # --- helpers ---------------------------------------------------------------------
    def counterparty(self, raw: Any) -> Counterparty | None:
        name = clean_name(raw) if raw not in (None, "") else ""
        if not name:
            return None
        key = name_key(name)
        cp = self._cps.get(key)
        if cp is None:
            cp = Counterparty.objects.create(business=self.business, name=name[:160])
            self._cps[key] = cp
        return cp

    def issue(
        self, sheet: str, row_no: int | None, exc: RowIssue, raw_row: RawRow | None = None
    ) -> None:
        _, created = DataIssue.objects.get_or_create(
            kind=exc.kind,
            message_uz=exc.message[:300],
            status=DataIssue.Status.OPEN,
            defaults={
                "business": self.business,
                "raw_row": raw_row,
                "suggestion": {
                    **exc.suggestion,
                    "short": exc.short,
                    "sheet": sheet,
                    "row": row_no,
                    "source_id": self.source.pk,
                },
            },
        )
        if created:
            self.stats.issues += 1

    @staticmethod
    def cols(mapping: SheetMapping) -> dict[str, list[int]]:
        out: dict[str, list[int]] = {}
        for idx, f in sorted(
            ((int(k), v) for k, v in mapping.column_map.items()), key=lambda x: x[0]
        ):
            if f and f != "ignore":
                out.setdefault(f, []).append(idx)
        return out

    @staticmethod
    def cell(row: list[Any], idx: int | None) -> Any:
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    def first(self, row: list[Any], cols: dict[str, list[int]], f: str) -> Any:
        for i in cols.get(f, []):
            v = self.cell(row, i)
            if v not in (None, ""):
                return v
        return None

    def date_of(self, sheet: str, row_no: int, value: Any, *, label: str = "Sana") -> date | None:
        try:
            return parse_date(value, today=self.today)
        except InvalidDate as exc:
            sug: date = exc.suggestion
            raise RowIssue(
                "invalid_date",
                f'{label} "{exc.text}" — {self._month_word(sug)} {exc.text.split(".")[0] if "." in exc.text else ""}-kun yo\'q'.replace(
                    "  ", " "
                ),
                f'"{sheet}" varag\'idagi {row_no}-qatorda sana "{exc.text}" mavjud emas. '
                f"{sug.day}.{sug.month:02d} deb olishni taklif qilaman.",
                {
                    "action": "use_suggestion",
                    "value": sug.isoformat(),
                    "action_label": f"{sug.day}.{sug.month:02d} deb olish",
                },
            ) from exc

    @staticmethod
    def _month_word(d: date) -> str:
        from apps.ai.uz_format import MONTHS

        return MONTHS[d.month - 1] + "da"

    # --- facts per row ---------------------------------------------------------------
    def build(
        self,
        kind: str,
        sheet: str,
        row_no: int,
        row: list[Any],
        cols: dict[str, list[int]],
        overrides: dict[str, Any] | None = None,
    ) -> list[Transaction | Obligation]:
        ov = overrides or {}
        amount_cols = cols.get("amount", [])
        amounts: list[tuple[int, Decimal]] = []
        for i in amount_cols:
            a = parse_amount(self.cell(row, i))
            if a is not None:
                amounts.append((i, a))
        if "amount" in ov:
            amounts = [(amount_cols[0] if amount_cols else -1, Decimal(str(ov["amount"])))]
        status = str(self.first(row, cols, "status") or "").lower()
        note = clean_name(self.first(row, cols, "note") or "")
        category_text = clean_name(self.first(row, cols, "category") or "")
        cp = self.counterparty(self.first(row, cols, "counterparty"))
        raw_date = ov.get("date") or self.first(row, cols, "date")
        raw_due = self.first(row, cols, "due_date")
        if not amounts:
            if any(v not in (None, "") for v in row):
                raise RowIssue(
                    "empty_amount",
                    "Summa bo'sh",
                    f'"{sheet}" varag\'idagi {row_no}-qatorda summa yozilmagan. Uni hisobga olmay turibman.',
                    {"action": "set_amount", "action_label": "Summani kiritish"},
                )
            return []

        def direction_for(idx: int, value: Decimal) -> str:
            if kind == "transactions_in":
                return "in"
            if kind in ("transactions_out", "obligations_schedule"):
                return "out"
            header_dir = self.header_dirs.get(idx)
            if header_dir:
                return header_dir
            d = parse_direction(self.first(row, cols, "direction"))
            if d:
                return d
            return "out" if value < 0 else "in"

        txn_date = (
            raw_date
            if isinstance(raw_date, date) and not isinstance(raw_date, datetime)
            else (self.date_of(sheet, row_no, raw_date) if raw_date not in (None, "") else None)
        )
        due = (
            self.date_of(sheet, row_no, raw_due, label="Muddat")
            if raw_due not in (None, "")
            else None
        )
        planned = any(w in status for w in PLANNED_WORDS) or (txn_date is None and due is not None)
        if kind == "obligations_schedule":
            planned, due = True, due or txn_date
        out: list[Transaction | Obligation] = []
        for idx, value in amounts:
            d = direction_for(idx, value)
            amount = abs(value)
            if amount == 0:
                continue
            cat = infer_category(category_text, note, cp.name if cp else "") or ""
            if planned and d == "out":
                if due is None:
                    raise RowIssue(
                        "no_date",
                        "Muddat yo'q",
                        f"\"{sheet}\" varag'idagi {row_no}-qatordagi rejalashtirilgan to'lovning muddati yo'q.",
                        {"action": "ignore", "action_label": "E'tiborsiz qoldirish"},
                    )
                prio = "deferrable" if any(w in status for w in DEFERRABLE_WORDS) else "critical"
                if cat == "supplier" and prio == "critical" and "kechik" in status:
                    prio = "deferrable"
                out.append(
                    Obligation(
                        business=self.business,
                        title=(category_text or note or (cp.name if cp else "To'lov"))[:160],
                        amount=amount,
                        due_date=due,
                        priority=prio,
                        category=cat,
                        counterparty=cp,
                        status=Obligation.Status.PLANNED,
                        source=Obligation.Source.SHEET,
                    )
                )
            else:
                when = txn_date or due
                if when is None:
                    raise RowIssue(
                        "no_date",
                        "Sana yo'q",
                        f"\"{sheet}\" varag'idagi {row_no}-qatorda sana yo'q. Uni hisobga olmay turibman.",
                        {"action": "ignore", "action_label": "E'tiborsiz qoldirish"},
                    )
                category = cat or category_text.lower()[:64]
                method = clean_name(self.first(row, cols, "method") or "")[:32]
                out.append(
                    Transaction(
                        business=self.business,
                        amount=amount,
                        direction=d,
                        category=category,
                        counterparty=cp,
                        txn_date=when,
                        method=method,
                        note=note[:255],
                    )
                )
        return out

    # --- sheets -------------------------------------------------------------------------
    header_dirs: dict[int, str] = {}

    def ingest_rows_sheet(self, sheet: SheetData, mapping: SheetMapping) -> None:
        cols = self.cols(mapping)
        h = mapping.header_row - 1
        headers = [str(c or "") for c in (sheet.rows[h] if h < len(sheet.rows) else [])]
        self.header_dirs = {
            i: d
            for i in cols.get("amount", [])
            if (d := parse_direction(headers[i] if i < len(headers) else "")) is not None
        }
        existing = {
            r.row_hash: r
            for r in RawRow.objects.filter(
                source=self.source, sheet_title=sheet.title, status=RawRow.Status.ACTIVE
            )
        }
        mapped_idx = sorted(i for idxs in cols.values() for i in idxs)
        seen: dict[str, int] = {}
        added = deleted = 0
        for offset, row in enumerate(sheet.rows[h + 1 :]):
            row_no = h + 2 + offset
            if not any(c not in (None, "") for c in row):
                continue
            self.stats.data_rows += 1
            key_cells = [self.cell(row, i) for i in mapped_idx]
            hsh = row_hash(sheet.title, key_cells)
            if hsh in seen:
                self.issue(
                    sheet.title,
                    row_no,
                    RowIssue(
                        "duplicate",
                        "Bir xil to'lov ikki marta yozilgan bo'lishi mumkin",
                        f'"{sheet.title}" varag\'idagi {seen[hsh]} va {row_no}-qatorlar bir xil. Bittasini hisobga oldim.',
                        {
                            "action": "ignore",
                            "action_label": "Bittasini olish",
                            "rows": [seen[hsh], row_no],
                        },
                    ),
                )
                continue
            seen[hsh] = row_no
            if hsh in existing:
                continue
            raw = RawRow.objects.create(
                business=self.business,
                source=self.source,
                sheet_title=sheet.title,
                row_index=row_no,
                row_hash=hsh,
                values=[json_safe(c) for c in row],
            )
            try:
                facts = self.build(mapping.sheet_kind, sheet.title, row_no, row, cols)
            except RowIssue as exc:
                self.issue(sheet.title, row_no, exc, raw)
                continue
            for f in facts:
                f.raw_row = raw
                f.save()
            added += 1
        gone = [r for hsh, r in existing.items() if hsh not in seen]
        if gone:
            ids = [r.pk for r in gone]
            Transaction.objects.filter(raw_row_id__in=ids).delete()
            Obligation.objects.filter(raw_row_id__in=ids).delete()
            DataIssue.objects.filter(raw_row_id__in=ids, status=DataIssue.Status.OPEN).update(
                status=DataIssue.Status.RESOLVED
            )
            RawRow.objects.filter(pk__in=ids).update(status=RawRow.Status.DELETED)
            deleted = len(ids)
        self.stats.rows_added += added
        self.stats.rows_deleted += deleted
        self.stats.per_sheet[sheet.title] = {"added": added, "deleted": deleted}

    def _regenerate(self, sheet_title: str, make: Callable[[], list[Obligation]]) -> None:
        Obligation.objects.filter(
            raw_row__isnull=True, recurrence__from_sheet=f"{self.source.pk}:{sheet_title}"
        ).delete()
        for o in make():
            o.recurrence = {**(o.recurrence or {}), "from_sheet": f"{self.source.pk}:{sheet_title}"}
            o.save()

    def ingest_payroll(self, sheet: SheetData, mapping: SheetMapping) -> None:
        cols = self.cols(mapping)
        h = mapping.header_row - 1
        salaries: list[Decimal] = []
        days: list[int] = []
        for row in sheet.rows[h + 1 :]:
            a = parse_amount(self.first(row, cols, "amount"))
            name = self.first(row, cols, "counterparty") or self.first(row, cols, "note")
            if (
                a is None
                or a <= 0
                or not name
                or "jami" in str(name).lower()
                or "жами" in str(name).lower()
                or "итого" in str(name).lower()
            ):
                continue
            salaries.append(a)
            d = parse_day_of_month(self.first(row, cols, "due_date"))
            if d:
                days.append(d)
        if not salaries:
            return
        Business.objects.filter(pk=self.business.pk).update(staff_count=len(salaries))
        self.business.staff_count = len(salaries)
        total = sum(salaries, Decimal(0))
        payday = Counter(days).most_common(1)[0][0] if days else 10
        title = f"Ish haqi · {len(salaries)} xodim"

        def make() -> list[Obligation]:
            out = []
            first = self.today.replace(day=1)
            for k in range(SCHEDULE_MONTHS):
                m = add_months(first, k)
                d = on_day_of_month(m.year, m.month, payday)
                if d <= self.today:
                    continue
                exists = (
                    Obligation.objects.filter(
                        category="payroll",
                        status="planned",
                        due_date__gte=d - timedelta(days=3),
                        due_date__lte=d + timedelta(days=3),
                    )
                    .exclude(recurrence__from_sheet=f"{self.source.pk}:{sheet.title}")
                    .exists()
                )
                if not exists:
                    out.append(
                        Obligation(
                            business=self.business,
                            title=title,
                            amount=total,
                            due_date=d,
                            priority="critical",
                            category="payroll",
                            status="planned",
                            source="sheet",
                            recurrence={"freq": "monthly", "day": payday},
                        )
                    )
            return out

        self._regenerate(sheet.title, make)

    def ingest_loan(self, sheet: SheetData, mapping: SheetMapping) -> None:
        cols = self.cols(mapping)
        h = mapping.header_row - 1
        lender = (
            clean_name(re.split(r"\s+", sheet.title.strip())[0]) if sheet.title.strip() else "Bank"
        )
        rows: list[tuple[date, Decimal]] = []
        for row in sheet.rows[h + 1 :]:
            amts = [
                a
                for i in cols.get("amount", [])
                if (a := parse_amount(self.cell(row, i))) is not None
            ]
            raw_d = self.first(row, cols, "due_date") or self.first(row, cols, "date")
            try:
                d = parse_date(raw_d, today=self.today) if raw_d not in (None, "") else None
            except InvalidDate:
                d = None
            if d and amts and d > self.today:
                rows.append((d, max(amts)))  # the "Jami to'lov" column is the largest
        cp = self.counterparty(lender)

        def make() -> list[Obligation]:
            return [
                Obligation(
                    business=self.business,
                    title=f"{lender} kredit to'lovi",
                    amount=a,
                    due_date=d,
                    priority="critical",
                    category="loan",
                    counterparty=cp,
                    status="planned",
                    source="sheet",
                )
                for d, a in rows
            ]

        self._regenerate(sheet.title, make)

    def ingest_cash(self, sheet: SheetData, mapping: SheetMapping) -> None:
        cols = self.cols(mapping)
        h = mapping.header_row - 1
        best: tuple[date, Decimal] | None = None
        for row in sheet.rows[h + 1 :]:
            a = parse_amount(self.first(row, cols, "amount"))
            try:
                d = parse_date(self.first(row, cols, "date"), today=self.today)
            except InvalidDate:
                d = None
            if a is not None and d and (best is None or d >= best[0]):
                best = (d, a)
        if best:
            CashAccount.objects.all().delete()
            CashAccount.objects.create(
                business=self.business, opening_balance=best[1], as_of_date=best[0]
            )
            self.stats.cash_found = True

    def ingest_counterparties(self, sheet: SheetData, mapping: SheetMapping) -> None:
        cols = self.cols(mapping)
        h = mapping.header_row - 1
        for row in sheet.rows[h + 1 :]:
            self.counterparty(self.first(row, cols, "counterparty"))

    def ingest(self, sheet: SheetData, mapping: SheetMapping) -> None:
        self.stats.sheets += 1
        k = mapping.sheet_kind
        if k in (
            "transactions_in",
            "transactions_out",
            "transactions_mixed",
            "obligations_schedule",
        ):
            self.ingest_rows_sheet(sheet, mapping)
        elif k == "payroll":
            self.ingest_payroll(sheet, mapping)
        elif k == "loan_schedule":
            self.ingest_loan(sheet, mapping)
        elif k == "cash_balance":
            self.ingest_cash(sheet, mapping)
        elif k == "counterparties":
            self.ingest_counterparties(sheet, mapping)

    def finish(self) -> None:
        dedupe_planned()
        estimate_variable_cost_ratio(self.business, self.today)


def dedupe_planned() -> None:
    """The same payment from a plan sheet and a schedule sheet counts once."""
    seen: set[tuple[date, Decimal, str]] = set()
    for o in Obligation.objects.filter(status="planned").order_by("raw_row_id", "id"):
        key = (o.due_date, o.amount, o.category)
        if key in seen and o.category:
            o.delete()
        else:
            seen.add(key)


def estimate_variable_cost_ratio(business: Business, today: date) -> Decimal | None:
    start = today - timedelta(days=55)
    agg = Transaction.objects.filter(txn_date__gte=start, txn_date__lte=today).aggregate(
        inflow=Sum("amount", filter=Q(direction="in")),
        var=Sum("amount", filter=Q(direction="out") & ~Q(category__in=OBLIGATION_CATEGORIES)),
    )
    inflow, var = agg["inflow"] or Decimal(0), agg["var"] or Decimal(0)
    if inflow <= 0:
        return None
    ratio = min(Decimal("0.9"), (var / inflow).quantize(Decimal("0.0001")))
    params, _ = ForecastParams.objects.get_or_create(
        business=business, defaults={"weekday_factors": [1.0] * 7}
    )
    params.variable_cost_ratio = ratio
    params.save(update_fields=["variable_cost_ratio", "updated_at"])
    return ratio


def replace_seed_data() -> None:
    """First confirmed sheet for a business: the sheet becomes the only source of truth
    (seeded/demo rows without a raw_row are removed; manual payments are kept)."""
    Transaction.objects.filter(raw_row__isnull=True).delete()
    Obligation.objects.filter(raw_row__isnull=True).exclude(
        source=Obligation.Source.MANUAL
    ).delete()
