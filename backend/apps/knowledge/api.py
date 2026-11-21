from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from django.utils import timezone
from rest_framework.request import Request
from rest_framework.response import Response

from apps.actions.audit import audit
from apps.ai import uz_format as uz
from apps.ai.tools import ToolContext
from apps.insights.api import USAGE_ORDER
from apps.insights.forecasting import invalidate, refresh_forecast
from apps.tenancy.api import BusinessAPIView
from apps.tenancy.models import Membership
from config import app_settings as cfg

from .learning import accept_candidate, candidate_from_text
from .models import BusinessRule, ForecastAccuracy, MemoryItem, RuleCandidate

SEGMENT_USAGE_UZ = {
    "forecast": "Prognozingizda hisobga olingan",
    "advice": "Maslahatlarda hisobga olinadi",
    "alerts": "Ogohlantirishlarda ishlatiladi",
    "later": "Yozgacha hali vaqt bor",
}


class CandidateAcceptView(BusinessAPIView):
    def post(self, request: Request, candidate_id: int) -> Response:
        if not RuleCandidate.objects.filter(pk=candidate_id).exists():
            return Response({"error": "not_found"}, status=404)
        rule = accept_candidate(self.business, candidate_id, request.user.pk)
        return Response({"rule_id": rule.pk, "text_uz": rule.text_uz, "forecast_changed": True})


class CandidateRejectView(BusinessAPIView):
    def post(self, request: Request, candidate_id: int) -> Response:
        n = RuleCandidate.objects.filter(
            pk=candidate_id, status=RuleCandidate.Status.PENDING
        ).update(status=RuleCandidate.Status.REJECTED)
        if n:
            audit(f"user:{request.user.pk}", "rule_rejected", args={"candidate_id": candidate_id})
        return Response({"ok": True})


ROLE_UZ = {"owner": "", "accountant": " (hisobchi)", "viewer": ""}


def _when(dt: datetime) -> str:
    d = timezone.localtime(dt).date()
    days = (timezone.localdate() - d).days
    return "bugun" if days <= 0 else "kecha" if days == 1 else uz.format_date(d)


def _effect_uz(r: BusinessRule) -> str:
    ef = r.effect or {}
    if r.type == "payment_shift":
        return f"to'lov sanasi +{ef.get('days')} kun"
    if r.type == "priority":
        return "eng muhim to'lov" if ef.get("level") == "critical" else "kechiktirsa bo'ladi"
    if r.type == "recurring":
        return "har oylik doimiy to'lov"
    if r.type == "weekday_factor":
        m = Decimal(str(ef.get("multiplier", "1")))
        return "savdo oshiriladi" if m >= 1 else "savdo kamaytiriladi"
    if r.type == "ignore":
        return "hisobga olinmaydi"
    return "prognozga qo'shildi"


def _rule_row(r: BusinessRule, roles: dict[int, str]) -> dict[str, Any]:
    name = (r.author.first_name or r.author.username) if r.author else "Siz"
    role = ROLE_UZ.get(roles.get(r.author_id or 0, ""), "")
    who = (
        f"AI sezdi, {name} tasdiqladi"
        if r.source == BusinessRule.Source.AI_CONFIRMED
        else f"{name}{role} aytdi"
    )
    return {
        "id": r.pk,
        "text": r.text_uz,
        "meta": f"{who} · {_when(r.created_at)} · prognozda: {_effect_uz(r)}",
        "enabled": r.enabled,
    }


class KnowledgeView(BusinessAPIView):
    """AI bilimi page: accuracy by week, pending candidates, rules, segment insights."""

    def get(self, request: Request) -> Response:
        b = self.business
        weeks = list(ForecastAccuracy.objects.order_by("-week_start")[:4])[::-1]
        roles = dict(Membership.objects.filter(business=b).values_list("user_id", "role"))
        rules = BusinessRule.objects.select_related("author").order_by("-created_at")
        segs = list(
            MemoryItem.objects.filter(business__isnull=True, kind="segment_insight").values(
                "text", "meta"
            )
        )
        segs.sort(key=lambda r: USAGE_ORDER.index((r["meta"] or {}).get("usage", "later")))
        return Response(
            {
                "business": b.name,
                "accuracy": [
                    {"label": f"{i + 1}-hafta", "pct": int((w.mape * 100).to_integral_value())}
                    for i, w in enumerate(weeks)
                ],
                "candidates": [
                    {"id": c.pk, "text": c.text_uz}
                    for c in RuleCandidate.objects.filter(
                        status=RuleCandidate.Status.PENDING, origin=RuleCandidate.Origin.PATTERN
                    ).order_by("-created_at")[:5]
                ],
                "rules": [_rule_row(r, roles) for r in rules[:30]],
                "segment": [
                    {
                        "text": s["text"],
                        "usage": SEGMENT_USAGE_UZ.get((s["meta"] or {}).get("usage", ""), ""),
                    }
                    for s in segs
                ],
                "segment_min": cfg.SEGMENT_MIN_BUSINESSES,
            }
        )


class RuleCreateView(BusinessAPIView):
    """ "+ Qoida yozish": plain Uzbek text -> rule (parser first, light LLM only if needed)."""

    def post(self, request: Request) -> Response:
        text = (
            str((request.data or {}).get("text", "")).strip()[:300]
            if isinstance(request.data, dict)
            else ""
        )
        if len(text) < 5:
            return Response(
                {"error": "empty", "message": "Qoidani bir jumla bilan yozing."}, status=400
            )
        ctx = ToolContext(
            business=self.business, user_id=request.user.pk, channel="api", last_user_text=text
        )
        cand = candidate_from_text(ctx, text)
        if cand is None:
            return Response(
                {
                    "error": "not_understood",
                    "message": "Buni qoida sifatida tushunmadim. Masalan: «Agro Go'shtga doim 15 kun kechiktirib to'laymiz».",
                },
                status=400,
            )
        if cand.get("duplicate"):
            return Response({"error": "duplicate", "message": cand["text"]}, status=409)
        rule = accept_candidate(self.business, int(cand["id"]), request.user.pk)
        audit(f"user:{request.user.pk}", "rule_written", args={"rule_id": rule.pk})
        return Response({"ok": True, "rule_id": rule.pk, "text": cand["text"].replace("**", "")})


class RuleToggleView(BusinessAPIView):
    def post(self, request: Request, rule_id: int) -> Response:
        r = BusinessRule.objects.filter(pk=rule_id).first()
        if r is None:
            return Response({"error": "not_found"}, status=404)
        enabled = (
            bool((request.data or {}).get("enabled"))
            if isinstance(request.data, dict)
            else not r.enabled
        )
        r.enabled = enabled
        r.save(update_fields=["enabled"])
        invalidate(self.business.pk)
        refresh_forecast(self.business)  # the snapshot's stored inputs still hold the old rules
        audit(f"user:{request.user.pk}", "rule_toggled", args={"rule_id": r.pk, "enabled": enabled})
        return Response({"ok": True, "enabled": enabled})
