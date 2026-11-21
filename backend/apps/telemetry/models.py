"""Latency events (frontend + backend measurements)."""

from __future__ import annotations

from django.db import models


class LatencyEvent(models.Model):
    class Channel(models.TextChoices):
        VOICE = "voice", "voice"
        CHAT = "chat", "chat"
        API = "api", "api"

    # business FK is added in M2 together with the tenancy models.
    channel = models.CharField(max_length=8, choices=Channel.choices)
    name = models.CharField(max_length=64)
    ms = models.FloatField()  # a duration, not money
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["channel", "name", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.channel}:{self.name}={self.ms:.0f}ms"
