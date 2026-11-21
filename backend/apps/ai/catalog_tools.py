"""Tier-2 catalogue tools: one dispatcher tool `catalog(intent, ...)` + the bad-intent reply.
Each implemented intent is a deterministic compute function returning a catalogue ReportCard."""

from __future__ import annotations

from typing import Any

from .catalog import IMPLEMENTED, registry
from .tools import TOOLS, Tool, ToolContext, envelope


def bad_intent_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    md = (
        "**Mening vazifam — biznesingizga foyda keltirish.** Xohlasangiz, biznesingizni nima xavf ostiga qo'yishini "
        "(risk xaritasi) ko'rsataman yoki biznesni to'g'ri yopish/sotish va zararni kamaytirish rejasini tuzaman.\n\n"
        "CHIPS: Biznesimni nima qulatishi mumkin? | Biznesni qanday to'g'ri sotaman? | Zararni qanday kamaytiraman?"
    )
    return envelope(
        ok=True,
        facts={},
        md=md,
        say="Mening vazifam — biznesingizga foyda keltirish. Xohlasangiz, xavflar xaritasini ko'rsataman.",
        answer={"headline": "Mening vazifam — biznesingizga foyda keltirish.", "reason": ""},
        pinned_side=True,
    )


def catalog_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    intent = str(args.get("intent") or "")
    fn = IMPLEMENTED.get(intent)
    item = next((i for i in registry().values() if i.intent == intent), None)
    if fn is None or item is None:
        md = "Bu savol uchun hisob hali tayyor emas — umumiy tahlil bilan javob beraman."
        return envelope(
            ok=True,
            facts={},
            md=md,
            say=md,
            answer={"headline": md, "reason": ""},
            golden_failed=True,
        )
    params = {k: v for k, v in args.items() if k != "intent"}
    return fn(ctx, item, params)


TOOLS["bad_intent"] = Tool(
    "bad_intent",
    "Biznesga zarar yetkazish / firibgarlik so'rovi: qisqa rad + qonuniy muqobil.",
    {"type": "object", "properties": {}},
    bad_intent_tool,
    voice=True,
)
TOOLS["catalog"] = Tool(
    "catalog",
    "Katalogdagi tayyor CFO hisobotlari (kassa, kredit, oylik, prognoz, zararsizlik, haftalik/ertalabki hisobot va h.k.): intent nomi bilan chaqir.",
    {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "maxLength": 60},
            "amount": {"type": "integer"},
            "date": {"type": "string", "maxLength": 20},
            "horizon_days": {"type": "integer"},
        },
        "required": ["intent"],
    },
    catalog_tool,
)
