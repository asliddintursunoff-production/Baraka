from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.tenancy.managers import TenantScopedModel


class ActionPlan(TenantScopedModel):
    class Kind(models.TextChoices):
        REMINDER = "reminder", "Eslatma"
        SPENDING_LIMIT = "spending_limit", "Xarajat chegarasi"
        PURCHASE_PLAN = "purchase_plan", "Xarid rejasi"
        RECORD_DEBT = "record_debt", "Qarzni yozish"

    class Status(models.TextChoices):
        PROPOSED = "proposed", "Taklif"
        APPROVED = "approved", "Tasdiqlangan"
        DONE = "done", "Bajarildi"
        CANCELLED = "cancelled", "Bekor"

    kind = models.CharField(max_length=16, choices=Kind.choices)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PROPOSED)
    idempotency_key = models.CharField(max_length=120, unique=True)
    proposed_by = models.CharField(max_length=8, default="ai")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)  # reminders: when to show
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["business", "status", "due_at"], name="plan_business_due")]


class AuditLog(TenantScopedModel):
    actor = models.CharField(max_length=120)  # "user:12" | "ai" | "scheduler"
    event = models.CharField(max_length=48)
    tool = models.CharField(max_length=48, blank=True)
    args = models.JSONField(default=dict, blank=True)
    result_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["business", "-created_at"], name="audit_business_time")]
