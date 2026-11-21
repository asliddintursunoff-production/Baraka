"""Sheet -> mapping proposal: header detection, heuristics, then ONE LLM call for all sheets.

Merge rule per column: LLM and heuristic agree -> the higher confidence; they disagree ->
the LLM's field with confidence capped at 0.6 (the person confirms), unless the heuristic
is very sure (>= 0.9) and the LLM is not (< 0.7). No LLM (busy/down) -> heuristics only.
Columns below 0.8 are shown with "Tasdiqlang".
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from google.genai import types

from apps.ai import uz_format as uz
from config import app_settings as cfg

from .header import detect_header, header_signature
from .heuristics import guess_mapping
from .normalize import parse_amount
from .readers import SheetData, WorkbookData

log = logging.getLogger(__name__)
FIELDS = (
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
KINDS = (
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
FIELD_LABELS = {
    "date": "To'lov sanasi",
    "amount": "Summa",
    "direction": "Kirim yoki chiqim",
    "category": "Kategoriya",
    "counterparty": "Kontragent",
    "due_date": "To'lash muddati (due date)",
    "method": "To'lov usuli",
    "status": "Holati ustuni uchun maydon",
    "note": "Izoh",
    "ignore": "E'tiborsiz qoldirish",
}
KIND_LABELS = {
    "transactions_in": "Kirim (savdo)",
    "transactions_out": "Xarajatlar",
    "transactions_mixed": "Kirim va chiqim",
    "obligations_schedule": "To'lovlar jadvali",
    "payroll": "Ish haqi jadvali",
    "loan_schedule": "Kredit to'lovlari",
    "counterparties": "Ta'minotchilar ro'yxati",
    "cash_balance": "Kassa qoldig'i",
    "ignore": "E'tiborsiz",
}
CONFIRM_BELOW = cfg.MAPPING_CONFIDENCE_THRESHOLD


@dataclass
class ColumnProposal:
    index: int
    header: str
    sample: str
    field: str
    confidence: float
    question: str | None = None


@dataclass
class SheetProposal:
    title: str
    header_row: int  # 1-based sheet row number of the header
    header_signature: str
    data_rows: int
    kind: str
    kind_confidence: float
    columns: list[ColumnProposal] = field(default_factory=list)

    def payload(self, *, kind_label: str | None = None) -> dict[str, Any]:
        sure = sum(1 for c in self.columns if c.confidence >= CONFIRM_BELOW)
        amount_label = {
            "transactions_in": "Summa · kirim",
            "transactions_out": "Summa · chiqim",
        }.get(self.kind, "Summa")
        return {
            "title": self.title,
            "rows": self.data_rows,
            "rows_display": uz.group_digits(self.data_rows),
            "header_row": self.header_row,
            "kind": self.kind,
            "kind_label": kind_label or KIND_LABELS.get(self.kind, self.kind),
            "recognized": f"{len(self.columns)} ustundan {sure} tasi aniq tanildi",
            "columns": [
                {
                    "index": c.index,
                    "header": c.header,
                    "sample": c.sample,
                    "field": c.field,
                    "field_label": amount_label
                    if c.field == "amount"
                    else FIELD_LABELS.get(c.field, c.field),
                    "confidence": round(c.confidence, 2),
                    "status": "sure" if c.confidence >= CONFIRM_BELOW else "confirm",
                    "question": c.question,
                }
                for c in self.columns
            ],
        }


def sample_text(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, bool):
        return "ha" if value else "yo'q"
    if isinstance(value, int | float):
        if (
            20_000 <= float(value) <= 80_000 and float(value).is_integer()
        ):  # likely a Sheets date serial
            return (date(1899, 12, 30) + timedelta(days=int(value))).strftime("%d.%m.%Y")
        amt = parse_amount(value)
        return (
            uz.group_digits(int(amt))
            if amt is not None and amt == amt.to_integral_value()
            else str(value)
        )
    text = str(value).strip()
    return text[:40] + ("…" if len(text) > 40 else "")


def heuristic_sheet(sheet: SheetData) -> SheetProposal | None:
    rows = sheet.rows
    h = detect_header(rows)
    if h is None:
        return SheetProposal(sheet.title, 1, "", 0, "ignore", 0.9)
    headers = ["" if c is None else str(c).strip() for c in rows[h]]
    data = [r for r in rows[h + 1 :] if any(c not in (None, "") for c in r)]
    guess = guess_mapping(headers, data[: cfg.MAPPING_SAMPLE_ROWS], title=sheet.title)
    cols = []
    for g in guess.columns:
        if not g.header:
            continue
        sample = next(
            (
                sample_text(r[g.index])
                for r in data
                if g.index < len(r) and r[g.index] not in (None, "")
            ),
            "",
        )
        q = "Haqiqiy to'lovmi yoki rejami?" if g.field == "status" else None
        cols.append(ColumnProposal(g.index, g.header, sample, g.field, float(g.confidence), q))
    return SheetProposal(
        sheet.title,
        h + 1,
        header_signature(headers),
        len(data),
        guess.sheet_kind,
        float(guess.kind_confidence),
        cols,
    )


LLM_SCHEMA = {
    "type": "object",
    "properties": {
        "sheets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "kind": {"type": "string", "enum": list(KINDS)},
                    "kind_confidence": {"type": "number"},
                    "columns": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "index": {"type": "integer"},
                                "field": {"type": "string", "enum": list(FIELDS)},
                                "confidence": {"type": "number"},
                            },
                            "required": ["index", "field", "confidence"],
                        },
                    },
                },
                "required": ["title", "kind", "columns"],
            },
        }
    },
    "required": ["sheets"],
}


def _llm_prompt(wb: WorkbookData, props: list[SheetProposal]) -> str:
    parts = [
        "Kichik biznes (kafe/do'kon) buxgalteriya jadvali. Har bir varaq turini va har bir ustun "
        "ma'nosini aniqlang. Sarlavhalar o'zbek, rus yoki ingliz tilida bo'lishi mumkin.",
        f"Varaq turlari: {', '.join(KINDS)}. Ustun maydonlari: {', '.join(FIELDS)}.",
        "transactions_out ichida rejalashtirilgan to'lovlar ham bo'lishi mumkin (muddat + holat).",
        "Ishonch 0..1; aniq bo'lmasangiz 0.8 dan past qo'ying.",
        f"Fayl: {wb.name}",
    ]
    for sheet, p in zip(wb.sheets, props, strict=False):
        if p.kind == "ignore" and not p.columns:
            parts.append(f'Varaq "{sheet.title}": bo\'sh yoki faqat matn.')
            continue
        h = p.header_row - 1
        sample_rows = [r for r in sheet.rows[h + 1 :] if any(c not in (None, "") for c in r)][:5]
        cols = [
            f"{c.index}: {c.header!r} (masalan: {', '.join(sample_text(r[c.index]) for r in sample_rows if c.index < len(r))[:120]})"
            for c in p.columns
        ]
        parts.append(f'Varaq "{sheet.title}" ({p.data_rows} qator):\n  ' + "\n  ".join(cols))
    return "\n".join(parts)


def merge(p: SheetProposal, llm: dict[str, Any] | None) -> SheetProposal:
    if not llm:
        return p
    by_index = {int(c["index"]): c for c in llm.get("columns", []) if c.get("field") in FIELDS}
    for c in p.columns:
        lc = by_index.get(c.index)
        if lc is None:
            continue
        lf, lconf = str(lc["field"]), float(lc.get("confidence", 0.5))
        if lf == c.field:
            c.confidence = max(c.confidence, lconf)
        elif c.confidence >= 0.9 and lconf < 0.7:
            c.confidence = min(c.confidence, 0.85)
        else:
            c.field, c.confidence = lf, min(lconf, 0.6)
        if c.field == "status" and c.question is None:
            c.question = "Haqiqiy to'lovmi yoki rejami?"
    kind = llm.get("kind")
    kconf = float(llm.get("kind_confidence", 0.7))
    if kind in KINDS and kind != p.kind and kconf >= 0.7:
        p.kind, p.kind_confidence = str(kind), kconf
    elif kind == p.kind:
        p.kind_confidence = max(p.kind_confidence, kconf)
    return p


async def propose_workbook(wb: WorkbookData, *, use_llm: bool = True) -> list[SheetProposal]:
    props = [
        heuristic_sheet(s) or SheetProposal(s.title, 1, "", 0, "ignore", 0.5) for s in wb.sheets
    ]
    if not use_llm or not any(p.columns for p in props):
        return props
    from apps.ai.llm import AllModelsFailed, generate

    try:
        res = await generate(
            [types.Content(role="user", parts=[types.Part(text=_llm_prompt(wb, props))])],
            types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=LLM_SCHEMA,
                max_output_tokens=2000,
            ),
            deadline_s=12.0,
            kind="mapping",
        )
        data = json.loads(res.response.text or "{}")
    except (TimeoutError, AllModelsFailed, ValueError) as exc:
        log.info("mapping LLM unavailable, heuristics only: %s", str(exc)[:120])
        return props
    except Exception as exc:  # never block onboarding on the LLM
        log.warning("mapping LLM error, heuristics only: %s", str(exc)[:160])
        return props
    llm_by_title = {s.get("title"): s for s in data.get("sheets", []) if isinstance(s, dict)}
    return [merge(p, llm_by_title.get(p.title)) for p in props]


def needs_amount(value: Any) -> Decimal | None:
    return parse_amount(value)
