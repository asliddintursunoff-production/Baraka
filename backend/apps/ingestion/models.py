from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.tenancy.managers import TenantScopedModel


class SheetMapping(TenantScopedModel):
    class Kind(models.TextChoices):
        IN = "transactions_in", "Kirim"
        OUT = "transactions_out", "Chiqim"
        MIXED = "transactions_mixed", "Kirim/chiqim"
        SCHEDULE = "obligations_schedule", "To'lovlar jadvali"
        PAYROLL = "payroll", "Ish haqi"
        LOAN = "loan_schedule", "Kredit"
        COUNTERPARTIES = "counterparties", "Kontragentlar"
        CASH = "cash_balance", "Kassa qoldig'i"  # added: where the opening balance lives
        IGNORE = "ignore", "E'tiborsiz"

    source = models.ForeignKey("integrations.DataSource", on_delete=models.CASCADE)
    sheet_title = models.CharField(max_length=200)
    header_row = models.PositiveIntegerField(default=1)
    header_signature = models.CharField(max_length=64, blank=True)
    sheet_kind = models.CharField(max_length=24, choices=Kind.choices)
    column_map = models.JSONField(default=dict)
    confidence = models.JSONField(default=dict)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "sheet_title"], name="uniq_sheet_mapping")
        ]


class RawRow(TenantScopedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Faol"
        DELETED = "deleted", "O'chirilgan"
        IGNORED = "ignored", "E'tiborsiz"

    source = models.ForeignKey("integrations.DataSource", on_delete=models.CASCADE)
    sheet_title = models.CharField(max_length=200)
    row_index = models.PositiveIntegerField()
    row_hash = models.CharField(max_length=64)
    values = models.JSONField(default=list)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "sheet_title", "row_hash"], name="uniq_raw_row_hash"
            )
        ]


class DataIssue(TenantScopedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Ochiq"
        RESOLVED = "resolved", "Hal qilingan"
        IGNORED = "ignored", "E'tiborsiz"

    raw_row = models.ForeignKey(RawRow, null=True, blank=True, on_delete=models.CASCADE)
    kind = models.CharField(max_length=32)
    message_uz = models.CharField(max_length=300)
    suggestion = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["business", "status"], name="issue_business_status")]


class SyncRun(TenantScopedModel):
    """One sync of one source: the "Oxirgi yangilanishlar" log on the Sources page."""

    source = models.ForeignKey("integrations.DataSource", on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, default="running")  # running|ok|skipped|error
    rows_added = models.PositiveIntegerField(default=0)
    rows_deleted = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=300, blank=True)
    trigger = models.CharField(max_length=16, default="schedule")  # schedule|manual|confirm

    class Meta:
        indexes = [models.Index(fields=["business", "-started_at"], name="syncrun_business_time")]
