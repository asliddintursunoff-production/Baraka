"""Chat (bootstrap, SSE messages, speech, transcription) and the shared tool endpoint."""

from __future__ import annotations

import io
import json
import logging
import re
import time
import wave
from collections import OrderedDict
from datetime import datetime
from typing import Any, cast

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
from apps.tenancy.gate import NO_DATA_BODY, data_status
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


def _msg_time(dt: Any) -> str:
    """Business-local (Asia/Tashkent) time; the date too when it is not today."""
    from zoneinfo import ZoneInfo

    local = dt.astimezone(ZoneInfo("Asia/Tashkent"))
    today = datetime.now(ZoneInfo("Asia/Tashkent")).date()
    return (
        local.strftime("%H:%M")
        if local.date() == today
        else f"{uz.format_date(local.date())}, {local.strftime('%H:%M')}"
    )


GREETING = re.compile(
    r"^\W*(salom|assalomu?\s*alaykum|assalom|qalaysiz|qanaysan|qalaysan|yaxshimisiz|hello|hi|privet|rahmat|ok|xop|xo'p)\W*$",
    re.I,
)


def is_greeting(text: str) -> bool:
    """Greeting-only messages never title (or list) a chat."""
    return bool(GREETING.match((text or "").strip()))


class ConversationView(BusinessAPIView):
    """PATCH {title} renames, DELETE removes one of the user's chats."""

    def patch(self, request: Request, conv_id: int) -> Response:
        conv = Conversation.objects.filter(user_id=request.user.pk, pk=conv_id).first()
        if conv is None:
            return Response({"error": "not_found"}, status=404)
        title = str(
            (request.data if isinstance(request.data, dict) else {}).get("title") or ""
        ).strip()[:60]
        if title:
            conv.title = title
            conv.save(update_fields=["title"])
        return Response({"id": conv.pk, "title": conv.title})

    def delete(self, request: Request, conv_id: int) -> Response:
        Conversation.objects.filter(user_id=request.user.pk, pk=conv_id).delete()
        return Response(status=204)


def message_payload(m: Message) -> dict[str, Any]:
    is_ai = m.role == "assistant"
    voice = (m.answer or {}).get("voice") if not is_ai else None
    return {
        "id": m.pk,
        "role": m.role,
        "author": "AI CFO" if is_ai else (m.author_name or "Siz"),
        "time": _msg_time(m.created_at),
        "text": m.content,
        "voice": voice,
        "answer": m.answer if is_ai and m.answer and "headline" in m.answer else None,
    }


def demo_questions() -> list[dict[str, str]]:
    """DEMO_GOLDEN_ONLY: the 4 golden question cards for the empty chat."""
    if not cfg.DEMO_GOLDEN_ONLY:
        return []
    from .demo import question_cards

    return question_cards()


_DEMO_TTS: dict[str, str] = {}  # speech_key -> text (dynamic answers: param variants)
_DEMO_WAV: OrderedDict[str, bytes] = OrderedDict()


async def _demo_auth(request: HttpRequest) -> tuple[Any, Any] | JsonResponse:
    user = await request.auser()
    business = getattr(request, "business", None)
    if not user.is_authenticated or business is None:
        return JsonResponse({"error": "auth_required"}, status=401)
    return user, business


async def demo_answer(request: HttpRequest) -> HttpResponseBase:
    """POST {text, prev} -> the demo router's answer (Live: card + clip).

    Async (like chat_messages): a slow free answer or TTS must never queue the next question
    behind it on the worker's single sync thread (owner 2026-11-22: "kutib qolayabdi").
    """
    from .demo import answer

    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    auth = await _demo_auth(request)
    if isinstance(auth, JsonResponse):
        return auth
    user, business = auth
    if await sync_to_async(data_status, thread_sensitive=False)(business) == "no_data":
        return JsonResponse(NO_DATA_BODY, status=409)
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"error": "bad_json"}, status=400)
    body = body if isinstance(body, dict) else {}
    text = str(body.get("text") or "").strip()[:500]
    prev = body.get("prev") if isinstance(body.get("prev"), str) else None

    def route() -> dict[str, Any]:
        with tenant_context(business):
            ctx = ToolContext(business, user.pk, "voice", last_user_text=text)
            d = answer(ctx, text, prev)
            d.pop("result", None)
            return d

    d = await sync_to_async(route, thread_sensitive=False)()
    if d["kind"] == "other":
        d = await _demo_free(business, user, text) or d
    if d["say"] and not d["clip"]:
        _DEMO_TTS[d["speech_key"]] = d["say"]
    return JsonResponse(d)


async def _demo_free(business: Any, user: Any, text: str) -> dict[str, Any] | None:
    """Outside Q1–Q4: the normal AI pipeline (tools + engine numbers), spoken via /demo/tts."""
    from .chat import collect_answer
    from .demo import _out

    def conv() -> Conversation:
        with tenant_context(business):
            c = (
                Conversation.objects.filter(user_id=user.pk, channel="voice", title="Live (demo)")
                .order_by("-created_at")
                .first()
            )
            if c is None:
                c = Conversation.objects.create(
                    business=business, user_id=user.pk, channel="voice", title="Live (demo)"
                )
            return cast(Conversation, c)

    turn = Turn(
        business=business,
        user_id=int(user.pk or 0),
        author=getattr(user, "first_name", "") or "Owner",
        conversation=await sync_to_async(conv, thread_sensitive=False)(),
        text=text,
        voice={"live": True},
    )
    try:
        f = await collect_answer(turn)
    except Exception as exc:
        log.warning("demo free answer failed: %s", scrub(str(exc))[:200])
        return None
    if not f:
        return None
    md = str(f.get("markdown") or f.get("headline") or "")
    # spoken = the screen headline (the pipeline's speech template may describe another tool)
    head = next((ln for ln in md.splitlines() if ln.strip()), "")
    say = re.sub(r"[*#`_|>]", "", head).strip() or str(f.get("speech") or "").strip()
    d = _out("free", markdown=md, blocks=list(f.get("blocks") or []), say=say)
    d.pop("result", None)
    return d


async def demo_tts(request: HttpRequest, key: str) -> HttpResponseBase:
    """GET a dynamic answer's speech (TTS once, then cached) — pre-recorded clips are static files."""
    from .demo import speakable

    auth = await _demo_auth(request)
    if isinstance(auth, JsonResponse):
        return auth
    if key in _DEMO_WAV:
        return HttpResponse(_DEMO_WAV[key], content_type="audio/wav")
    text = _DEMO_TTS.get(key)
    if not text:
        return JsonResponse({"error": "not_found"}, status=404)
    try:
        wav = await sync_to_async(tts_wav, thread_sensitive=False)(speakable(text))
    except Exception as exc:
        log.warning("demo tts failed: %s", scrub(str(exc))[:200])
        return JsonResponse({"error": "tts_failed"}, status=502)
    _DEMO_WAV[key] = wav
    while len(_DEMO_WAV) > 50:
        _DEMO_WAV.popitem(last=False)
    return HttpResponse(wav, content_type="audio/wav")


class ChatBootstrapView(BusinessAPIView):
    requires_data = True  # 409 no_data until a source is synced

    def get(self, request: Request) -> Response:
        b = self.business
        cid = request.query_params.get("conversation_id")
        conv = None
        if request.query_params.get("new"):
            conv = Conversation.objects.create(
                business=b, user_id=request.user.pk, channel="chat", title="Yangi chat"
            )
        elif cid and str(cid).isdigit():
            conv = Conversation.objects.filter(user_id=request.user.pk, pk=int(cid)).first()
        if conv is None:
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
                "conversations": [
                    {
                        "id": c.pk,
                        "title": (c.title or "Chat")[:60],
                        "channel": c.channel,
                        "date": c.created_at.date().isoformat(),
                    }
                    for c in Conversation.objects.filter(user_id=request.user.pk)
                    .annotate(n=Count("message"))
                    .filter(n__gt=0)
                    .exclude(title__in=("Yangi chat", "Chat", ""))
                    .order_by("-created_at")[:60]
                    if not is_greeting(c.title or "")
                ][:40],
                "business_name": b.name,
                "brief": {"time": "08:00", **brief},
                "messages": [message_payload(m) for m in msgs],
                "chips": [{"id": k, "label": v[0]} for k, v in CHIPS.items()],
                "questions": demo_questions(),
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
    # full-context mode: data-quality issues are a badge, never a refusal in chat
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
            if (
                conv is not None
                and conv.title in ("Yangi chat", "Chat", "")
                and not is_greeting(text)
            ):
                conv.title = text[:60]
                conv.save(update_fields=["title"])
            return conv or Conversation.objects.create(
                business=business,
                user_id=user.pk,
                channel="chat",
                title="Yangi chat" if is_greeting(text) else text[:60],
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


def trim_tail(pcm: bytes, rate: int = 24000) -> bytes:
    """Cut the TTS end-of-stream burst: speech -> silence -> a loud ~0.2 s click/hiss at the end."""
    import numpy as np

    x = np.frombuffer(pcm[: len(pcm) // 2 * 2], dtype=np.int16)
    win = rate // 50  # 20 ms
    n = len(x) // win
    if n < 10:
        return pcm
    rms = np.sqrt(np.mean(x[: n * win].reshape(n, win).astype(np.float64) ** 2, axis=1))
    quiet = rms < 300
    cut = None
    # the last run of >=3 quiet windows within the final 0.6 s, followed only by the burst
    for i in range(n - 1, max(n - 30, 2), -1):
        if quiet[i] and quiet[i - 1] and quiet[i - 2]:
            cut = i + 1
            break
    if cut is None or cut >= n:
        y = x.copy()
    else:
        y = x[: cut * win].copy()
    fade = min(len(y), rate // 33)  # 30 ms fade-out
    if fade:
        y[-fade:] = (y[-fade:].astype(np.float64) * np.linspace(1, 0, fade)).astype(np.int16)
    return y.tobytes()


def _pcm_to_wav(pcm: bytes, rate: int = 24000) -> bytes:
    pcm = trim_tail(pcm, rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def tts_wav(text: str) -> bytes:
    """TTS with a fallback chain: each TTS model has its own (small) daily quota."""
    err: Exception | None = None
    for model in cfg.TTS_MODEL_CHAIN:
        try:
            return _tts_once(text, model)
        except Exception as exc:
            err = exc
            log.info("tts %s failed: %s", model, scrub(str(exc))[:120])
    raise RuntimeError("tts failed") from err


def _tts_once(text: str, model: str) -> bytes:
    r = budget.generate_sync(
        "tts",
        model=model,
        # the bare text only: any instruction in `contents` is read aloud by the TTS model
        contents=text,
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
            config=types.GenerateContentConfig(
                max_output_tokens=600,
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel("LOW")),
            ),
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
