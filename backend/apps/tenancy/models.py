"""Businesses, memberships. Users are Django auth users (email = username)."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from config import app_settings as cfg


class Business(models.Model):
    class Kind(models.TextChoices):
        CAFE = "cafe", "Kafe"
        SHOP = "shop", "Do'kon"
        RESTAURANT = "restaurant", "Restoran"
        PHARMACY = "pharmacy", "Dorixona"
        OTHER = "other", "Boshqa"

    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.CAFE)
    city = models.CharField(max_length=64, default="Toshkent")
    safe_min_balance = models.DecimalField(
        max_digits=18, decimal_places=2, default=cfg.DEFAULT_SAFE_MIN_BALANCE
    )
    timezone = models.CharField(max_length=64, default=cfg.DEFAULT_TIMEZONE)
    segment_key = models.CharField(max_length=64, blank=True, db_index=True)
    staff_count = models.PositiveIntegerField(null=True, blank=True)
    seed_tag = models.CharField(max_length=16, blank=True, db_index=True)  # rows made by seed_demo
    is_demo = models.BooleanField(default=False)  # seeded demo: never mixed with a real business
    profile_completed = models.BooleanField(default=True)  # False right after /register
    salary_day = models.PositiveSmallIntegerField(null=True, blank=True)  # 1..31 (onboarding)
    # reconciliation / plausibility / freshness of the connected data (apps.ingestion.quality)
    data_quality = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "businesses"

    def __str__(self) -> str:
        return self.name

    @property
    def safe_min(self) -> Decimal:
        return Decimal(self.safe_min_balance)


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Egasi"
        ACCOUNTANT = "accountant", "Hisobchi"
        VIEWER = "viewer", "Kuzatuvchi"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.OWNER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "business"], name="uniq_membership")]

    def __str__(self) -> str:
        return f"{self.user_id}@{self.business_id}:{self.role}"
