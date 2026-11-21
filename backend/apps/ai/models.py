from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.tenancy.managers import TenantScopedModel


class Conversation(TenantScopedModel):
    class Channel(models.TextChoices):
        CHAT = "chat", "Chat"
        VOICE = "voice", "Ovoz"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    channel = models.CharField(max_length=8, choices=Channel.choices, default=Channel.CHAT)
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Message(TenantScopedModel):
    class Role(models.TextChoices):
        USER = "user", "Foydalanuvchi"
        ASSISTANT = "assistant", "AI"
        SYSTEM = "system", "Tizim"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=Role.choices)
    author_name = models.CharField(max_length=80, blank=True)
    content = models.TextField(blank=True)
    answer = models.JSONField(null=True, blank=True)  # structured answer (verdict, headline...)
    ui_blocks = models.JSONField(default=list, blank=True)
    tool_calls = models.JSONField(default=list, blank=True)
    model = models.CharField(max_length=64, blank=True)  # which model answered (chain)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["conversation", "created_at"], name="message_conv_time")]
