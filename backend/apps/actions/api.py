"""Plans and reminders. The AI only proposes (status=proposed); a person approves.

A reminder the user creates with a button is approved immediately (the click is the
consent). Idempotency keys make retries safe (no duplicates).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from apps.ai import uz_format as uz
from apps.tenancy.api import BusinessAPIView
from apps.tenancy.context import today_for

from .audit import audit
from .models import ActionPlan

REMINDER_HOUR = time(9, 0)


def plan_payload(p: ActionPlan) -> dict[str, Any]:
    return {
        "id": p.pk,
        "kind": p.kind,
        "status": p.status,
        "payload": p.payload,
        "due_at": p.due_at.isoformat() if p.due_at else None,
        "summary": p.payload.get("summary", ""),
    }


class ReminderIn(serializers.Serializer[dict[str, object]]):
    kind = serializers.ChoiceField(choices=["reminder"])
    date = serializers.DateField()
    text = serializers.CharField(max_length=200)


class ActionCreateView(BusinessAPIView):
    def post(self, request: Request) -> Response:
        s = ReminderIn(data=request.data)
        s.is_valid(raise_exception=True)
        b = self.business
        d = s.validated_data["date"]
        if d < today_for(b):
            return Response(
                {"error": "past_date", "message": "O'tgan sanaga eslatma qo'yib bo'lmaydi."},
                status=400,
            )
        text = s.validated_data["text"]
        digest = hashlib.sha256(text.encode()).hexdigest()[:10]
        key = f"user-reminder:{b.pk}:{d.isoformat()}:{digest}"
        due = datetime.combine(d, REMINDER_HOUR, ZoneInfo(b.timezone))
        summary = f"{uz.format_date(d)} 09:00 — {text}"
        try:
            with transaction.atomic():
                plan, created = ActionPlan.objects.get_or_create(
                    idempotency_key=key,
                    defaults={
                        "business": b,
                        "kind": ActionPlan.Kind.REMINDER,
                        "payload": {"date": d.isoformat(), "text": text, "summary": summary},
                        "status": ActionPlan.Status.APPROVED,
                        "proposed_by": "user",
                        "approved_by_id": request.user.pk,
                        "approved_at": timezone.now(),
                        "due_at": due,
                    },
                )
        except IntegrityError:
            plan, created = ActionPlan.objects.get(idempotency_key=key), False
        if created:
            audit(
                f"user:{request.user.pk}",
                "reminder_created",
                args={"plan_id": plan.pk, "date": d.isoformat()},
            )
        return Response(plan_payload(plan), status=201 if created else 200)


class RemindersView(BusinessAPIView):
    def get(self, request: Request) -> Response:
        since = timezone.now() - timedelta(days=1)
        plans = ActionPlan.objects.filter(
            kind=ActionPlan.Kind.REMINDER, status=ActionPlan.Status.APPROVED, due_at__gte=since
        ).order_by("due_at")[:50]
        return Response({"reminders": [plan_payload(p) for p in plans]})


class ActionApproveView(BusinessAPIView):
    """The UI button "Ha, shunday qilamiz" — a person approves (idempotent)."""

    def post(self, request: Request, plan_id: int) -> Response:
        from apps.ai.plans import PlanNotFound, approve_plan

        try:
            plan = approve_plan(
                self.business, plan_id, request.user.pk, actor=f"user:{request.user.pk}"
            )
        except PlanNotFound:
            return Response({"error": "not_found", "message": "Reja topilmadi."}, status=404)
        return Response(
            {"id": plan.pk, "status": plan.status, "summary": plan.payload.get("summary", "")}
        )
