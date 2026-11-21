from __future__ import annotations

from typing import Any, ClassVar

from django.conf import settings
from django.db import models
from pgvector.django import HnswIndex, VectorField

from apps.tenancy.managers import TenantOrGlobalManager, TenantScopedModel
from config import app_settings as cfg


class BusinessRule(TenantScopedModel):
    class Source(models.TextChoices):
        USER = "user", "Foydalanuvchi"
        AI_CONFIRMED = "ai_confirmed", "AI sezdi, tasdiqlandi"

    type = models.CharField(max_length=16)  # payment_shift|recurring|weekday_factor|priority|ignore
    target = models.JSONField(default=dict)
    effect = models.JSONField(default=dict)
    text_uz = models.CharField(max_length=300)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.USER)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class RuleCandidate(TenantScopedModel):
    class Origin(models.TextChoices):
        CORRECTION = "correction", "Tuzatish"
        PATTERN = "pattern", "AI sezdi"

    class Status(models.TextChoices):
        PENDING = "pending", "Kutilmoqda"
        ACCEPTED = "accepted", "Qabul qilindi"
        REJECTED = "rejected", "Rad etildi"

    proposed = models.JSONField()  # {type, target, effect}
    text_uz = models.CharField(max_length=300)
    origin = models.CharField(max_length=16, choices=Origin.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)


class ForecastParams(TenantScopedModel):
    weekday_factors = models.JSONField(default=list)  # 7 floats, Mon..Sun
    variable_cost_ratio = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["business"], name="uniq_params")]


class ForecastAccuracy(TenantScopedModel):
    week_start = models.DateField()
    mape = models.DecimalField(max_digits=6, decimal_places=4)  # 0.0600 = 6 %
    n_days = models.PositiveIntegerField(default=7)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["business", "week_start"], name="uniq_accuracy_week")
        ]


class SegmentStats(models.Model):
    """Anonymous aggregate over >= 5 businesses. NOT linked to any business."""

    segment_key = models.CharField(max_length=64)
    metric = models.CharField(max_length=64)
    value = models.JSONField()
    n_businesses = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["segment_key", "metric"], name="uniq_segment_metric"),
            models.CheckConstraint(
                condition=models.Q(n_businesses__gte=cfg.SEGMENT_MIN_BUSINESSES),
                name="segment_min_businesses",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.segment_key}:{self.metric}"


class MemoryItem(models.Model):
    """Text memory with an embedding. business NULL = global (segment insight)."""

    class Kind(models.TextChoices):
        RULE = "rule", "Qoida"
        NOTE = "note", "Eslatma"
        CORRECTION = "correction", "Tuzatish"
        SUMMARY = "conversation_summary", "Suhbat xulosasi"
        SEGMENT = "segment_insight", "Segment bilimi"

    business = models.ForeignKey(
        "tenancy.Business", null=True, blank=True, on_delete=models.CASCADE, db_index=True
    )
    kind = models.CharField(max_length=24, choices=Kind.choices)
    text = models.TextField()
    embedding = VectorField(dimensions=cfg.EMBEDDING_DIM, null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects: ClassVar[TenantOrGlobalManager] = TenantOrGlobalManager()
    unscoped: ClassVar[models.Manager[Any]] = models.Manager()

    class Meta:
        indexes = [
            HnswIndex(
                name="memory_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self) -> str:
        return f"{self.kind}:{self.text[:40]}"
