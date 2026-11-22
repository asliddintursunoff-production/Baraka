"""Live voice: session token with preloaded context (no retrieval on the voice path),
prefetch on hover (P3), and saving the finished conversation."""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.db import connections
from rest_framework.request import Request
from rest_framework.response import Response

from apps.insights import advice
from apps.insights.forecasting import get_forecast
from apps.knowledge.models import BusinessRule, MemoryItem
from apps.telemetry import timing
from apps.telemetry.models import AiUsage
from apps.tenancy.api import BusinessAPIView
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Business
from config import app_settings as cfg

from . import budget
from . import uz_format as uz
from .gemini import GeminiNotConfigured, scrub
from .live import live_config, mint_token
from .models import Conversation, Message
from .prompts import live_system_instruction
from .tools import TOOLS

log = logging.getLogger(__name__)


def live_context(business: Business) -> list[str]:
    """<= ~1 500 tokens: cash, hardest day, next 5 payments, top 10 rules/notes."""
    base = get_forecast(business).result
    if base.insufficient_data:
        return ["Ma'lumot kam: ishonchli prognoz uchun kamida 2 haftalik tarix kerak."]
    cash = base.close_on(base.today)
    d = base.min_date
    pays = advice.payments_on(base, d)
    from .tools import freshness_note

    fresh = freshness_note(business)
    lines = [
        f"Hozirgi kassa: {uz.format_mln(cash)} ({uz.speech_amount(cash)})"
        + (f" — {fresh}. Kassa haqida gapirganda shu sanani ayt." if fresh else "."),
        f"Eng qiyin kun: {uz.format_date(d)} ({uz.uz_ordinal_date(d)}), kassada {uz.format_mln(base.min_balance)} "
        f"({uz.speech_amount(base.min_balance)}) qoladi"
        + (
            f"; o'sha kuni {advice.join_uz([advice.payment_word(p) for p in pays])}."
            if pays
            else "."
        ),
        f"Xavfsiz chegara: {uz.format_mln(base.safe_min)} ({uz.speech_amount(base.safe_min)}).",
        "Keyingi majburiy to'lovlar:",
    ]
    for p in [o for o in base.obligations if o.date > base.today][:5]:
        lines.append(
            f"  {uz.format_date(p.date)} ({uz.uz_ordinal_date(p.date)}) — {p.title}: "
            f"{uz.format_mln(p.amount)} ({uz.speech_amount(p.amount)})"
        )
    rules = list(
        BusinessRule.objects.filter(enabled=True)
        .order_by("-created_at")
        .values_list("text_uz", flat=True)[:10]
    )
    notes = list(
        MemoryItem.objects.filter(business=business, kind="note")
        .order_by("-created_at")
        .values_list("text", flat=True)[:3]
    )
    if rules or notes:
        lines.append("Tasdiqlangan qoidalar va eslatmalar: " + "; ".join([*rules, *notes]))
    if business.staff_count:
        lines.append(f"Xodimlar soni: {business.staff_count}.")
    from .chat import recent_dialogue
    from .growth_tools import market_facts_text

    lines.append(market_facts_text()[:1500])

    from .digest import digest_for

    lines.append("BIZNES DIGEST (raqamlar faqat shu yerdan):\n" + digest_for(business)[:24000])
    dlg = recent_dialogue(business, n=16)
    if dlg:
        lines.append(
            "Oxirgi suhbat (chat va ovoz; foydalanuvchi shu mavzuni davom ettirishi mumkin, kontekstni yo'qotma):\n"
            + dlg[:4000]
        )
    return lines


def session_payload(business: Business) -> dict[str, Any]:
    base = get_forecast(business).result
    instruction = live_system_instruction(
        business_name=business.name,
        today_long=uz.format_date_long(base.today),
        context_lines=live_context(business),
    )
    specs = [t.declaration() for t in TOOLS.values() if t.voice]
    # demo hybrid (owner 2026-11-22): Live answers by itself (instant voice, its tools); the page
    # replaces the turn with the frozen card + recorded clip when the router says golden
    conf = live_config(
        system_instruction=instruction,
        tool_specs=specs,
        behavior="blocking",
        silence_ms=cfg.LIVE_SILENCE_DURATION_MS,
    )
    with timing.measure("llm"):
        tok = mint_token(conf)
    return {
        "ok": True,
        "token": tok.token,
        "model": tok.model,
        "expires_at": tok.expires_at.isoformat(),
        "new_session_expires_at": tok.new_session_expires_at.isoformat(),
        "behavior": "blocking",
        "demo": cfg.DEMO_GOLDEN_ONLY,
        "mint_ms": round(tok.mint_ms, 1),
        "business_name": business.name,
        "cash": {
            "label": "Hozirgi kassa",
            "display": uz.format_mln(base.close_on(base.today)) + " so'm",
        },
    }


class LiveSessionView(BusinessAPIView):
    """POST /api/live/session and GET /api/live/session/prefetch (hover on "Jonli gaplashish")."""

    requires_data = True  # 409 no_data until a source is synced

    def _mint(self) -> Response:
        if budget.over_limit():
            log.warning("AI budget reached: Live session refused")
            return Response(
                {"ok": False, "error": "budget", "message": cfg.BUDGET_MESSAGE_LIVE}, status=429
            )
        try:
            payload = session_payload(self.business)
            # a token is free; the session is billed by time -> reserve, /live/finish corrects
            u = budget.record(
                "live",
                cfg.AI_MODELS["live"],
                seconds=cfg.LIVE_RESERVE_S,
                business_id=self.business.pk,
            )
            payload["usage_id"] = u.pk
            return Response(payload)
        except GeminiNotConfigured:
            return Response({"ok": False, "error": "gemini_not_configured"}, status=503)
        except Exception as exc:
            log.warning("live token mint failed: %s", scrub(str(exc))[:200])
            return Response(
                {
                    "ok": False,
                    "error": "token_failed",
                    "message": "Jonli suhbatni ochib bo'lmadi. Yozib so'rang.",
                },
                status=502,
            )

    def post(self, request: Request) -> Response:
        return self._mint()

    def get(self, request: Request) -> Response:
        return self._mint()


def _summarize(business_id: int, conversation_id: int, text: str) -> None:
    """Background: short summary by the light model -> MemoryItem (embedding comes in M7)."""
    from google.genai import types

    try:
        r = budget.generate_sync(
            "light",
            model=cfg.AI_MODELS["light"],
            contents="Ushbu suhbatni 1-2 jumlada o'zbekcha xulosa qil (faqat nima so'raldi va nima kelishildi, "
            "raqamlarni qo'shma):\n" + text[:6000],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel("LOW"))
            ),
        )
        summary = (r.text or "").strip()[:500]
        if summary:
            with tenant_context(business_id):
                MemoryItem.objects.create(
                    business_id=business_id,
                    kind=MemoryItem.Kind.SUMMARY,
                    text=summary,
                    meta={"conversation_id": conversation_id, "channel": "voice"},
                )
    except Exception as exc:
        log.info("live summary skipped: %s", scrub(str(exc))[:160])
    finally:
        connections.close_all()


def _settle_live_usage(business_id: int, data: dict[str, Any]) -> None:
    """Replace the minted reservation with the real session length (capped at 5 min)."""
    try:
        seconds = max(1, min(int(data.get("seconds") or 0), cfg.LIVE_MAX_SESSION_S))
    except (TypeError, ValueError):
        return
    if not data.get("seconds"):
        return
    qs = AiUsage.objects.filter(business_id=business_id, kind="live", seconds=cfg.LIVE_RESERVE_S)
    uid = data.get("usage_id")
    u = (qs.filter(pk=uid).first() if isinstance(uid, int) else None) or qs.order_by(
        "-created_at"
    ).first()
    if u:
        u.seconds = seconds
        u.cost_usd = (cfg.AI_LIVE_USD_PER_MIN * seconds / 60).quantize(Decimal("0.000001"))
        u.save(update_fields=["seconds", "cost_usd"])


class LiveFinishView(BusinessAPIView):
    def post(self, request: Request) -> Response:
        data = request.data if isinstance(request.data, dict) else {}
        turns = [
            t
            for t in (data.get("transcript") or [])
            if isinstance(t, dict) and str(t.get("text", "")).strip()
        ][:200]
        blocks = data.get("blocks") if isinstance(data.get("blocks"), list) else []
        _settle_live_usage(self.business.pk, data)
        if not turns:
            return Response({"ok": True, "saved": 0})
        b = self.business
        conv = Conversation.objects.create(
            business=b,
            user_id=request.user.pk,
            channel="voice",
            title=str(turns[0].get("text", ""))[:60],
        )
        Message.objects.bulk_create(
            [
                Message(
                    business=b,
                    conversation=conv,
                    role="user" if t.get("who") == "user" else "assistant",
                    author_name="Siz" if t.get("who") == "user" else "AI CFO",
                    content=str(t.get("text", ""))[:2000],
                    ui_blocks=blocks if i == len(turns) - 1 else [],
                )
                for i, t in enumerate(turns)
            ]
        )
        text = "\n".join(
            f"{'Foydalanuvchi' if t.get('who') == 'user' else 'AI'}: {t.get('text')}" for t in turns
        )
        threading.Thread(target=_summarize, args=(b.pk, conv.pk, text), daemon=True).start()
        return Response(
            {
                "ok": True,
                "saved": len(turns),
                "conversation_id": conv.pk,
                "at": datetime.now().isoformat(),
            }
        )
