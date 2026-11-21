"""Plan approval. Only a person approves: the UI button, or Live after an explicit "ha"."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from apps.actions.audit import audit
from apps.actions.models import ActionPlan
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Business


class PlanNotFound(LookupError):
    pass


def approve_plan(
    business: Business, plan_id: int, user_id: int | None, *, actor: str
) -> ActionPlan:
    with tenant_context(business), transaction.atomic():
        plan: ActionPlan | None = ActionPlan.objects.select_for_update().filter(pk=plan_id).first()
        if plan is None:
            raise PlanNotFound(plan_id)
        if plan.status == ActionPlan.Status.APPROVED:
            return plan  # idempotent
        if plan.status != ActionPlan.Status.PROPOSED:
            raise PlanNotFound(plan_id)
        plan.status = ActionPlan.Status.APPROVED
        plan.approved_by_id = user_id
        plan.approved_at = timezone.now()
        plan.save(update_fields=["status", "approved_by", "approved_at"])
        if plan.kind == ActionPlan.Kind.PURCHASE_PLAN and plan.payload.get("date"):
            # "Execution" in the MVP = an in-app reminder on that morning. No money moves.
            d = datetime.fromisoformat(plan.payload["date"]).date()
            ActionPlan.objects.get_or_create(
                idempotency_key=f"reminder-for-plan:{plan.pk}",
                defaults={
                    "business": business,
                    "kind": ActionPlan.Kind.REMINDER,
                    "payload": {
                        "date": d.isoformat(),
                        "text": plan.payload.get("summary", ""),
                        "summary": plan.payload.get("summary", ""),
                        "plan_id": plan.pk,
                    },
                    "status": ActionPlan.Status.APPROVED,
                    "proposed_by": "ai",
                    "approved_by_id": user_id,
                    "approved_at": timezone.now(),
                    "due_at": datetime.combine(d, time(9, 0), ZoneInfo(business.timezone)),
                },
            )
        audit(
            actor,
            "plan_approved",
            tool="confirm_plan",
            args={"plan_id": plan.pk, "kind": plan.kind},
        )
    return plan
