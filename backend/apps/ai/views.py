"""Chat (bootstrap, SSE messages, speech, transcription) and the shared tool endpoint."""

from __future__ import annotations

import io
import json
import logging
import time
import wave
from collections import OrderedDict
from typing import Any

from asgiref.sync import sync_to_async
from django.db.models import Count
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBase,
    JsonResponse,
    StreamingHttpResponse,
)
from django.views.decorators.http import require_POST
from google.genai import types
from rest_framework.request import Request
from rest_framework.response import Response

from apps.actions.audit import audit
from apps.insights.forecasting import get_forecast
from apps.integrations.models import DataSource
from apps.knowledge.models import BusinessRule, MemoryItem
from apps.telemetry import timing
from apps.tenancy.api import BusinessAPIView
from apps.tenancy.context import tenant_context
from apps.tenancy.gate import NO_DATA_BODY, data_status, review_body
from config import app_settings as cfg

from . import budget
from . import uz_format as uz
from .chat import CHIPS, Turn, stream_turn, warm_brief
from .gemini import scrub
from .models import Conversation, Message
from .tools import TOOLS, ToolArgError, ToolContext, run_tool

log = logging.getLogger(__name__)
CONFIDENCE = {"high": "Yuqori", "medium": "O'rtacha", "low": "Past"}


def basis_payload(business: Any) -> dict[str, Any]:
    base = get_forecast(business).result
    src = DataSource.objects.order_by("-last_synced_at").values("last_synced_at").first()
    rules = (
        BusinessRule.objects.filter(enabled=True)
        .order_by("created_at")
        .values_list("text_uz", flat=True)
    )
    seg = MemoryItem.objects.filter(business__isnull=True, kind="segment_insight").aggregate(
        n=Count("id")
    )["n"]
    items = []
    if src and src["last_synced_at"]:
        items.append(
            {
                "icon": "sheets",
                "title": "Sizning Google Sheets jadvallaringiz",
                "note": f"yangilangan: {uz.format_date(src['last_synced_at'].date())}",
            }
        )
    else:
        items.append(
            {
                "icon": "sheets",
                "title": "Sizning jadval ma'lumotlaringiz",
                "note": "jadval hali ulanmagan — demo ma'lumot",
            }
        )
    rule_list = list(rules)
    if rule_list:
        items.append(
            {
                "icon": "rules",
                "title": f"Siz o'rgatgan {len(rule_list)} ta qoida",
                "note": f"masalan: {rule_list[0][0].lower()}{rule_list[0][1:]}",
            }
        )
    if seg:
        items.append(
            {
                "icon": "segment",
                "title": f"{business.city}dagi shunga o'xshash bizneslar tajribasi",
                "note": "anonim, ularning ma'lumoti ko'rinmaydi",
            }
        )
    level = base.confidence or "low"
    note = (
        "Ishonchli prognoz uchun kamida 2 haftalik ma'lumot kerak."
        if base.insufficient_data
        else "Majburiy to'lov sanalari aniq ma'lum."
        if level == "high"
        else "Savdo kunlar bo'yicha ancha o'zgarib turadi."
        if level == "medium"
        else "Tarix qisqa yoki savdo juda notekis."
    )
    return {
        "items": items,
        "confidence": {"label": CONFIDENCE[level], "level": level, "note": note},
    }


def message_payload(m: Message) -> dict[str, Any]:
    is_ai = m.role == "assistant"
    voice = (m.answer or {}).get("voice") if not is_ai else None
    return {
        "id": m.pk,
        "role": m.role,
        "author": "AI CFO" if is_ai else (m.author_name or "Siz"),
        "time": m.created_at.astimezone().strftime("%H:%M"),
        "text": m.content,
        "voice": voice,
        "answer": m.answer if is_ai and m.answer and "headline" in m.answer else None,
    }


class ChatBootstrapView(BusinessAPIView):
    requires_data = True  # 409 no_data until a source is synced

    def get(self, request: Request) -> Response:
        b = self.business
        conv = (
            Conversation.objects.filter(user_id=request.user.pk, channel="chat")
            .order_by("-created_at")
            .first()
        )
        if conv is None:
            conv = Conversation.objects.create(
                business=b, user_id=request.user.pk, channel="chat", title="Chat"
            )
        msgs = list(Message.objects.filter(conversation=conv).order_by("-created_at")[:40])[::-1]
        from asgiref.sync import async_to_sync

        brief = async_to_sync(warm_brief)(b)
        return Response(
            {
                "conversation_id": conv.pk,
                "business_name": b.name,
                "brief": {"time": "08:00", **brief},
                "messages": [message_payload(m) for m in msgs],
                "chips": [{"id": k, "label": v[0]} for k, v in CHIPS.items()],
                "basis": basis_payload(b),
            }
        )


async def chat_messages(request: HttpRequest) -> HttpResponseBase:
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    user = await request.auser()
    business = getattr(request, "business", None)
    if not user.is_authenticated or business is None:
        return JsonResponse({"error": "auth_required"}, status=401)
    st = await sync_to_async(data_status)(business)
    if st == "no_data":
        return JsonResponse(NO_DATA_BODY, status=409)  # no data, no answer
    if st == "needs_review":  # does not reconcile with the file's own totals: no advice
        return JsonResponse(await sync_to_async(review_body)(business), status=409)
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"error": "bad_json"}, status=400)
    chip = body.get("chip")
    text = str(body.get("text") or "").strip()[:1000]
    if chip:
        if chip not in CHIPS:
            return JsonResponse({"error": "unknown_chip"}, status=400)
        text = CHIPS[chip][0]
    if not text:
        return JsonResponse({"error": "empty", "message": "Savol yozing."}, status=400)
    conv_id = body.get("conversation_id")

    def _conv() -> Conversation:
        with tenant_context(business):
            conv: Conversation | None = (
                Conversation.objects.filter(pk=conv_id, user_id=user.pk).first()
                if conv_id
                else None
            )
            return conv or Conversation.objects.create(
                business=business, user_id=user.pk, channel="chat", title=text[:60]
            )

    conv = await sync_to_async(_conv)()
    voice = body.get("voice") if isinstance(body.get("voice"), dict) else None
    turn = Turn(
        business=business,
        user_id=user.pk,
        author=user.first_name or "Siz",
        conversation=conv,
        text=text,
        chip=chip,
        voice=voice,
    )
    resp = StreamingHttpResponse(stream_turn(turn), content_type="text/event-stream; charset=utf-8")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp


_speech_cache: OrderedDict[int, bytes] = OrderedDict()


def _pcm_to_wav(pcm: bytes, rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def tts_wav(text: str) -> bytes:
    r = budget.generate_sync(
        "tts",
        model=cfg.TTS_MODEL,
        contents=f"O'zbek tilida, sokin va aniq o'qing: {text}",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=cfg.TTS_VOICE)
                )
            ),
        ),
    )
    pcm = b"".join(
        p.inline_data.data
        for c in (r.candidates or [])
        for p in ((c.content.parts if c.content else None) or [])
        if p.inline_data and p.inline_data.data
    )
    if not pcm:
        raise RuntimeError("no audio")
    return _pcm_to_wav(pcm)


class ChatSpeechView(BusinessAPIView):
    requires_data = True  # 409 no_data until a source is synced

    def get(self, request: Request, message_id: int) -> HttpResponse:
        if message_id in _speech_cache:
            return HttpResponse(_speech_cache[message_id], content_type="audio/wav")
        m = Message.objects.filter(pk=message_id, role="assistant").first()
        if m is None or not m.answer:
            return JsonResponse({"error": "not_found"}, status=404)
        text = m.answer.get("speech") or m.content
        try:
            with timing.measure("llm"):
                wav = tts_wav(text)
        except Exception as exc:
            log.warning("tts failed: %s", scrub(str(exc))[:200])
            return JsonResponse(
                {"error": "tts_failed", "message": "Ovozni hozir tayyorlab bo'lmadi."}, status=502
            )
        _speech_cache[message_id] = wav
        while len(_speech_cache) > 50:
            _speech_cache.popitem(last=False)
        return HttpResponse(wav, content_type="audio/wav")


@require_POST
def transcribe(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated or getattr(request, "business", None) is None:
        return JsonResponse({"error": "auth_required"}, status=401)
    if data_status(request.business) == "no_data":  # type: ignore[attr-defined]
        return JsonResponse(NO_DATA_BODY, status=409)
    audio = request.body
    if not audio or len(audio) > 3_000_000:
        return JsonResponse(
            {"error": "bad_audio", "message": "Ovoz juda uzun yoki bo'sh."}, status=400
        )
    mime = (request.content_type or "audio/webm").split(";")[0]
    try:
        r = budget.generate_sync(
            "stt",
            model=cfg.AI_MODELS["light"],
            contents=[
                types.Part.from_bytes(data=audio, mime_type=mime),
                "Bu audioni o'zbek tilida (lotin yozuvida) so'zma-so'z yozib ber. Faqat matnni qaytar.",
            ],
            config=types.GenerateContentConfig(max_output_tokens=300),
        )
        text = (r.text or "").strip()
    except Exception as exc:
        log.warning("transcribe failed: %s", scrub(str(exc))[:200])
        return JsonResponse(
            {"error": "transcribe_failed", "message": "Ovozni tushunib bo'lmadi. Yozib so'rang."},
            status=502,
        )
    try:
        secs = max(0, round(float(request.headers.get("X-Audio-Duration", "0"))))
    except ValueError:
        secs = 0
    return JsonResponse({"text": text, "duration": f"{secs // 60}:{secs % 60:02d}"})


class ToolView(BusinessAPIView):
    """POST /api/tools/<name> (Live): args validated by schema; no LLM, no network."""

    requires_data = True  # 409 no_data until a source is synced

    def post(self, request: Request, name: str) -> Response:
        if name not in TOOLS:
            return Response({"ok": False, "error": "unknown_tool"}, status=404)
        data = request.data if isinstance(request.data, dict) else {}
        utterance = str(data.pop("_user_utterance", ""))[:300]
        channel = "voice" if data.pop("_channel", "voice") == "voice" else "api"
        ctx = ToolContext(self.business, request.user.pk, channel, last_user_text=utterance)
        t0 = time.perf_counter()
        try:
            with timing.measure("engine"):
                result = run_tool(ctx, name, data)
        except ToolArgError as exc:
            return Response({"ok": False, "error": "bad_args", "detail": str(exc)}, status=400)
        audit(
            f"{channel}:user:{request.user.pk}",
            "tool_call",
            tool=name,
            args=data,
            result=result.get("facts"),
        )
        if channel == "voice" and result.get("md"):
            # voice needs the lead sentence, not the tables (shorter Live turn = faster reply)
            result = {**result, "md": str(result["md"]).split("\n\n", 1)[0]}
        resp = Response(result)
        resp["X-Tool-Ms"] = f"{(time.perf_counter() - t0) * 1000:.1f}"
        return resp
