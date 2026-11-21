"""Golden reports: deterministic compute tools that return a full "report" (verdict, KPI tiles,
charts, tables, actions, assumptions) + Live speech segments with [cue]s + a plan to approve.

Specs live in /golden/Q<N>_*.md. The LLM never computes: every number shown or spoken is from the
payload. Registry: INTENTS (keyword rules + param extraction), used by the chat router and Live.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from apps.engine import channels as CH

from . import uz_format as uz
from .tools import TOOLS, Tool, ToolContext, envelope, propose

D0 = Decimal(0)


def N(x: Decimal, step: int = 1) -> str:
    """'49 420' (thousands with spaces)."""
    v = (Decimal(x) / step).quantize(Decimal(1), ROUND_HALF_UP) * step
    return uz.group_digits(int(v))


def S(x: Decimal) -> str:
    v = Decimal(x)
    return ("+" if v > 0 else "") + N(v, 10_000 if abs(v) >= 1_000_000 else 10)


def MLN(x: Decimal) -> str:
    return uz.format_mln(Decimal(x))


def say(x: Decimal, step: int = 1000) -> str:
    v = (abs(Decimal(x)) / step).quantize(Decimal(1), ROUND_HALF_UP) * step
    if v < 1000:
        return uz.uz_number_words(int(v))
    return uz.speech_amount(v).removesuffix(" so'm")


def month_label(m: str) -> str:
    return f"{uz.MONTHS[int(m[5:7]) - 1]} {m[:4]}"


def _summary() -> dict[str, Any] | None:
    from apps.integrations.models import DataSource

    src = DataSource.objects.exclude(summary={}).order_by("-last_synced_at").first()
    return (src.summary or {}) if src else None


# --- Q1 channel_economics ----------------------------------------------------------------------
def channel_economics_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = _summary()
    if not s or not (s.get("details") or {}).get("channels"):
        md = "**Kanallar bo'yicha sotuv ma'lumoti topilmadi.** Sotuv varag'ida 'Kanal' ustuni (Zal / Yandex / Uzum / O'z dostavka) kerak — shu ustunni to'ldirsangiz, darhol hisoblayman."
        return envelope(
            ok=True,
            facts={},
            md=md,
            say=md.strip("*"),
            answer={"headline": md.strip("*"), "reason": ""},
        )
    p = CH.Params()
    if args.get("shift_pct") is not None:
        p.shift_pct = Decimal(str(args["shift_pct"])) / 100
    if args.get("markup_pct") is not None:
        p.markup_pct = Decimal(str(args["markup_pct"])) / 100
    if args.get("couriers"):
        p.couriers = int(args["couriers"])
    if args.get("exit"):
        p.exit_only = str(args["exit"]).lower()
    if isinstance(args.get("orders"), dict):
        p.orders = {k: Decimal(str(v)) for k, v in args["orders"].items()}
    e = CH.compute(s, p)
    own, aggs = e.own, sorted(e.aggregators, key=lambda c: -c.keep100k)
    if own is None or not aggs:
        miss = ", ".join(e.missing) or "agregator yoki o'z dostavka kanali"
        md = f"**Hisoblash uchun ma'lumot yetishmaydi: {miss}.** Shu ma'lumotni kiritsangiz, kanallarni solishtiraman."
        return envelope(
            ok=True,
            facts={},
            md=md,
            say=md.strip("*"),
            answer={"headline": md.strip("*"), "reason": ""},
        )
    best_agg = aggs[0]
    rec = e.best
    exit_s = next(sc for sc in e.scenarios if sc.key == "exit")
    recv_total = sum(e.receivables.values(), D0)
    per_day = (own.orders / 30).quantize(Decimal(1), ROUND_HALF_UP)
    load_now, load_plan = (
        int((e.load_now * 100).quantize(Decimal(1), ROUND_HALF_UP)),
        int((e.load_plan * 100).quantize(Decimal(1), ROUND_HALF_UP)),
    )
    plan = e.own_plan
    mon = month_label(e.month)
    agg_names = " va ".join(c.name.split()[0] for c in aggs)
    verdict = (
        f"{agg_names}'dan chiqmang — ular foydali. Lekin o'z dostavkangiz hozir eng kam foyda qoldiryapti: kuryer atigi {load_now}% band."
        if own.keep100k < min(c.keep100k for c in aggs)
        else f"O'z dostavkangiz eng foydali kanal. {agg_names}'ni yangi mijoz manbai sifatida saqlang."
    )
    verdict_hl = f"Ikkalasini birga ishlating — oyiga {S(rec.delta)} so'm foyda va ~{MLN(plan.revenue - own.revenue)} pul tezroq."
    est = " (taxmin: tushum ÷ o'rtacha chek)" if own.orders_estimated else ""
    kpis = [
        {
            "label": "Eng foydali kanal hozir",
            "value": best_agg.name.split()[0],
            "sub": f"{N(best_agg.keep100k, 10)} / 100 000 so'm",
        },
        {
            "label": "O'z dostavka hozir",
            "value": N(own.keep100k, 10),
            "sub": f"kuryer {load_now}% yuklangan",
            "tone": "bad",
        },
        {
            "label": "Tavsiya natijasi",
            "value": S(rec.delta),
            "sub": f"so'm / oy · {MLN(rec.delta * 12)} / yil",
            "tone": "good",
        },
        {
            "label": "Agregatorlarda turgan pul",
            "value": N(recv_total, 100_000),
            "sub": f"{month_label(e.month)} oxiri holatiga",
        },
    ]
    stack_rows = []
    for c in [*aggs, own]:
        stack_rows.append(
            {
                "kanal": c.name + (" (hozir)" if c.kind == "own" else ""),
                "Masalliq": int(c.per100k(c.cost)),
                "Komissiya / dostavka": int(c.per100k(c.commission)),
                "Qadoq": int(c.per100k(c.packaging)),
                "Sizga qoladi": int(c.keep100k),
            }
        )
    stack_rows.append(
        {
            "kanal": own.name + " (reja)",
            "Masalliq": int(plan.per100k(plan.cost)),
            "Komissiya / dostavka": int(plan.per100k(plan.commission)),
            "Qadoq": int(plan.per100k(plan.packaging)),
            "Sizga qoladi": int(plan.keep100k),
        }
    )
    table100 = {
        "columns": [
            "Kanal",
            "Tushum (oy)",
            "Buyurtma",
            "O'rtacha chek",
            "Masalliq",
            "Komissiya / dostavka",
            "Qadoq",
            "Sizga qoladi",
        ],
        "rows": [
            [
                c.name,
                N(c.revenue, 10_000),
                N(c.orders) + ("*" if c.orders_estimated else ""),
                N(c.avg_check, 100),
                N(c.per100k(c.cost), 10),
                f"{N(c.per100k(c.commission), 10)} ({'komissiya ' + str(int((c.rate * 100).quantize(Decimal(1)))) + '%' if c.kind == 'aggregator' else 'kuryer + yoqilg‘i'})",
                N(c.per100k(c.packaging), 10),
                f"**{N(c.keep100k, 10)}**",
            ]
            for c in [*aggs, own]
        ],
    }
    variants = [
        {
            "variant": ("❌ " if sc.key == "exit" else "✅ " if sc.key == "both" else "")
            + sc.title,
            "what": sc.what,
            "delta": int(sc.delta),
            "year": MLN(sc.delta * 12),
            "risk": sc.risk,
            "highlight": sc.key == "both",
        }
        for sc in e.scenarios
    ]
    actions = [
        f"**{agg_names}'ni o'chirmang** — oyiga {MLN(-exit_s.delta)} foyda va yangi mijoz.",
        f'**Telegram-bot / sayt**: "o\'zimizdan buyurtma bersangiz −{int(p.discount_pct * 100)}%". Har agregator paketiga QR-varaqcha.',
        f"**{agg_names} menyusida narx +{int(p.markup_pct * 100)}%**. Zal va olib ketish narxi o'zgarmaydi.",
        "**Hozircha 2-kuryer olmang** — yuklama 70% ga yetguncha."
        if e.load_plan < Decimal("0.7") or p.couriers > 1
        else "**2-kuryer oling** — yuklama 70% dan oshadi.",
        f"**30 kundan keyin tekshiring:** o'z dostavka buyurtmalari {N(own.orders)} → ~{N(plan.orders)}.",
    ]
    assumptions = (
        f"Taxminlar: kuryer quvvati {N(p.capacity)} buyurtma/oy · qo'shimcha buyurtmaga yoqilg'i {N(p.fuel_per_order)} so'm · mijozlarning {int(p.shift_pct * 100)}% i o'tadi · "
        f"narx +{int(p.markup_pct * 100)}% da agregator buyurtmalari −{int(p.markup_drop_pct * 100)}% · qadoq tushumning {str((p.packaging_rate * 100).normalize()).replace('.', ',')}% "
        f"(faylda Kassa bo'yicha {str((e.packaging_check * 100).quantize(Decimal('0.1'))).replace('.', ',')}%)"
        + (
            " · *buyurtma soni taxmin: tushum ÷ oyning o'rtacha cheki (faylda kanal bo'yicha buyurtma soni yo'q)"
            if own.orders_estimated
            else ""
        )
        + ". O'zgartirsangiz, qayta hisoblanadi."
    )
    sections = [
        {
            "id": "chart_100k",
            "title": f"Har 100 000 so'mlik buyurtmadan qayerga ketadi ({mon})",
            "chart": {
                "type": "stacked_bar_horizontal",
                "unit": "so'm",
                "series": ["Masalliq", "Komissiya / dostavka", "Qadoq", "Sizga qoladi"],
                "colors": ["#94A3B8", "#F87171", "#CBD5E1", "#2DD4BF"],
                "x": "kanal",
                "data": stack_rows,
                "highlight": "Sizga qoladi",
            },
        },
        {
            "id": "table_100k",
            "title": "Har 100 000 so'mlik buyurtmadan sizga qancha qoladi",
            "table": table100,
            "note": f"Nega o'z dostavka kam qoldiryapti? Kuryer oyligi ({MLN(e.courier_cost)}) va yoqilg'i ({MLN(e.fuel)}) — qat'iy xarajat. Kuryer oyiga {N(own.orders)}{est} buyurtma tashiydi, quvvati ~{N(p.capacity)} — {load_now}% yuklangan.",
        },
        {
            "id": "profit",
            "title": "Kanal bo'yicha oylik foyda (komissiya va dostavkadan keyin)",
            "table": {
                "columns": ["Kanal", f"Foyda ({uz.MONTHS[int(e.month[5:7]) - 1]})"],
                "rows": [
                    [c.name, N(c.profit, 10_000)]
                    for c in sorted([*aggs, own], key=lambda c: -c.profit)
                ]
                + [
                    [
                        "**Jami dostavka kanallari**",
                        f"**{N(sum((c.profit for c in [*aggs, own]), D0), 10_000)}**",
                    ]
                ],
            },
        },
        {
            "id": "variants",
            "title": "Variantlar: oylik foyda o'zgarishi",
            "chart": {
                "type": "bar",
                "x": "variant",
                "y": "qiymat",
                "unit": "so'm",
                "data": [
                    {
                        "variant": v["variant"].strip("❌✅ "),
                        "qiymat": v["delta"],
                        "color": "#F87171"
                        if v["delta"] < 0
                        else ("#2DD4BF" if v["highlight"] else "#5EEAD4"),
                    }
                    for v in variants
                ],
            },
            "table": {
                "columns": ["Variant", "Nima qilasiz", "Oylik foyda o'zgarishi", "Yillik", "Xavf"],
                "rows": [
                    [v["variant"], v["what"], S(Decimal(v["delta"])), v["year"], v["risk"]]
                    for v in variants
                ],
                "highlight_last": True,
            },
            "note": f"Natija: dostavka kanallaridan oylik foyda {MLN(sum((c.profit for c in [*aggs, own]), D0))} → {MLN(sum((c.profit for c in [*aggs, own]), D0) + rec.delta)}"
            + (
                f"; bu {mon} sof foydangizga ({MLN(e.net_profit)}) nisbatan +{int((rec.delta / e.net_profit * 100).quantize(Decimal(1)))}%."
                if e.net_profit > 0
                else "."
            ),
        },
        {
            "id": "courier",
            "title": "Kuryer yuklamasi",
            "chart": {
                "type": "progress",
                "now": float(e.load_now),
                "plan": float(e.load_plan),
                "hire_second_at": 0.70,
                "label_now": f"Hozir: {N(own.orders)} / {N(p.capacity * p.couriers)} buyurtma",
                "label_plan": f"Reja: {N(plan.orders)} / {N(p.capacity * p.couriers)} buyurtma",
                "note": "2-kuryer yuklama 70% dan oshgandan keyin arziydi.",
            },
        },
        {
            "id": "receivables",
            "title": "Oy oxirida agregatorlarda turgan pulingiz",
            "chart": {
                "type": "line",
                "x": "oy",
                "y": "qiymat",
                "unit": "mln so'm",
                "data": [
                    {
                        "oy": month_label(m)[:3].capitalize() + " " + m[:4],
                        "qiymat": float((v / 1_000_000).quantize(Decimal("0.1"))),
                    }
                    for m, v in e.receivables_history
                ],
            },
            "note": f"{month_label(e.month)} oxirida agregatorlarda {MLN(recv_total)} ("
            + ", ".join(f"{k} {MLN(v)}" for k, v in e.receivables.items())
            + "). Ular keyingi oyning 8–10-sanasida tushadi; o'z dostavka puli shu kuni.",
        },
        {"id": "actions", "title": "Nima qilish kerak (shu hafta)", "actions": actions},
    ]
    report = {
        "type": "report",
        "id": "q1_channel_economics",
        "intent": "channel_economics",
        "period": mon,
        "verdict": verdict,
        "verdict_highlight": verdict_hl,
        "kpis": kpis,
        "sections": sections,
        "assumptions": assumptions,
        "collapsed_sections": ["chart_100k"],
    }
    speech = [
        {
            "cue": "verdict+kpi",
            "text": f"Qisqasi: {agg_names}'dan chiqmang — ular sizga foydali. Lekin o'z dostavkangizdan to'liq foydalanmayapsiz.",
        },
        {
            "cue": "chart_100k",
            "text": f"Qarang: har yuz ming so'mlik buyurtmadan {aggs[0].name.split()[0]} sizga {say(aggs[0].keep100k)}"
            + (f", {aggs[1].name.split()[0]} {say(aggs[1].keep100k)}" if len(aggs) > 1 else "")
            + f" so'm qoldiradi. O'z dostavkangiz esa {say(own.keep100k)} — chunki kuryeringiz kuniga atigi {say(per_day, 1)}ta buyurtma tashiydi.",
        },
        {
            "cue": "variants",
            "text": f"Agregatorlardan butunlay chiqsangiz, oyiga {say(-exit_s.delta, 1_000_000)} foyda yo'qotasiz — buni qilmang. Buning o'rniga doimiy mijozlarni {say(p.discount_pct * 100, 1)} foiz chegirma bilan o'z Telegram-botingizga o'tkazing va agregatorda narxni {say(p.markup_pct * 100, 1)} foiz yuqori qo'ying.",
        },
        {
            "cue": "kpi_result+receivables",
            "text": f"Shunda oyiga yana {say(rec.delta, 100_000)} so'm foyda olasiz. Hozir agregatorlarda {say(recv_total, 1_000_000)} pulingiz turibdi — reja bilan uning bir qismi ancha oldin qo'lingizga keladi.",
        },
        {
            "cue": "courier+actions",
            "text": (
                "Ikkinchi kuryerni hozircha olmang — avval birinchisini to'ldiring. "
                if e.load_plan < Decimal("0.7")
                else ""
            )
            + "Shu rejani tasdiqlaysizmi? Tasdiqlasangiz, o'ttiz kundan keyin natijani tekshiraman.",
        },
        {"cue": "approve_button", "text": ""},
    ]
    short = f"{agg_names}'dan chiqmang — ular oyiga {say(-exit_s.delta, 1_000_000)} foyda beradi. Mijozlarni o'z Telegram-botingizga o'tkazib, agregatorda narxni {say(p.markup_pct * 100, 1)} foiz oshirsangiz, oyiga yana {say(rec.delta, 100_000)} so'm foyda qo'shiladi."
    due = ctx.base.today if not ctx.base.insufficient_data else None
    plan_obj = propose(
        ctx,
        "reminder",
        {
            "summary": f"Dostavka rejasi: Telegram-bot −{int(p.discount_pct * 100)}%, agregatorda narx +{int(p.markup_pct * 100)}%; 30 kundan keyin tekshirish ({N(own.orders)} → ~{N(plan.orders)} buyurtma)",
            "note": "golden:Q1 channel_economics",
            "steps": [re.sub(r"\*\*", "", a) for a in actions],
        },
        (due + timedelta(days=30)) if due else None,
    )
    md_lines = [
        f"**Xulosa: {verdict} {verdict_hl}**",
        "",
        f"### Har 100 000 so'mlik buyurtmadan sizga qancha qoladi ({mon})",
        "| " + " | ".join(table100["columns"]) + " |",
        "|---|" + "---:|" * (len(table100["columns"]) - 1),
    ]
    md_lines += ["| " + " | ".join(r) + " |" for r in table100["rows"]]
    md_lines += [
        "",
        "### Variantlar (oyiga)",
        "| Variant | Oylik foyda o'zgarishi | Yillik | Xavf |",
        "|---|---:|---:|---|",
    ]
    md_lines += [
        f"| {v['variant']} | {S(Decimal(v['delta']))} | {v['year']} | {v['risk']} |"
        for v in variants
    ]
    md_lines += [
        "",
        "### Nima qilish kerak (shu hafta)",
        *[f"{i}. {a}" for i, a in enumerate(actions, 1)],
        "",
        f"_{assumptions}_",
        "",
        "CHIPS: 50% ini o'tkazsam-chi? | 2-kuryer olsam? | Uzum'dan chiqsam?",
    ]
    facts: dict[str, Any] = {
        "verdict": verdict,
        "recommended_delta": S(rec.delta),
        "exit_delta": S(exit_s.delta),
        "receivables": N(recv_total),
        "load_now": f"{load_now}%",
        "load_plan": f"{load_plan}%",
        "orders_now": N(own.orders),
        "orders_plan": N(plan.orders),
        **{f"keep_{c.name}": N(c.keep100k, 10) for c in [*aggs, own]},
        "keep_plan": N(plan.keep100k, 10),
        **{f"profit_{c.name}": N(c.profit, 10_000) for c in [*aggs, own]},
        **{f"scenario_{sc.key}": S(sc.delta) for sc in e.scenarios},
    }
    return envelope(
        ok=True,
        facts=facts,
        md="\n".join(md_lines),
        say=" ".join(seg["text"] for seg in speech if seg["text"]),
        speech_segments=speech,
        speech_short=short,
        ui_blocks=[report],
        proposed_plan=plan_obj,
        answer={"headline": f"{verdict} {verdict_hl}", "reason": ""},
        raw={
            "q1": {
                "keep": {c.name: str(c.keep100k) for c in [*aggs, own]},
                "keep_plan": str(plan.keep100k),
                "scenarios": {sc.key: str(sc.delta) for sc in e.scenarios},
                "load_now": str(e.load_now),
                "load_plan": str(e.load_plan),
                "orders_now": str(own.orders),
                "orders_plan": str(plan.orders),
                "receivables": str(recv_total),
            }
        },
    )


# --- registry -----------------------------------------------------------------------------------
@dataclass
class Intent:
    id: str
    spec: str
    tool: str
    pattern: re.Pattern[str]
    params: Callable[[str], dict[str, Any]]


def _q1_params(t: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    m = re.search(r"(\d{1,3})\s*%\s*(?:i|ini|ni)?\s*(?:o'tkaz|ko'chir)", t)
    if m:
        out["shift_pct"] = int(m.group(1))
    m = re.search(r"narx\w*\s+\+?(\d{1,2})\s*%", t)
    if m:
        out["markup_pct"] = int(m.group(1))
    if re.search(r"(2|ikkinchi|yana bitta)\s*-?\s*kuryer", t):
        out["couriers"] = 2
    m = re.search(r"(uzum|yandex)\w*\s*(?:dan|'dan)?\s+chiq", t)
    if m:
        out["exit"] = m.group(1)
    return out


INTENTS = [
    Intent(
        "channel_economics",
        "golden/Q1_agregator_vs_ozdostavka.md",
        "channel_economics",
        re.compile(
            r"agregator|yandex|uzum|o'z\s+dostavka|dostavka\w*\s+(dan|qancha|foyda)|kuryer\s+(olsam|kerak)|savdo\s+kanal|qaysi\s+kanal|komissiya\w*\s+.*(yeb|ko'p)",
            re.I,
        ),
        _q1_params,
    ),
]


def match(text: str, prev_intent: str | None = None) -> tuple[Intent, dict[str, Any]] | None:
    t = re.sub(r"[‘’ʻʼ`]", "'", text).lower()
    for it in INTENTS:
        if it.pattern.search(t):
            return it, it.params(t)
    # a follow-up with only a parameter ("50% ini o'tkazsam-chi?") continues the last golden intent
    if prev_intent:
        it = next((i for i in INTENTS if i.id == prev_intent), None)
        if it is not None:
            params = it.params(t)
            if params:
                return it, params
    return None


def last_intent(conversation_id: int) -> str | None:
    from .models import Message

    m = (
        Message.objects.filter(conversation_id=conversation_id, role="assistant")
        .order_by("-created_at")
        .values("model", "tool_calls")
        .first()
    )
    if not m or m["model"] != "golden":
        return None
    names = {c.get("name") for c in (m["tool_calls"] or []) if isinstance(c, dict)}
    return next((i.id for i in INTENTS if i.tool in names), None)


GOLDEN_TOOLS = [
    Tool(
        "channel_economics",
        "Savdo kanallari iqtisodi (golden Q1): Yandex/Uzum/O'z dostavka — har 100 000 so'mdan qoladi, kanal foydasi, variantlar (chiqish, mijozni o'tkazish, narx ustamasi), kuryer yuklamasi, agregatorda turgan pul. To'liq hisobot + reja.",
        {
            "type": "object",
            "properties": {
                "shift_pct": {"type": "integer", "minimum": 0, "maximum": 100},
                "markup_pct": {"type": "integer", "minimum": 0, "maximum": 50},
                "couriers": {"type": "integer", "minimum": 1, "maximum": 5},
                "exit": {"type": "string", "enum": ["uzum", "yandex"]},
            },
        },
        channel_economics_tool,
    ),
]
TOOLS.update({t.name: t for t in GOLDEN_TOOLS})
