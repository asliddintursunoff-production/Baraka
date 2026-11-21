"""Chat orchestrator (spec §5.5) as an async event stream.

1. Parallel: memory retrieval (skipped when nothing is embedded) + cash status from cache.
2. Chips: tool + template answer, no LLM (fast path).
3. Purchase-looking text: evaluate_purchase runs immediately (speculative) -> `blocks`
   within ~200 ms. If the LLM calls the same tool with the same args, the cached result
   is reused; different args -> the LLM's result wins and the cards are replaced.
4. LLM via the fallback chain, <= 3 tool rounds, final structured answer (JSON schema).
5. Number guard; one retry; then the engine-made template answer.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone
from google.genai import errors as genai_errors
from google.genai import types

from apps.actions.audit import audit
from apps.insights import advice
from apps.knowledge.models import BusinessRule
from apps.telemetry.models import LatencyEvent
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Business

from . import uz_format as uz
from .guard import violations
from .llm import AllModelsFailed, generate
from .models import Conversation, Message
from .tools import TOOLS, ToolArgError, ToolContext, for_model, run_tool
from .uz_parse import looks_like_purchase, parse_amounts

log = logging.getLogger(__name__)

CHIPS: dict[str, tuple[str, str, dict[str, Any]]] = {
    "cash": ("Hozir qancha pulim bor?", "get_cash_status", {}),
    "revenue_drop": (
        "Savdo kamaysa nima bo'ladi?",
        "simulate_change",
        {"kind": "revenue_pct", "value": -20},
    ),
    "staff": (
        "Yana 2 ta xodim olsam bo'ladimi?",
        "simulate_change",
        {"kind": "new_staff", "value": 2},
    ),
}
CONTROL_TOOLS = {"remember_fact", "set_staff_count", "propose_plan", "confirm_plan"}
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["yes", "no", "risky", "info"]},
        "headline": {"type": "string", "description": "<= 60 belgi, avval qaror"},
        "reason": {"type": "string", "description": "bitta jumla"},
        "steps": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        "chips": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        "show_blocks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict", "headline", "reason", "steps"],
}
SYSTEM = """Sen {app} — "{biz}" biznesining shaxsiy AI moliyaviy direktorisan (AI CFO). Bugun: {today}.
Qoidalar:
1. Faqat o'zbek tilida (lotin) yoz.
2. Raqam, summa va sanani FAQAT tool natijasidan yoki pastdagi kontekstdan ol, o'zing hisoblama. Summalarni tool'dagi "display" ko'rinishida yoz (masalan "6,2 mln").
3. Pul haqidagi savolda avval tegishli tool'ni chaqir: xarid yoki katta xarajat -> evaluate_purchase; "agar..." -> simulate_change; aniq kun -> explain_day; to'lovlar -> get_upcoming_payments; kassa -> get_cash_status; prognoz -> get_forecast; foydalanuvchi biznes qoidasini yoki tuzatishni aytsa -> remember_fact; xodimlar sonini aytsa -> set_staff_count.
4. Yakuniy javob JSON: verdict, headline (60 belgigacha, avval qaror), reason (bitta oddiy jumla, sabab), steps (ko'pi bilan 3 ta qisqa qadam), chips (ko'pi bilan 3 ta keyingi savol).
5. Oddiy so'zlar: kassa, majburiy to'lov, oylik, kredit, ta'minotchi, xavfsiz chegara. "stsenariy", "zaxira", "deterministik" so'zlarini ishlatma.
6. Ma'lumot bo'lmasa: "Bu ma'lumot jadvalingizda yo'q". O'ylab topma.
7. Reja yoki eslatmani faqat taklif qil; tasdiqlashni foydalanuvchi tugma bilan qiladi. remember_fact faqat taklif yaratadi: foydalanuvchi tasdiqlamaguncha qoida prognozga qo'shilmaydi.
Kontekst:
{context}"""


T = TypeVar("T")


async def db[T](business: Business, fn: Callable[[], T]) -> T:
    """Run ORM work in a thread with the tenant context set inside that thread
    (never held across an async generator's yields)."""

    def _run() -> T:
        with tenant_context(business):
            return fn()

    return await sync_to_async(_run)()


def sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n".encode()


@dataclass
class Turn:
    business: Business
    user_id: int
    author: str
    conversation: Conversation
    text: str
    chip: str | None = None
    voice: dict[str, Any] | None = None
    t0: float = field(default_factory=time.perf_counter)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)  # name -> last result
    blocks_sent_ms: float | None = None

    def ms(self) -> float:
        return (time.perf_counter() - self.t0) * 1000


def context_lines(ctx: ToolContext) -> list[str]:
    base = ctx.base
    if base.insufficient_data:
        return ["Ma'lumot kam: ishonchli prognoz uchun kamida 2 haftalik tarix kerak."]
    cash = base.close_on(base.today)
    lines = [
        f"Hozirgi kassa: {uz.format_mln(cash)}.",
        f"Eng qiyin kun (90 kun): {uz.format_date(base.min_date)}, {uz.format_mln(base.min_balance)} qoladi.",
        f"Xavfsiz chegara: {uz.format_mln(base.safe_min)}.",
        "Yaqin majburiy to'lovlar: "
        + "; ".join(
            f"{uz.format_date(p.date)} {p.title} {uz.format_mln(p.amount)}"
            for p in [o for o in base.obligations if o.date > base.today][:5]
        ),
    ]
    rules = list(
        BusinessRule.objects.filter(enabled=True)
        .order_by("-created_at")
        .values_list("text_uz", flat=True)[:10]
    )
    if rules:
        lines.append("Tasdiqlangan qoidalar: " + "; ".join(rules))
    if ctx.business.staff_count:
        lines.append(f"Xodimlar soni: {ctx.business.staff_count}.")
    return lines


def template_answer(result: dict[str, Any]) -> dict[str, Any]:
    a = dict(result.get("answer") or {})
    a.setdefault("verdict", result.get("verdict") or "info")
    a.setdefault("steps", [])
    return a


def _texts_of(result: dict[str, Any]) -> list[str]:
    return [
        json.dumps(for_model(result), ensure_ascii=False, default=str),
        json.dumps(result.get("answer") or {}, ensure_ascii=False),
    ]


def finalize(turn: Turn, answer: dict[str, Any], model: str) -> dict[str, Any]:
    """Merge the chosen answer with engine-made parts (blocks, plan, candidate, explain)."""
    primary = next(reversed(turn.results.values()), None) if turn.results else None
    blocks = list(primary.get("ui_blocks", [])) if primary else []
    wanted = answer.get("show_blocks")
    if wanted:
        chosen = [b for b in blocks if b.get("id") in wanted]
        blocks = chosen or blocks
    tmpl = (primary or {}).get("answer") or {}
    last_tool = turn.tool_calls[-1]["name"] if turn.tool_calls else ""
    if last_tool in CONTROL_TOOLS and tmpl:
        # State-changing tools: the exact engine/template wording, never an LLM paraphrase
        # (e.g. a rule is NOT applied until the person confirms it).
        answer = {**tmpl, "chips": answer.get("chips") or tmpl.get("chips", [])}
    out = {
        "verdict": answer.get("verdict") or tmpl.get("verdict") or "info",
        "headline": (answer.get("headline") or tmpl.get("headline") or "")[:80],
        "reason": answer.get("reason") or tmpl.get("reason") or "",
        "steps": list(answer.get("steps") or tmpl.get("steps") or [])[:3],
        "blocks": blocks,
        "chips": list(answer.get("chips") or tmpl.get("chips") or [])[:3],
        "plan": (primary or {}).get("proposed_plan"),
        "candidate": (primary or {}).get("candidate"),
        "explain": tmpl.get("explain", []),
        "speech": (primary or {}).get("say")
        or " ".join([answer.get("headline", ""), answer.get("reason", "")]).replace("**", ""),
        "model": model,
    }
    return out


async def run_tool_async(
    turn: Turn, ctx: ToolContext, name: str, args: dict[str, Any], *, source: str
) -> dict[str, Any]:
    t = time.perf_counter()

    def _run() -> dict[str, Any]:
        with tenant_context(turn.business):
            result = run_tool(ctx, name, args)
            audit(
                "ai",
                "tool_call",
                tool=name,
                args={**args, "source": source},
                result=for_model(result),
            )
            return result

    result = await sync_to_async(_run)()
    turn.tool_calls.append(
        {
            "name": name,
            "args": args,
            "ms": round((time.perf_counter() - t) * 1000, 1),
            "source": source,
        }
    )
    turn.results[name] = result
    return result


def _args_key(name: str, args: dict[str, Any]) -> str:
    return name + json.dumps(
        {k: (int(v) if isinstance(v, float) and v.is_integer() else v) for k, v in args.items()},
        sort_keys=True,
        default=str,
    )


def _extract_json(text: str) -> dict[str, Any] | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


async def stream_turn(turn: Turn) -> AsyncIterator[bytes]:
    b = turn.business
    user_msg = await db(
        b,
        lambda: Message.objects.create(
            business=b,
            conversation=turn.conversation,
            role="user",
            author_name=turn.author,
            content=turn.text,
            answer={"voice": turn.voice} if turn.voice else None,
        ),
    )
    yield sse("meta", {"conversation_id": turn.conversation.pk, "user_message_id": user_msg.pk})
    yield sse("status", {"text": "Hisoblayapman…"})
    ctx = ToolContext(b, turn.user_id, "chat", last_user_text=turn.text)
    final: dict[str, Any] | None = None
    try:
        # 1. context (cache) — embeddings are skipped until memory is embedded (M7)
        lines = await db(b, lambda: context_lines(ctx))

        # 2. chip fast path
        if turn.chip:
            _, tool, args = CHIPS[turn.chip]
            result = await run_tool_async(turn, ctx, tool, args, source="chip")
            turn.blocks_sent_ms = turn.ms()
            yield sse("blocks", {"blocks": result.get("ui_blocks", []), "replace": True})
            final = finalize(turn, template_answer(result), "template")
        else:
            speculative: dict[str, dict[str, Any]] = {}
            if looks_like_purchase(turn.text):
                amounts = parse_amounts(turn.text)
                spec_args: dict[str, Any] = {"amount": int(amounts[0])}
                try:
                    result = await run_tool_async(
                        turn, ctx, "evaluate_purchase", spec_args, source="speculative"
                    )
                    speculative[_args_key("evaluate_purchase", spec_args)] = result
                    turn.blocks_sent_ms = turn.ms()
                    yield sse(
                        "blocks",
                        {
                            "blocks": result.get("ui_blocks", []),
                            "replace": True,
                            "speculative": True,
                        },
                    )
                except ToolArgError:
                    pass
            final, _model = None, "template"
            try:
                async for item in llm_loop(turn, ctx, lines, speculative):
                    if isinstance(item, bytes):
                        yield item
                    else:
                        final, _model = item
            except (genai_errors.APIError, ValueError) as exc:  # never break the stream
                log.warning("llm loop failed, using template: %s", str(exc)[:200])
            if final is None:
                primary = next(reversed(turn.results.values()), None)
                if primary is None:
                    raise AllModelsFailed("no answer and no tool result")
                final = finalize(turn, template_answer(primary), "template")
    except AllModelsFailed:
        yield sse(
            "error",
            {
                "message": "AI hozir band. Bir daqiqadan keyin qayta so'rang yoki pastdagi tayyor savollardan foydalaning."
            },
        )
        return
    except ToolArgError as exc:
        log.info("tool arg error: %s", exc)
        yield sse("error", {"message": "Savolni tushunmadim. Summa yoki sanani aniqroq yozing."})
        return
    yield sse("answer", final)
    latency = turn.ms()
    msg = await db(
        b,
        lambda: Message.objects.create(
            business=b,
            conversation=turn.conversation,
            role="assistant",
            author_name="AI CFO",
            content=final["headline"],
            answer=final,
            ui_blocks=final["blocks"],
            tool_calls=turn.tool_calls,
            model=final["model"],
            latency_ms=round(latency),
        ),
    )
    events = [
        LatencyEvent(
            business=b,
            channel="chat",
            name="send_to_answer",
            ms=latency,
            model=final["model"],
            meta={"chip": turn.chip or "", "tools": [t["name"] for t in turn.tool_calls]},
        )
    ]
    if turn.blocks_sent_ms is not None:
        events.append(
            LatencyEvent(
                business=b,
                channel="chat",
                name="send_to_blocks",
                ms=turn.blocks_sent_ms,
                model=final["model"],
                meta={},
            )
        )
    await db(b, lambda: LatencyEvent.objects.bulk_create(events))
    yield sse("done", {"message_id": msg.pk, "latency_ms": round(latency), "model": final["model"]})


async def llm_loop(
    turn: Turn, ctx: ToolContext, lines: list[str], speculative: dict[str, dict[str, Any]]
) -> AsyncIterator[bytes | tuple[dict[str, Any], str]]:
    system = SYSTEM.format(
        app=settings.APP_NAME,
        biz=turn.business.name,
        today=uz.format_date_long(ctx.base.today),
        context="\n".join(lines),
    )
    history = await db(
        turn.business,
        lambda: list(
            Message.objects.filter(conversation=turn.conversation)
            .order_by("-created_at")
            .values("role", "content")[1:7]
        ),
    )
    contents: list[types.Content] = [
        types.Content(
            role="user" if h["role"] == "user" else "model",
            parts=[types.Part(text=h["content"] or "…")],
        )
        for h in reversed(history)
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=turn.text)]))
    decls = [
        types.FunctionDeclaration(
            name=t.name, description=t.description, parameters_json_schema=t.parameters
        )
        for t in TOOLS.values()
    ]
    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=[types.Tool(function_declarations=decls)],
        response_mime_type="application/json",
        response_json_schema=ANSWER_SCHEMA,
        max_output_tokens=800,
    )
    model = "template"
    for _round in range(3):
        try:
            res = await generate(contents, config)
        except genai_errors.ClientError as exc:
            if config.response_json_schema is not None:  # model can't mix tools + schema
                log.info("retrying without schema: %s", str(exc)[:120])
                config = config.model_copy(
                    update={"response_json_schema": None, "response_mime_type": None}
                )
                continue
            raise
        except AllModelsFailed:
            return
        model = res.model
        cand = res.response.candidates[0] if res.response.candidates else None
        parts = (cand.content.parts if cand and cand.content else None) or []
        calls = [p.function_call for p in parts if p.function_call]
        if not calls:
            answer = _extract_json(res.response.text or "")
            if answer is None:
                return
            checked = await check_answer(turn, answer, lines)
            if checked is None:  # one retry with the violations pointed out
                contents.append(
                    types.Content(
                        role="model",
                        parts=[types.Part(text=json.dumps(answer, ensure_ascii=False))],
                    )
                )
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                text="Javobdagi ba'zi raqamlar tool natijasida yo'q. Faqat tool natijasidagi raqamlar bilan qayta yoz."
                            )
                        ],
                    )
                )
                try:
                    res2 = await generate(contents, config)
                    answer2 = _extract_json(res2.response.text or "")
                    checked = await check_answer(turn, answer2, lines) if answer2 else None
                    model = res2.model
                except (AllModelsFailed, genai_errors.APIError):
                    checked = None
            if checked is None:
                return  # template answer is used by the caller
            yield (finalize(turn, checked, model), model)
            return
        contents.append(cand.content)  # type: ignore[union-attr, arg-type]
        responses: list[types.Part] = []
        for call in calls:
            name = call.name or ""
            args = dict(call.args or {})
            key = _args_key(name, args)
            try:
                if key in speculative:
                    result = speculative[key]
                    turn.results[name] = result
                    turn.tool_calls.append(
                        {"name": name, "args": args, "ms": 0, "source": "speculative_hit"}
                    )
                else:
                    result = await run_tool_async(turn, ctx, name, args, source="llm")
                    if result.get("ui_blocks"):
                        if turn.blocks_sent_ms is None:
                            turn.blocks_sent_ms = turn.ms()
                        yield sse("blocks", {"blocks": result["ui_blocks"], "replace": True})
                payload = for_model(result)
            except ToolArgError as exc:
                payload = {"ok": False, "error": str(exc)}
            responses.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        id=call.id, name=name, response=payload
                    )
                )
            )
        contents.append(types.Content(role="user", parts=responses))
    return


async def check_answer(
    turn: Turn, answer: dict[str, Any], lines: list[str]
) -> dict[str, Any] | None:
    texts = [
        str(answer.get("headline", "")),
        str(answer.get("reason", "")),
        *[str(s) for s in answer.get("steps", [])],
    ]
    allowed = [turn.text, *lines]
    for r in turn.results.values():
        allowed += _texts_of(r)
    bad = violations(texts, allowed)
    if bad:
        log.info("number guard rejected: %s", bad[:5])
        return None
    return answer


async def warm_brief(business: Business) -> dict[str, str]:
    """The proactive 'AI CFO · 08:00' message (same data as the dashboard banner)."""
    from apps.insights.forecasting import get_forecast

    def _b() -> dict[str, str]:
        base = get_forecast(business).result  # get_forecast sets its own tenant context
        bn = advice.banner(base)
        if base.verdict == "yes":
            pays = advice.payments_on(base, base.min_date)
            words = advice.join_uz([advice.payment_word(p) for p in pays])
            return {
                "lead": "Xayrli tong! Bugun hammasi joyida. Faqat bitta narsa:",
                "strong": f"{uz.format_date(base.min_date)} qiyin kun bo'ladi",
                "rest": f"— {words} bir kunga tushgan. Ungacha katta xarid qilmang."
                if len(pays) > 1
                else "— ungacha katta xarid qilmang.",
            }
        return {"lead": "Xayrli tong!", "strong": bn["headline"], "rest": bn["instruction"]}

    return await sync_to_async(_b)()


def now_hhmm(business: Business) -> str:
    from zoneinfo import ZoneInfo

    return timezone.localtime(timezone.now(), ZoneInfo(business.timezone)).strftime("%H:%M")


__all__ = ["CHIPS", "Turn", "asyncio", "stream_turn", "warm_brief"]
