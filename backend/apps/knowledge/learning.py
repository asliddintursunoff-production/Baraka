"""Corrections -> RuleCandidate -> (person confirms) -> BusinessRule -> forecast changes.

Parsing order: a deterministic parser for the common phrasing ("X ga doim 15 kun
kechiktirib to'laymiz"), then the `light` model with structured output. The example and
the warning shown to the user are computed by the engine, never by the LLM.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import replace
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db import transaction

from apps.actions.audit import audit
from apps.ai import uz_format as uz
from apps.ai.uz_parse import parse_number_words
from apps.engine import EngineError, RuleIn, forecast, norm
from apps.finance.models import Counterparty
from apps.insights import advice
from apps.insights.forecasting import invalidate, refresh_forecast
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Business

from .models import BusinessRule, MemoryItem, RuleCandidate

if TYPE_CHECKING:
    from apps.ai.tools import ToolContext

log = logging.getLogger(__name__)
_SHIFT = re.compile(
    r"(\d+|[a-z' ]+?)\s*kun\w*\s*(kechiktirib|kech|keyin|so'ng|кейин)", re.IGNORECASE
)


def _clean(text: str) -> str:
    return re.sub(r"[‘’ʻʼ`]", "'", text).lower()


def _find_counterparty(text: str) -> str | None:
    t = norm(text)
    names = list(Counterparty.objects.values_list("name", flat=True))
    names.sort(key=len, reverse=True)
    for n in names:
        if norm(n) in t:
            return str(n)
    return None


def parse_rule(text: str) -> dict[str, Any] | None:
    """Deterministic: payment shift for a known counterparty."""
    t = _clean(text)
    m = _SHIFT.search(t)
    cp = _find_counterparty(text)
    if not (m and cp):
        return None
    raw = m.group(1).strip()
    days = (
        int(raw)
        if raw.isdigit()
        else (int(parse_number_words(raw)[0]) if parse_number_words(raw) else 0)
    )
    if not 1 <= days <= 120:
        return None
    return {"type": "payment_shift", "target": {"counterparty": cp}, "effect": {"days": days}}


RULE_SCHEMA = {
    "type": "object",
    "properties": {
        "understood": {"type": "boolean"},
        "type": {
            "type": "string",
            "enum": ["payment_shift", "recurring", "weekday_factor", "priority", "ignore"],
        },
        "counterparty": {"type": "string"},
        "category": {"type": "string"},
        "title": {"type": "string"},
        "days": {"type": "integer"},
        "amount": {"type": "integer"},
        "day_of_month": {"type": "integer"},
        "weekdays": {"type": "array", "items": {"type": "integer"}},
        "multiplier": {"type": "number"},
        "level": {"type": "string", "enum": ["critical", "deferrable", "discretionary"]},
    },
    "required": ["understood"],
}


def llm_rule(text: str) -> dict[str, Any] | None:
    from google.genai import types

    from apps.ai.gemini import client
    from config import app_settings as cfg

    known = list(Counterparty.objects.values_list("name", flat=True)[:40])
    prompt = (
        "Foydalanuvchi biznes qoidasini aytdi. Uni JSON ga aylantir. Raqamlarni o'zing o'ylab topma, "
        "faqat matnda borini ol. Tushunmasang understood=false.\n"
        f"Ma'lum kontragentlar: {', '.join(known)}\nMatn: {text}"
    )
    try:
        r = client().models.generate_content(
            model=cfg.AI_MODELS["light"],
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=RULE_SCHEMA,
                max_output_tokens=300,
            ),
        )
        data = json.loads(r.text or "{}")
    except Exception as exc:  # LLM unavailable: no candidate rather than a guess
        log.warning("rule extraction failed: %s", str(exc)[:200])
        return None
    if not data.get("understood"):
        return None
    t = data.get("type")
    if t == "payment_shift" and data.get("counterparty") and data.get("days"):
        return {
            "type": t,
            "target": {"counterparty": data["counterparty"]},
            "effect": {"days": int(data["days"])},
        }
    if t == "recurring" and data.get("title") and data.get("amount") and data.get("day_of_month"):
        return {
            "type": t,
            "target": {"title": data["title"]},
            "effect": {
                "amount": str(data["amount"]),
                "day_of_month": int(data["day_of_month"]),
                "priority": data.get("level", "critical"),
            },
        }
    if t == "priority" and data.get("level") and (data.get("counterparty") or data.get("category")):
        key = "counterparty" if data.get("counterparty") else "category"
        return {"type": t, "target": {key: data[key]}, "effect": {"level": data["level"]}}
    if t == "ignore" and (data.get("counterparty") or data.get("category")):
        key = "counterparty" if data.get("counterparty") else "category"
        return {"type": t, "target": {key: data[key]}, "effect": {}}
    if t == "weekday_factor" and data.get("weekdays") and data.get("multiplier"):
        return {
            "type": t,
            "target": {"weekdays": data["weekdays"]},
            "effect": {"multiplier": str(data["multiplier"])},
        }
    return None


def describe(rule: dict[str, Any]) -> str:
    t, tg, ef = rule["type"], rule["target"], rule["effect"]
    if t == "payment_shift":
        return f"Endi {uz.add_case(tg['counterparty'], 'ga')} to'lovni har doim **{ef['days']} kun keyin** deb hisoblayman."
    if t == "recurring":
        return f'Endi "{tg["title"]}" uchun har oyning {ef["day_of_month"]}-sanasida {uz.format_mln(Decimal(str(ef["amount"])))} to\'lov deb hisoblayman.'
    if t == "priority":
        what = tg.get("counterparty") or tg.get("category")
        return f"Endi {what} to'lovini {'muhim' if ef['level'] == 'critical' else 'kechiktirsa bo`ladigan'} deb hisoblayman."
    if t == "ignore":
        return f"Endi {tg.get('counterparty') or tg.get('category')} yozuvlarini hisobga olmayman."
    return "Endi savdoni shu kunlarda boshqacha hisoblayman."


def _impact(ctx: ToolContext, rule: dict[str, Any]) -> tuple[str, str]:
    """Engine-computed example + warning for the candidate rule."""
    inp = ctx.cached.inp
    cand = RuleIn(type=rule["type"], target=rule["target"], effect=rule["effect"], id="candidate")
    try:
        after = forecast(replace(inp, rules=(*inp.rules, cand)), 90)
    except EngineError:
        return "", ""
    before = ctx.base
    example = ""
    if rule["type"] == "payment_shift":
        who = norm(rule["target"]["counterparty"])
        moved = [
            p for p in after.obligations if norm(p.counterparty) == who and p.date != p.due_date
        ]
        if moved:
            p = moved[0]
            example = f"Masalan, {uz.format_date(p.due_date)}dagi to'lov {uz.format_date(p.date, 'ga')} o'tadi."
    warning = ""
    d = after.min_date
    heavier = len(advice.payments_on(after, d)) > len(advice.payments_on(before, d))
    if heavier or after.min_balance < before.min_balance:
        crit = [p for p in advice.payments_on(after, d) if p.priority == "critical"]
        words = advice.join_uz([advice.payment_word(p) for p in crit]) or "majburiy to'lovlar"
        warning = f"Lekin e'tibor bering: {uz.format_date(d)} yanada og'irlashadi. Shu kuni birinchi {words}ni to'lang."
    return example, warning


def candidate_from_text(ctx: ToolContext, text: str) -> dict[str, Any] | None:
    with tenant_context(ctx.business):
        rule = parse_rule(text) or llm_rule(text)
        if rule is None:
            return None
        exists = BusinessRule.objects.filter(
            enabled=True, type=rule["type"], target=rule["target"]
        ).first()
        if exists:
            return {
                "id": None,
                "text": f"Bu qoida allaqachon bor: {exists.text_uz}",
                "example": "",
                "warning": "",
                "say": "Bu qoida allaqachon bor.",
                "duplicate": True,
            }
        sentence = describe(rule)
        example, warning = _impact(ctx, rule)
        cand = RuleCandidate.objects.create(
            business=ctx.business,
            proposed={**rule, "source_text": text},
            text_uz=text[:300],
            origin=RuleCandidate.Origin.CORRECTION,
        )
    say = "Tushundim. " + sentence.replace("**", "") + (" " + warning if warning else "")
    return {
        "id": cand.pk,
        "text": "Tushundim, eslab qoldim. " + sentence,
        "example": example,
        "warning": warning,
        "say": say,
    }


def accept_candidate(business: Business, candidate_id: int, user_id: int | None) -> BusinessRule:
    with tenant_context(business), transaction.atomic():
        cand = RuleCandidate.objects.select_for_update().get(pk=candidate_id)
        if cand.status == RuleCandidate.Status.ACCEPTED:
            existing = BusinessRule.objects.filter(
                target=cand.proposed.get("target"), type=cand.proposed.get("type")
            ).first()
            if existing is not None:
                found: BusinessRule = existing
                return found
        rule = cand.proposed
        text = describe(rule).replace("**", "").removeprefix("Endi ").rstrip(".")
        br: BusinessRule = BusinessRule.objects.create(
            business=business,
            type=rule["type"],
            target=rule["target"],
            effect=rule["effect"],
            text_uz=(cand.text_uz if cand.origin == RuleCandidate.Origin.CORRECTION else text)[
                :300
            ],
            source=BusinessRule.Source.USER
            if cand.origin == RuleCandidate.Origin.CORRECTION
            else BusinessRule.Source.AI_CONFIRMED,
            author_id=user_id,
        )
        cand.status = RuleCandidate.Status.ACCEPTED
        cand.save(update_fields=["status"])
        MemoryItem.objects.create(
            business=business,
            kind=MemoryItem.Kind.RULE,
            text=br.text_uz,
            meta={"rule_id": br.pk, "source": br.source},
        )
        audit(f"user:{user_id}", "rule_accepted", args={"candidate_id": cand.pk, "rule_id": br.pk})
    invalidate(business.pk)
    refresh_forecast(business)
    return br
