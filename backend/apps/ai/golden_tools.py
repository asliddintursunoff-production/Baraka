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
    if args.get("markup_pct") is not None:
        p.markup_drop_pct = (Decimal(str(args["markup_pct"])) * Decimal("0.6")).quantize(
            Decimal(1)
        ) / 100
    if isinstance(args.get("orders"), dict):
        p.orders = {k: Decimal(str(v)) for k, v in args["orders"].items()}
    e = CH.compute(s, p)
    changed = any(args.get(k) is not None for k in ("shift_pct", "markup_pct", "couriers", "exit"))
    e0 = CH.compute(s, CH.Params(orders=p.orders)) if changed else None
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
    if e0 is not None and e0.own_plan is not None and plan is not None:
        rows = [
            ["Tavsiya natijasi (oyiga)", S(e0.best.delta), S(rec.delta)],
            ["O'z dostavka buyurtmalari (reja)", N(e0.orders_plan), N(e.orders_plan)],
            [
                "Kuryer yuklamasi (reja)",
                f"{int((e0.load_plan * 100).quantize(Decimal(1)))}%",
                f"{load_plan}%",
            ],
        ]
        ex1 = next((sc for sc in e.scenarios if sc.key == "exit_one"), None)
        if ex1:
            rows.append([ex1.title + " (oyiga)", "—", S(ex1.delta)])
            verdict = f"{ex1.title} oyiga {MLN(ex1.delta)} — chiqmang. " + verdict
        sections.insert(
            0,
            {
                "id": "compare",
                "title": "Oldin → Yangi",
                "table": {"columns": ["Ko'rsatkich", "Oldin", "Yangi"], "rows": rows},
            },
        )
        if e.load_plan > Decimal("0.85") and p.couriers == 1:
            sections[0]["note"] = (
                f"Kuryer {load_plan}% band bo'lib qoladi — chegarada, sifat tushishi mumkin; avval 30% dan boshlang."
            )
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


# --- Q2 hire_payback -------------------------------------------------------------------------
ROLE_UZ = {
    "ofitsiant": "ofitsiant",
    "oshpaz": "oshpaz (lavash ustasi)",
    "kassir": "kassir",
    "kuryer": "kuryer",
    "farrosh": "farrosh",
}


def hire_payback_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from apps.engine import hiring as HR

    s = _summary()
    if not s or not (s.get("details") or {}).get("channels"):
        md = "**Hisoblash uchun sotuv va ish haqi ma'lumoti kerak.** Sotuv (Kanal ustuni bilan) va Ish haqi varaqlarini to'ldiring — darhol hisoblayman. Qaysi lavozim va qancha oylik?"
        return envelope(
            ok=True,
            facts={},
            md=md,
            say=md.strip("*"),
            answer={"headline": md.strip("*"), "reason": ""},
        )
    role_given = args.get("role")
    p = HR.Params(role=str(role_given or "ofitsiant"))
    if args.get("salary"):
        p.salary = Decimal(str(args["salary"]))
    if args.get("official") is not None:
        p.official = bool(args["official"])
    # courier orders: from the channel economics model (estimate when the file has no counts)
    try:
        e1 = CH.compute(s)
        if e1.own is not None:
            p.courier_orders = e1.own.orders
    except Exception:
        pass
    h = HR.compute(s, p)
    role = ROLE_UZ.get(h.role, h.role)
    net, cost = h.net, h.cost
    ok = net > 0
    mon = month_label(h.month)
    loads = [
        ("Oshxona — shanba", h.sat_checks, Decimal(90), "chek"),
        ("Oshxona — ish kunlari", h.weekday_checks, Decimal(90), "chek"),
        ("Kassa — eng band soat", h.peak_checks, Decimal(60), "chek/soat"),
        ("Kuryer", h.courier_orders, Decimal(450), "buyurtma"),
    ]
    pct = lambda v, c: int((v / c * 100).quantize(Decimal(1), ROUND_HALF_UP)) if c else 0
    dec = lambda v: str(Decimal(v).quantize(Decimal("0.1"))).replace(".", ",")
    lost_txt = f"navbat sababli yo'qotilgan kunlar oxirgi 3 oyda: {h.lost_days_recent}" + (
        f" (oxirgisi {h.last_lost_day})" if h.last_lost_day else ""
    )
    if ok:
        verdict = f"Yangi {role} o'zini oqlaydi — oyiga +{N(net, 1000)} so'm, {dec(h.payback_months or 0)} oyda qoplaydi."
        hl = ""
    else:
        verdict = (
            f"Hozir yangi {role} o'zini oqlamaydi — har oy ~{N(-net, 10_000)} so'm zarar. Oshxona va kassa hali bo'sh quvvatda"
            + (
                ", oxirgi 3 oyda navbat sababli birorta buyurtma yo'qolmagan."
                if h.lost_days_recent == 0
                else "."
            )
        )
        hl = f"Buning o'rniga kassirlarga qo'shimcha sotuv bonusi bering — oyiga +{str((h.alt_net / 1_000_000).quantize(Decimal('0.01'))).replace('.', ',')} mln so'm."
    kpis = [
        {
            "label": f"{role.capitalize()}: oylik natija",
            "value": S(net) if net >= 0 else "−" + N(-net, 1000),
            "sub": f"narxi {MLN(cost)} · foyda {MLN(h.gain_gp)}",
            "tone": "good" if ok else "bad",
        },
        {
            "label": "Qoplash muddati",
            "value": (dec(h.payback_months or 0) + " oy") if ok else "Qoplamaydi",
            "sub": f"12 oyda {MLN(h.cumulative[-1])}",
            "tone": "good" if ok else "bad",
        },
        {
            "label": "Yaxshiroq variant",
            "value": S(h.alt_net),
            "sub": f"kassirga {int(p.bonus_pct * 100)}% bonus · so'm/oy",
            "tone": "good",
        },
        {
            "label": "Ishchi kerak bo'ladi",
            "value": f"~{h.hire_month}" if h.hire_month else "—",
            "sub": f"shanba ≥ {int(h.sat_threshold)} chek bo'lganda",
        },
    ]
    cost_rows = [
        [
            "Oklad" + (f" ({h.salary_source})" if "taxmin" in h.salary_source else ""),
            N(h.salary, 1000),
        ]
    ]
    if h.sales_share:
        cost_rows.append(
            [
                f"Zal savdosidan {str(p.sales_pct * 100).rstrip('0').rstrip('.').replace('.', ',')}%",
                N(h.sales_share, 1000),
            ]
        )
    if h.social_tax:
        cost_rows.append(["Ijtimoiy soliq 12%", N(h.social_tax, 1000)])
    cost_rows += [
        [f"Xodim ovqati (12 × {h.meal_dish})", N(h.meals, 1000)],
        ["**Jami narxi**", f"**{N(cost, 1000)}**"],
        [
            f"{'Zal cheki +' + str(int(p.uplift * 100)) + '% → yalpi foyda' if h.role == 'ofitsiant' else 'Qo‘shimcha yalpi foyda'}",
            "+" + N(h.gain_gp, 1000),
        ],
        ["**Sof natija**", f"**{S(net) if net >= 0 else '−' + N(-net, 1000)}**"],
    ]
    sections = [
        {
            "id": "chart_cumulative",
            "title": "12 oyda yig'ma natija (mln so'm)",
            "chart": {
                "type": "line_multi",
                "x_labels": h.months_labels,
                "zero_line": True,
                "unit": "mln so'm",
                "series": [
                    {
                        "name": f"Yangi {role}",
                        "color": "#F87171",
                        "data": [
                            float((v / 1_000_000).quantize(Decimal("0.01"))) for v in h.cumulative
                        ],
                    },
                    {
                        "name": "Kassirga bonus (tavsiya)",
                        "color": "#14B8A6",
                        "data": [
                            float((v / 1_000_000).quantize(Decimal("0.01")))
                            for v in h.alt_cumulative
                        ],
                    },
                ],
            },
        },
        {
            "id": "load",
            "title": "Xodimlaringiz yuklamasi (oxirgi 3 oy)",
            "chart": {
                "type": "progress_list",
                "threshold": 0.85,
                "items": [
                    {
                        "label": lb,
                        "value": float(v / c) if c else 0,
                        "note": f"{dec(v)} / {int(c)} {u} · {pct(v, c)}%",
                    }
                    for lb, v, c, u in loads
                ],
                "note": f"Qizil chiziq — 85%: undan oshsa ishchi olish vaqti. {lost_txt.capitalize()}.",
            },
        },
        {
            "id": "cost",
            "title": f"{role.capitalize()}: oyiga narxi va foydasi",
            "table": {"columns": ["Modda", "So'm / oy"], "rows": cost_rows},
            "note": (
                f"O'zini oqlashi uchun: zal cheki +{dec(h.breakeven_uplift * 100)}% yoki zal savdosi {MLN(h.breakeven_hall_rev)}/oy"
                + (
                    f" (~{h.months_to_breakeven} oyda, o'sish oyiga {dec(h.hall_growth * 100)}%)."
                    if h.months_to_breakeven
                    else "."
                )
            )
            if h.role == "ofitsiant"
            else None,
        },
        {
            "id": "alternative",
            "title": "Shu pulga yaxshiroq variant",
            "table": {
                "columns": ["Variant", "Oylik xarajat", "Oylik sof natija", "12 oyda"],
                "rows": [
                    [
                        f"❌ Yangi {role}",
                        N(cost, 1000),
                        S(net) if net >= 0 else "−" + N(-net, 1000),
                        MLN(h.cumulative[-1]),
                    ],
                    [
                        f"✅ Kassirlarga qo'shimcha sotuv bonusi ({int(p.bonus_pct * 100)}%)",
                        N(h.alt_cost, 1000),
                        S(h.alt_net),
                        MLN(h.alt_cumulative[-1]),
                    ],
                ],
            },
            "note": f'Kassir har buyurtmada bitta taklif qiladi ("Kombo qilib beraymi?", "Sous qo\'shaymi?"). Zal va olib ketish tushumi {int(p.uplift * 100)}% oshsa: +{MLN(h.alt_revenue)} tushum → +{MLN(h.alt_gp)} yalpi foyda; bonus {N(h.alt_cost, 1000)} so\'m.',
        },
        {
            "id": "signals",
            "title": "Qachon ishchi olish kerak — signallar",
            "table": {
                "columns": ["Signal", "Hozir", "Chegara"],
                "rows": [
                    [
                        "Shanba cheklari",
                        dec(h.sat_checks),
                        f"≥ {int(h.sat_threshold)}"
                        + (f" (~{h.hire_month})" if h.hire_month else ""),
                    ],
                    ['"Ulgurmadi" kunlari', f"{h.lost_days_recent} / 3 oy", "≥ 2 / oy"],
                    ["Pik soat cheklari", dec(h.peak_checks), "≥ 45"],
                    ["Zal savdosi", MLN(h.hall_revenue), f"≥ {MLN(h.breakeven_hall_rev)}"],
                ],
            },
            "note": "AI signallarni har kuni kuzatadi va vaqti kelganda xabar beradi.",
        },
        {
            "id": "actions",
            "title": "Nima qilish kerak",
            "actions": (
                [f"**Hozir {role} olmang.**"]
                if not ok
                else [f"**{role.capitalize()}ni sinov muddati bilan oling.**"]
            )
            + [
                f'**Kassirlarga "bitta taklif" qoidasi + {int(p.bonus_pct * 100)}% bonus**: "Kombo qilib beraymi? Sous qo\'shaymi?" — shu haftadan.',
                f"**30 kundan keyin tekshiring:** zal va olib ketishda o'rtacha chek +{int(p.uplift * 100)}% bo'ldimi.",
                f"**Signal kuzatuvini yoqing** — shanba {int(h.sat_threshold)} chekdan oshsa, lavash ustasi olish vaqti.",
            ],
        },
    ]
    if role_given is None:
        sections.insert(
            0,
            {
                "id": "role_note",
                "title": "Lavozim",
                "note": f"Lavozim aytilmadi — {role} uchun hisobladim (fast food'da u taomni stolga olib boradi va qo'shimcha taom tavsiya qiladi). Boshqa lavozimmi: oshpaz, kassir, kuryer?",
            },
        )
    assumptions = (
        f"Taxminlar: {role} oklad {MLN(h.salary)} ({h.salary_source}) · zal cheki +{int(p.uplift * 100)}% · kassir quvvati {int(p.cashier_cap)} chek/soat · "
        f"oshxona {int(p.kitchen_cap)} chek/kun · zal savdosi o'sishi {dec(h.hall_growth * 100)}%/oy · kuryer buyurtmalari {N(h.courier_orders)}"
        + (" (taxmin)" if e1.own is not None and e1.own.orders_estimated else "")
        + ". O'zgartirsangiz, qayta hisoblanadi."
    )
    report = {
        "type": "report",
        "id": "q2_hire_payback",
        "intent": "hire_payback",
        "period": mon,
        "verdict": verdict,
        "verdict_highlight": hl,
        "kpis": kpis,
        "sections": sections,
        "assumptions": assumptions,
    }
    sat_pct = pct(h.sat_checks, Decimal(90))
    speech = [
        {
            "cue": "verdict+kpi",
            "text": f"Qisqasi: hozir {role} olmang — u o'zini oqlamaydi, har oy {say(-net, 100_000)} so'mga yaqin zarar qiladi."
            if not ok
            else f"Qisqasi: {role} o'zini oqlaydi — oyiga {say(net, 100_000)} so'm foyda beradi.",
        },
        {
            "cue": "load",
            "text": f"Sababi: oshxonangiz shanba kuni {say(sat_pct, 1)} foiz band, kassa eng band soatda ham deyarli bo'sh."
            + (
                " Oxirgi uch oyda birorta mijoz navbat sababli ketmagan."
                if h.lost_days_recent == 0
                else ""
            ),
        },
        {
            "cue": "chart_cumulative",
            "text": (
                f"{role.capitalize()} bir yilda {say(-h.cumulative[-1], 100_000)} zarar keltiradi. "
                if h.cumulative[-1] < 0
                else ""
            )
            + f"Uning o'rniga kassirlaringizga har qo'shimcha sotuvdan {say(p.bonus_pct * 100, 1)} foiz bonus bering — oyiga {say(h.alt_net, 100_000)} foyda.",
        },
        {
            "cue": "signals",
            "text": (
                f"Ishchi taxminan {h.hire_month.split()[0].lower()} oyida kerak bo'ladi, shanba kunlari {say(h.sat_threshold, 1)} chekdan oshganda. "
                if h.hire_month
                else ""
            )
            + "Men buni kuzatib, vaqti kelganda sizga o'zim aytaman.",
        },
        {"cue": "approve_button", "text": "Bonus rejasini tasdiqlaysizmi?"},
    ]
    short = (
        f"Hozir {role} olmang — oyiga {say(-net, 100_000)} zarar qiladi, chunki xodimlaringiz hali to'liq band emas. "
        if not ok
        else f"{role.capitalize()} oyiga {say(net, 100_000)} foyda beradi. "
    ) + f"Kassirlarga qo'shimcha sotuv bonusi bering — oyiga {say(h.alt_net, 100_000)} foyda."
    due = ctx.base.today if not ctx.base.insufficient_data else None
    plan_obj = propose(
        ctx,
        "reminder",
        {
            "summary": f"Kassirlarga {int(p.bonus_pct * 100)}% qo'shimcha sotuv bonusi; 30 kundan keyin o'rtacha chekni tekshirish; signal: shanba ≥ {int(h.sat_threshold)} chek",
            "note": "golden:Q2 hire_payback",
            "steps": [re.sub(r"\*\*", "", a) for a in sections[-1]["actions"]],
        },
        (due + timedelta(days=30)) if due else None,
    )
    md = "\n".join(
        [
            f"**Xulosa: {verdict} {hl}**",
            "",
            f"### {role.capitalize()}: oyiga narxi va foydasi ({mon})",
            "| Modda | So'm / oy |",
            "|---|---:|",
            *[f"| {a} | {b} |" for a, b in cost_rows],
            "",
            f"_{assumptions}_",
            "",
            "CHIPS: Oshpaz olsam-chi? | 3 mln oylik bilan? | Kassir olsam?",
        ]
    )
    facts = {
        "net": str(net.quantize(Decimal(1))),
        "cost": str(cost.quantize(Decimal(1))),
        "alt_net": str(h.alt_net.quantize(Decimal(1))),
        "payback": str(h.payback_months),
        "hire_month": h.hire_month,
        "sat_load": f"{sat_pct}%",
        "role": h.role,
    }
    return envelope(
        ok=True,
        facts=facts,
        md=md,
        say=" ".join(x["text"] for x in speech),
        speech_segments=speech,
        speech_short=short,
        ui_blocks=[report],
        proposed_plan=plan_obj,
        answer={"headline": f"{verdict} {hl}".strip(), "reason": ""},
    )


def _q2_params(t: str) -> dict[str, Any]:
    from apps.engine.hiring import role_of

    out: dict[str, Any] = {}
    r = role_of(t)
    if r:
        out["role"] = r
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(mln|million)", t)
    if m:
        out["salary"] = int(float(m.group(1).replace(",", ".")) * 1_000_000)
    if re.search(r"rasmiy", t):
        out["official"] = True
    return out


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
    m = re.search(r"narx\w*\s+\+?(\d{1,2})\s*%", t) or re.search(
        r"(\d{1,2})\s*%\s*(?:qilsam|qo'ysam|oshirsam)", t
    )
    if m:
        out["markup_pct"] = int(m.group(1))
    if re.search(r"narx\w*\s+oshirmasam|faqat\s+mijoz", t):
        out["markup_pct"] = 0
    if re.search(r"(2|ikkinchi|yana bitta)\s*-?\s*kuryer", t):
        out["couriers"] = 2
    m = re.search(r"(uzum|yandex)\w*\s*(?:dan|'dan)?\s+chiq", t)
    if m:
        out["exit"] = m.group(1)
    return out


INTENTS = [
    Intent(
        "hire_payback",
        "golden/Q2_ishchi_olsam_oqlaydimi.md",
        "hire_payback",
        re.compile(
            r"(ishchi|xodim|ofitsiant|ofitsam|oshpaz|lavash\s+usta|kassir|farrosh|odam)\w*\s+(olsam|qo'shsam|kerak|olaymi|olish|yetishma)|ikkinchi\s+kuryer\s+olsam|smenaga\s+odam|o'zini\s+(necha\s+oyda\s+)?oqla|millionlik\s+ishchi|ishchi\s+olish\s+vaqti",
            re.I,
        ),
        _q2_params,
    ),
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


_SIDE = re.compile(
    r"\bnega\b|nima\s+uchun|qanday\s+(hisob|chiqdi|chiqar)|qayerdan\s+(oldi|chiqdi)|qachon\s+(olaman|tushadi|keladi)|qancha\s+turadi|arziydimi|kamaytirsa|tushuntir|formula",
    re.I,
)


def is_side_question(text: str) -> bool:
    """Explanation / follow-up about the report itself (not a parameter change)."""
    return bool(_SIDE.search(re.sub(r"[‘’ʻʼ`]", "'", text).lower()))


def last_intent(conversation_id: int) -> str | None:
    """The golden intent of the conversation's latest report (looks back 4 answers)."""
    from .models import Message

    for m in (
        Message.objects.filter(conversation_id=conversation_id, role="assistant")
        .order_by("-created_at")
        .values("model", "tool_calls")[:4]
    ):
        names = {c.get("name") for c in (m["tool_calls"] or []) if isinstance(c, dict)}
        hit = next((i.id for i in INTENTS if i.tool in names), None)
        if hit:
            return hit
    return None


GOLDEN_TOOLS = [
    Tool(
        "hire_payback",
        "Yana ishchi olsam o'zini oqlaydimi (golden Q2): ishchi narxi, foyda mexanizmi (lavozim bo'yicha), qoplash muddati, 12 oylik yig'ma, xodimlar yuklamasi, signallar, yaxshiroq alternativa.",
        {
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "enum": ["ofitsiant", "oshpaz", "kassir", "kuryer", "farrosh"],
                },
                "salary": {"type": "integer", "minimum": 100000},
                "official": {"type": "boolean"},
            },
        },
        hire_payback_tool,
    ),
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
