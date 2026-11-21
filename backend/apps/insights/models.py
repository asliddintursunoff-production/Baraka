from __future__ import annotations

from django.db import models

from apps.tenancy.managers import TenantScopedModel


class ForecastSnapshot(TenantScopedModel):
    created_at = models.DateTimeField(auto_now_add=True)
    horizon_days = models.PositiveIntegerField()
    daily = models.JSONField()  # [{date, open, inflow, outflow, close, p10, p90}]
    min_balance = models.DecimalField(max_digits=18, decimal_places=2)
    min_date = models.DateField()
    first_shortage_date = models.DateField(null=True, blank=True)
    verdict = models.CharField(max_length=8, blank=True)  # yes|risky|no ('' = not enough data)
    inputs_hash = models.CharField(max_length=64)
    inputs = models.JSONField()  # canonical engine input: the cache-miss path is one SELECT

    class Meta:
        indexes = [
            models.Index(fields=["business", "-created_at"], name="snapshot_business_latest")
        ]


class Alert(TenantScopedModel):
    class Severity(models.TextChoices):
        INFO = "info", "Ma'lumot"
        WARN = "warn", "Ehtiyot"
        DANGER = "danger", "Xavf"

    class Status(models.TextChoices):
        NEW = "new", "Yangi"
        SEEN = "seen", "Ko'rilgan"
        DISMISSED = "dismissed", "Yopilgan"

    kind = models.CharField(max_length=32)
    severity = models.CharField(max_length=8, choices=Severity.choices)
    date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    text_uz = models.TextField()
    dedupe_key = models.CharField(max_length=160, unique=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    snapshot = models.ForeignKey(ForecastSnapshot, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "status", "-created_at"], name="alert_business_new")
        ]
