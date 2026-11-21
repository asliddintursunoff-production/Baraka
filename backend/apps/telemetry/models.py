"""Latency events (frontend + backend measurements)."""

from __future__ import annotations

from django.db import models


class LatencyEvent(models.Model):
    class Channel(models.TextChoices):
        VOICE = "voice", "voice"
        CHAT = "chat", "chat"
        API = "api", "api"

    business = models.ForeignKey(
        "tenancy.Business", null=True, blank=True, on_delete=models.CASCADE
    )
    channel = models.CharField(max_length=8, choices=Channel.choices)
    name = models.CharField(max_length=64)
    ms = models.FloatField()  # a duration, not money
    meta = models.JSONField(default=dict, blank=True)
    model = models.CharField(max_length=64, blank=True)  # LLM that answered, if any
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["channel", "name", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.channel}:{self.name}={self.ms:.0f}ms"


class AiUsage(models.Model):
    """One billed AI call (LLM, Live, TTS/STT, embedding) with its estimated cost."""

    business = models.ForeignKey(
        "tenancy.Business", null=True, blank=True, on_delete=models.SET_NULL
    )
    kind = models.CharField(max_length=16)  # chat | live | tts | stt | light | mapping | embedding
    model = models.CharField(max_length=64)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    seconds = models.IntegerField(default=0)  # Live minutes are billed by audio time
    cost_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self) -> str:
        return f"{self.kind}:{self.model}=${self.cost_usd}"
