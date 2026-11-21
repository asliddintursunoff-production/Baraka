from __future__ import annotations

from django.db import models

from apps.tenancy.managers import TenantScopedModel


class DataSource(TenantScopedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Faol"
        PAUSED = "paused", "To'xtatilgan"
        ERROR = "error", "Xato"

    spreadsheet_id = models.CharField(max_length=128)
    title = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    auto_sync = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["business", "spreadsheet_id"], name="uniq_source")
        ]


class GoogleCredential(TenantScopedModel):
    encrypted_refresh_token = models.TextField()  # Fernet, key derived from DJANGO_SECRET_KEY
    scopes = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
