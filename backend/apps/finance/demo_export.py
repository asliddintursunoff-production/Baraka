"""Export the Navro'z demo dataset as a realistic, messy .xlsx (seed_demo --export).

The same data seed_demo writes to the DB, laid out the way a café really keeps it:
several sheets, Uzbek headers (one sheet in Cyrillic), header rows that are not row 1,
mixed date formats (14.11.2026 / 2026-11-14 / 14 noyabr 2026 / real date cells), mixed
amount formats (4 350 000 / 4,350,000 / 4,35 mln / numbers). A few deliberately broken
rows are added ON TOP of the real data (duplicate, empty amount, impossible date), so the
real totals stay identical after the M5 sync flags and skips them.
Dev/seed only: openpyxl is a dev dependency.
"""

from __future__ import annotations

import calendar
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from apps.ai.uz_format import MONTHS

from .demo import DemoBusiness, DemoTxn

M = Decimal(1_000_000)


def _date_text(d: date, style: int) -> str | date:
    if style == 0:
        return d.strftime("%d.%m.%Y")
    if style == 1:
        return d.isoformat()
    if style == 2:
        return f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    return d  # a real date cell


def _amount_text(a: Decimal, style: int) -> str | int:
    whole = int(a)
    if style == 0:
        return f"{whole:,}".replace(",", " ")
    if style == 1:
        return f"{whole:,}"
    if style == 2 and whole % 10_000 == 0 and whole >= M:
        return f"{(a / M).normalize():f}".replace(".", ",") + " mln"
    return whole


def _impossible_date(today: date) -> str:
    """e.g. "31.11.2026": day 31 in the nearest past 30-day month."""
    d = today.replace(day=1)
    for _ in range(12):
        d = (d - timedelta(days=1)).replace(day=1)
        if calendar.monthrange(d.year, d.month)[1] == 30:
            return f"31.{d.month:02d}.{d.year}"
    return f"30.02.{today.year}"


def export_xlsx(biz: DemoBusiness, path: str | Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    rng = random.Random(7)
    wb = Workbook()
    bold = Font(bold=True)

    # --- Kassa: the opening balance (asked at onboarding if missing) ---------------
    ws = wb.active
    ws.title = "Kassa"
    ws.append([f"{biz.name} — kassa qoldig'i"])
    ws.append([])
    ws.append(["Sana", "Qoldiq (so'm)", "Izoh"])
    ws.append(
        [
            biz.today.strftime("%d.%m.%Y"),
            _amount_text(biz.closing_cash_today, 0),
            "Kun oxiridagi qoldiq (naqd + bank)",
        ]
    )

    # --- Kirim: header on row 3 -----------------------------------------------------
    ws = wb.create_sheet("Kirim")
    ws.append([f"{biz.name} — kirimlar (savdo)"])
    ws.append([])
    ws.append(["Sana", "Summa (so'm)", "To'lov turi", "Izoh"])
    sales = [t for t in biz.txns if t.direction == "in"]
    for t in sales:
        ws.append(
            [
                _date_text(t.date, rng.choice((0, 0, 0, 1, 2, 3))),
                _amount_text(t.amount, rng.choice((0, 0, 1, 3))),
                "Naqd" if t.method == "naqd" else "Karta",
                t.note,
            ]
        )

    # --- Chiqim: expenses paid + planned payments (Muddat/Holati) ------------------
    ws = wb.create_sheet("Chiqim")
    ws.append(["Sana", "Summa (so'm)", "Nima uchun", "Kimga", "Muddat", "Naqd/karta", "Holati"])
    expenses: list[DemoTxn] = [t for t in biz.txns if t.direction == "out"]
    for t in expenses:
        what = (
            t.note
            if t.note and t.category in {"payroll", "loan", "rent", "tax", "supplier", "kommunal"}
            else t.category
        )
        ws.append(
            [
                _date_text(t.date, rng.choice((0, 0, 0, 1, 2))),
                _amount_text(t.amount, rng.choice((0, 0, 1, 2, 3))),
                what,
                t.counterparty,
                "",
                "Naqd" if t.method == "naqd" else "Uzcard" if t.method == "karta" else "Bank",
                "to'landi",
            ]
        )
    for o in biz.obligations:
        if o.status != "planned":
            continue
        ws.append(
            [
                "",
                _amount_text(o.amount, 0),
                o.title,
                o.counterparty,
                o.due_date.strftime("%d.%m.%Y"),
                "Bank",
                "kutilyapti" if o.priority == "critical" else "kutilyapti (kechiksa bo'ladi)",
            ]
        )
    # deliberately broken extra rows (flagged as DataIssue in M5, never counted twice)
    first = expenses[-1]
    ws.append(
        [
            first.date.strftime("%d.%m.%Y"),
            _amount_text(first.amount, 0),
            first.category,
            first.counterparty,
            "",
            "Naqd",
            "to'landi",
        ]
    )  # duplicate of a real row
    ws.append([biz.today.strftime("%d.%m.%Y"), "", "xo'jalik", "", "", "Naqd", "to'landi"])
    ws.append(
        [
            _impossible_date(biz.today),
            "350 000",
            "sabzavot",
            "Chorsu bozori",
            "",
            "Naqd",
            "to'landi",
        ]
    )

    # --- Oylik: Cyrillic headers, header on row 2 ----------------------------------
    ws = wb.create_sheet("Oylik")
    ws.append(["Иш ҳақи жадвали (ҳар ой 10-санада)"])
    ws.append(["№", "Ф.И.Ш.", "Лавозими", "Ойлик маош (сўм)", "Тўлов куни"])
    for i, e in enumerate(biz.employees, start=1):
        ws.append([i, e.name, e.role, int(e.salary), "10"])
    ws.append(["", "Жами", "", int(sum(e.salary for e in biz.employees)), ""])

    # --- Ta'minotchilar ----------------------------------------------------------------
    ws = wb.create_sheet("Ta'minotchilar")
    ws.append(["Kontragent", "Telefon", "To'lov kuni", "Odatdagi summa", "Izoh"])
    supplier = next(o for o in biz.obligations if o.category == "supplier")
    ws.append(
        [
            supplier.counterparty,
            "+998 90 123 45 67",
            "har oy 25",
            _amount_text(supplier.amount, 0),
            "Go'sht, oyiga bir marta hisob-kitob",
        ]
    )
    ws.append(["Chorsu bozori", "", "har kuni", "", "Sabzavot, naqd"])
    ws.append(["Non sexi", "+998 93 555 12 12", "har kuni", "", ""])

    # --- NBU kredit: loan schedule -------------------------------------------------
    ws = wb.create_sheet("NBU kredit")
    ws.append(["NBU kredit jadvali"])
    ws.append(["To'lov sanasi", "Asosiy qarz", "Foiz", "Jami to'lov", "Qoldiq qarz"])
    loans = [o for o in biz.obligations if o.category == "loan"]
    left = Decimal("180000000")
    for o in loans:
        interest = (left * Decimal("0.02")).quantize(Decimal(1))
        principal = o.amount - interest
        left -= principal
        ws.append([o.due_date, int(principal), int(interest), int(o.amount), int(left)])

    # --- Izohlar: a sheet the AI should ignore --------------------------------------
    ws = wb.create_sheet("Izohlar")
    ws.append(["Eslatmalar"])
    ws.append(["Gaz hisoblagichini tekshirish"])
    ws.append(["Yangi ofitsiant bilan shartnoma"])

    for sheet in wb.worksheets:
        for row in sheet.iter_rows(min_row=1, max_row=3):
            for cell in row:
                if isinstance(cell.value, str) and cell.value:
                    cell.font = bold
    out = Path(path).resolve()
    wb.save(out)
    return out
