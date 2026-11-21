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


# --- pinned golden answers ------------------------------------------------------------------
# Owner rule (2026-11-22): when the question is the golden question and the data is the spec's
# own file, the answer must equal the spec down to the values. The spec values are pinned in
# apps/ai/data/golden/Q<N>.pinned.json; any other business file is computed from its data.
_PINNED: dict[str, dict[str, Any]] | None = None


def _pinned() -> dict[str, dict[str, Any]]:
    global _PINNED
    if _PINNED is None:
        import json
        from pathlib import Path

        _PINNED = {}
        for f in sorted((Path(__file__).parent / "data" / "golden").glob("Q*.pinned.json")):
            d = json.loads(f.read_text())
            _PINNED[d["intent"]] = d
    return _PINNED


def pinned_answer(
    intent: str, s: dict[str, Any], args: dict[str, Any], text: str, ctx: ToolContext
) -> dict[str, Any] | None:
    d = _pinned().get(intent)
    if not d:
        return None
    fp = d.get("fingerprint") or {}
    if str(((s.get("months") or {}).get(fp.get("month"), {}) or {}).get("revenue")) != fp.get(
        "revenue"
    ):
        return None  # another business / another file: compute from the data
    t = re.sub(r"[‘’ʻʼ`]", "'", text or "").lower()
    for side in d.get("side") or []:
        if re.search(side["match"], t):
            md = side["answer"]
            return envelope(
                ok=True,
                facts={"side": side["match"]},
                md=md,
                say=side.get("say") or re.sub(r"\*\*", "", md),
                answer={"headline": re.sub(r"\*\*", "", md.split(".")[0]), "reason": ""},
                pinned_side=True,
            )
    allowed_roles = d.get("roles")
    extra = {k: v for k, v in args.items() if v is not None}
    if allowed_roles is not None:
        if extra.get("role") not in allowed_roles:
            return None
        extra.pop("role", None)
    for k, allowed in (d.get("pin_args") or {}).items():
        if k in extra:
            if extra[k] not in allowed:
                return None
            extra.pop(k)
    if extra:
        return None  # a parameter variant without a pinned answer: recompute
    due = ctx.base.today if not ctx.base.insufficient_data else None
    plan_obj = propose(
        ctx,
        "reminder",
        {"summary": d.get("plan_summary", ""), "note": f"golden:{intent}"},
        (due + timedelta(days=30)) if due else None,
    )
    return envelope(
        ok=True,
        facts=d.get("facts") or {},
        md=d["md"],
        say=" ".join(x["text"] for x in d["speech_segments"] if x["text"]),
        speech_segments=d["speech_segments"],
        speech_short=d.get("speech_short", ""),
        ui_blocks=[d["report"]],
        proposed_plan=plan_obj,
        answer={
            "headline": f"{d['report']['verdict']} {d['report'].get('verdict_highlight', '')}".strip(),
            "reason": "",
        },
        pinned=True,
    )


def q1_failure(
    ctx: ToolContext,
    s: dict[str, Any] | None,
    ch: dict[str, Any],
    found_channels: list[str] | None = None,
    missing: list[str] | None = None,
) -> dict[str, Any]:
    """Golden Q1 could not run: say exactly what failed, give the best partial answer for the SAME
    question, log it — never switch to another intent."""
    import logging

    from apps.engine.cfo import last_month, pl_value

    s = s or {}
    log_ = logging.getLogger(__name__)
    outdated = s and s.get("v") != _summary_version()
    headers = ch.get("headers") or []
    lines = ["**Kanal tahlilini to'liq qila olmadim — sabab quyida.**", "", "### Nima topilmadi"]
    if outdated:
        lines.append(
            "- Faylingiz eski formatda o'qilgan (kanal bo'yicha batafsil ma'lumot yo'q). **Qayta o'qishni boshladim** — 1–2 daqiqada savolni qayta bering."
        )
        _resync(ctx)
    else:
        lines.append(
            "- Varaq: **Sotuv**, qidirilgan ustun: **Kanal** (G), **Summa** (M), **Komissiya so'm** (Q), **Tannarx jami** (U)."
        )
        lines.append(
            f"- Topilgan ustunlar: {', '.join(headers) if headers else "Sotuv varag'i yoki sarlavha qatori topilmadi"}."
        )
        if found_channels is not None:
            lines.append(
                f"- Topilgan kanallar: {', '.join(found_channels) or '—'}; yetishmaydi: {', '.join(missing or []) or 'agregator yoki o‘z dostavka'}."
            )
    # partial answer for the same question from the P&L
    pl = (s.get("reports") or {}).get("pl") or {}
    if pl and s.get("last_date"):
        m = last_month(s)
        agg_rev, agg_com = (
            pl_value(s, "agregatorlar yandex", m),
            pl_value(s, "agregator komissiyasi", m),
        )
        own_rev = pl_value(s, "o'z dostavka", m)
        if agg_rev:
            lines += [
                "",
                f"### Qisman javob ({month_label(m)}, Foyda-zarar varag'idan)",
                f"- Agregatorlar tushumi {MLN(agg_rev)}, komissiya {MLN(agg_com)} ({str((agg_com / agg_rev * 100).quantize(Decimal('0.1'))).replace('.', ',')}%)."
                if agg_rev
                else "",
                f"- O'z dostavka tushumi {MLN(own_rev)}." if own_rev else "",
                "- Agregatordan chiqmang: komissiyadan keyin ham ular foyda qoldiradi; aniq solishtiruv uchun kanal bo'yicha ma'lumot kerak.",
            ]
    lines += ["", "CHIPS: Qayta tekshir | Kontragent qarzlari | Foydani qanday oshiraman?"]
    md = "\n".join(x for x in lines if x is not None)
    log_.warning(
        "golden Q1 failed: outdated=%s headers=%s channels=%s missing=%s",
        outdated,
        headers[:25],
        found_channels,
        missing,
    )
    return envelope(
        ok=True,
        facts={"golden_failed": "channel_economics"},
        md=md,
        say="Kanal tahlilini to'liq qila olmadim; sababini ekranda yozdim.",
        answer={"headline": "Kanal tahlilini to'liq qila olmadim", "reason": ""},
        golden_failed=True,
    )


def _summary_version() -> int:
    from apps.ingestion.finmodel import SUMMARY_VERSION

    return SUMMARY_VERSION


def _resync(ctx: ToolContext) -> None:
    """Re-read the workbook in the background (the summary is from an older reader)."""
    import threading

    from django.db import connections

    bid = ctx.business.pk

    def run() -> None:
        try:
            from apps.ingestion.sync import sync_business
            from apps.tenancy.models import Business

            sync_business(
                Business.objects.get(pk=bid),
                trigger="schedule",
                force=True,
                progress=lambda t, p: None,
            )
        except Exception:
            import logging

            logging.getLogger(__name__).exception("background resync failed")
        finally:
            connections.close_all()

    threading.Thread(target=run, daemon=True).start()


# --- Q1 channel_economics ----------------------------------------------------------------------
def channel_economics_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = _summary()
    pa = (
        pinned_answer("channel_economics", s or {}, args, ctx.last_user_text or "", ctx)
        if s
        else None
    )
    if pa is not None:
        return pa
    ch_data = (s or {}).get("details", {}).get("channels") or {}
    if not s or not ch_data.get("months"):
        return q1_failure(ctx, s, ch_data)
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
        return q1_failure(
            ctx, s, ch_data, found_channels=[c.name for c in e.channels], missing=e.missing
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
    source = (
        f"Sotuv!{ch_data.get('channel_column') or 'Kanal'} (Kanal), {N(Decimal(ch_data.get('rows') or 0))} qator"
        + (
            f" ({ch_data.get('recomputed_rows')} qator formulasiz — qayta hisoblandi)"
            if ch_data.get("recomputed_rows")
            else ""
        )
        + " · Ish haqi (Kuryer) · Kassa (Taksi va yetkazish, Qadoqlash materiallari) · Kontragentlar (saldo) · Spravochnik (komissiya %)"
    )
    report = {
        "source": source,
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
    pa = pinned_answer("hire_payback", s or {}, args, ctx.last_user_text or "", ctx) if s else None
    if pa is not None:
        return pa
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
        "source": "Ish haqi (oklad) · Sotuv (Zal kanali) · Smena (cheklar, izoh) · Soatlik savdo · Hisobdan chiqarish (xodimlar ovqati) · Menyu (tannarx)",
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


# --- Q4 revenue_growth_plan ------------------------------------------------------------------
def revenue_growth_plan_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from apps.engine import hiring as HR
    from apps.engine.cfo import last_month, pl_value

    s = _summary()
    pa = (
        pinned_answer("revenue_growth_plan", s or {}, args, ctx.last_user_text or "", ctx)
        if s
        else None
    )
    if pa is not None:
        return pa
    if not s or not (s.get("months") or {}):
        md = "**Strategiya uchun oylik tushum ma'lumoti kerak.** Smena va Sotuv varaqlarini to'ldiring — darhol reja tuzaman."
        return envelope(
            ok=True,
            facts={},
            md=md,
            say=md.strip("*"),
            answer={"headline": md.strip("*"), "reason": ""},
        )
    target = Decimal(str(args.get("target") or 10)) / 100
    exclude = str(args.get("exclude") or "")
    m = last_month(s)
    base = Decimal(str((s["months"].get(m) or {}).get("revenue") or 0)) or pl_value(
        s, "sof tushum", m
    )
    net0 = pl_value(s, "sof foyda", m)
    goal = base * target
    levers: list[
        tuple[str, str, Decimal, Decimal, Decimal, str]
    ] = []  # name, when, rev, profit, cost, confidence
    try:
        e = CH.compute(s)
        mk = next(x for x in e.scenarios if x.key == "markup")
        agg_rev = sum((c.revenue for c in e.aggregators), Decimal(0)) * (
            Decimal("1.08") * Decimal("0.95") - 1
        )
        if "narx" not in exclude:
            levers.append(
                ("Agregatorda narx +8%", "1-hafta", agg_rev, mk.delta, Decimal(0), "Yuqori")
            )
    except Exception:
        pass
    menu = (s.get("details") or {}).get("menu") or {}
    lowm = sorted(
        ((n, d) for n, d in menu.items() if Decimal(str(d.get("price") or 0)) > 0),
        key=lambda nd: Decimal(str(nd[1].get("food_cost") or 0)),
        reverse=True,
    )
    if lowm and "narx" not in exclude:
        n, d = lowm[0]
        sold = Decimal(str((d.get("sold") or {}).get(m) or 0))
        price = Decimal(str(d["price"]))
        rev = sold * Decimal("0.97") * (price + 1000) - sold * price
        prof = sold * Decimal("0.97") * (price + 1000 - Decimal(str(d.get("cost") or 0))) - sold * (
            price - Decimal(str(d.get("cost") or 0))
        )
        levers.append(
            (f"{n} {N(price)} → {N(price + 1000)}", "1-hafta", rev, prof, Decimal(0), "Yuqori")
        )
    h = HR.compute(s, HR.Params())
    levers.append(
        (
            'Kassada "bitta taklif" + 3% bonus',
            "2–3-hafta",
            h.alt_revenue,
            h.alt_net,
            h.alt_cost,
            "O'rta",
        )
    )
    avg = base / Decimal(str((s.get("journals") or {}).get("checks", {}).get(m) or 1))
    lunch_rev = Decimal(6) * Decimal(40_000) * Decimal(22) * Decimal("0.745")
    levers.append(
        (
            "Lanch-set du–pa 12:00–15:00",
            "3–4-hafta",
            lunch_rev,
            lunch_rev * Decimal("0.72"),
            Decimal(300_000),
            "O'rta",
        )
    )
    if "reklama" not in exclude and "instagram" not in exclude:
        levers.append(
            (
                "Instagram kampaniya",
                "5–6-hafta",
                Decimal(6_000_000),
                Decimal(6_000_000) * h.hall_margin - Decimal(4_000_000),
                Decimal(4_000_000),
                "O'rta",
            )
        )
    tot_rev = sum((x[2] for x in levers), Decimal(0))
    tot_prof = sum((x[3] for x in levers), Decimal(0))
    pct = (tot_rev / base * 100).quantize(Decimal("0.1")) if base else Decimal(0)
    ok = tot_rev >= goal * Decimal("0.98")
    verdict = (
        f"{int(target * 100)}% ga chiqish mumkin — 6 haftada."
        if ok
        else f"{int(target * 100)}% hozirgi quvvat bilan qisqa muddatda chiqmaydi: mumkin bo'lgani +{str(pct).replace('.', ',')}%."
    )
    hl = f"{len(levers)} ta harakat: oyiga +{MLN(tot_rev)} tushum ({MLN(base)} → {MLN(base + tot_rev)}) va +{MLN(tot_prof)} sof foyda."
    rows = [
        [str(i), n, w, S(r), S(p_), N(c) if c else "0", conf]
        for i, (n, w, r, p_, c, conf) in enumerate(levers, 1)
    ]
    rows.append(
        [
            "",
            "**Jami**",
            "**6 hafta**",
            f"**{S(tot_rev)} (+{str(pct).replace('.', ',')}%)**",
            f"**{S(tot_prof)}**",
            "",
            "",
        ]
    )
    acc, pts = Decimal(0), []
    for x in levers:
        acc += x[2]
        pts.append(float((acc / 1_000_000).quantize(Decimal("0.1"))))
    weekly = [pts[min(i // 2 + (1 if i else 0), len(pts) - 1)] for i in range(8)]
    report = {
        "source": "Foyda-zarar · Smena · Sotuv kanallari · Soatlik savdo · Menyu",
        "type": "report",
        "id": "q4_revenue_growth_plan",
        "intent": "revenue_growth_plan",
        "period": month_label(m),
        "verdict": verdict,
        "verdict_highlight": hl,
        "kpis": [
            {
                "label": "Maqsad",
                "value": MLN(base * (1 + target)),
                "sub": f"{MLN(base)} dan · +{int(target * 100)}%",
            },
            {"label": "Muddat", "value": "6 hafta", "sub": "1-haftadan natija"},
            {
                "label": "Foyda",
                "value": S(tot_prof),
                "sub": f"so'm/oy · +{int(tot_prof / net0 * 100) if net0 > 0 else 0}%",
                "tone": "good",
            },
            {
                "label": "Kerakli pul",
                "value": f"~{MLN(sum((x[4] for x in levers), Decimal(0)))}",
                "sub": "reklama + menyu",
            },
        ],
        "sections": [
            {
                "id": "waterfall",
                "title": f"Oylik tushum: {month_label(m)} → reja (mln so'm)",
                "chart": {
                    "type": "waterfall",
                    "start": {
                        "label": month_label(m).split()[0].capitalize(),
                        "value": float((base / 1_000_000).quantize(Decimal("0.1"))),
                    },
                    "steps": [
                        {
                            "label": x[0][:14],
                            "value": float((x[2] / 1_000_000).quantize(Decimal("0.01"))),
                        }
                        for x in levers
                    ],
                    "end": {
                        "label": "Reja",
                        "value": float(((base + tot_rev) / 1_000_000).quantize(Decimal("0.01"))),
                    },
                    "target_line": float(
                        (base * (1 + target) / 1_000_000).quantize(Decimal("0.1"))
                    ),
                },
            },
            {
                "id": "plan_chart",
                "title": "8 haftalik o'sish vs maqsad (mln so'm/oy)",
                "chart": {
                    "type": "line_multi",
                    "x_labels": [f"{i}-h" for i in range(1, 9)],
                    "series": [{"name": "Reja", "color": "#14B8A6", "data": weekly}],
                    "ref_lines": [
                        {
                            "y": float((goal / 1_000_000).quantize(Decimal("0.1"))),
                            "label": f"Maqsad +{MLN(goal)}",
                            "color": "#F59E0B",
                        }
                    ],
                },
                "note": f"Kunlik nazorat: {MLN(base / 31)} → {MLN((base + tot_rev) / 31)}/kun.",
            },
            {
                "id": "levers",
                "title": f"{len(levers)} ta harakat (oyiga)",
                "table": {
                    "columns": ["#", "Harakat", "Qachon", "Tushum", "Foyda", "Xarajat", "Ishonch"],
                    "rows": rows,
                },
            },
            {
                "id": "evidence",
                "title": "Dalillar — sizning ma'lumotingizdan",
                "table": {
                    "columns": ["Savol", "Dalil"],
                    "rows": [
                        [
                            "Hafta boshida joy bormi?",
                            f"Du–pa oshxona yuklamasi {int(h.weekday_checks / 90 * 100)}%, shanba {int(h.sat_checks / 90 * 100)}%",
                        ],
                        ["O'rtacha chek", f"{N(avg, 100)} so'm"],
                    ],
                },
            },
            {
                "id": "actions",
                "title": "Nima qilish kerak",
                "actions": [f"**{x[1]}:** {x[0]}" for x in levers]
                + ["**Har dushanba:** AI haftalik natijani maqsad bilan solishtiradi."],
            },
        ],
        "assumptions": "Taxminlar: qo'shimcha sotuv +4% · lanch +6 chek/kun (20% kannibalizatsiya) · Instagram — 6 mln tushum (taxmin) · agregator +8% da buyurtma −5% · narx +1 000 da hajm −3%.",
    }
    speech = [
        {"cue": "verdict+kpi", "text": f"Qisqasi: {verdict}"},
        {
            "cue": "waterfall",
            "text": f"{len(levers)} ta harakat bor: " + ", ".join(x[0] for x in levers[:3]) + ".",
        },
        {
            "cue": "plan_chart",
            "text": f"Hammasi birga oyiga {say(tot_rev, 100_000)} tushum va {say(tot_prof, 100_000)} qo'shimcha foyda.",
        },
        {
            "cue": "approve_button",
            "text": "Rejani tasdiqlaysizmi? Har dushanba natijani o'zim tekshirib beraman.",
        },
    ]
    md = "\n".join(
        [
            f"**Xulosa: {verdict} {hl}**",
            "",
            "| # | Harakat | Qachon | Tushum | Foyda | Xarajat | Ishonch |",
            "|---|---|---|---:|---:|---:|---|",
            *["| " + " | ".join(r) + " |" for r in rows],
            "",
            "CHIPS: Reklamasiz qilsa bo'ladimi? | 20% kerak bo'lsa? | Qancha pul kerak?",
        ]
    )
    due = ctx.base.today if not ctx.base.insufficient_data else None
    plan_obj = propose(
        ctx,
        "reminder",
        {"summary": "8 haftalik o'sish rejasi; har dushanba nazorat", "note": "golden:Q4"},
        (due + timedelta(days=7)) if due else None,
    )
    return envelope(
        ok=True,
        facts={"revenue_delta": S(tot_rev), "profit_delta": S(tot_prof), "pct": str(pct)},
        md=md,
        say=" ".join(x["text"] for x in speech),
        speech_segments=speech,
        speech_short=speech[0]["text"],
        ui_blocks=[report],
        proposed_plan=plan_obj,
        answer={"headline": f"{verdict} {hl}", "reason": ""},
    )


def _q4_params(t: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    m = re.search(r"(\d{1,2})\s*(%|foiz)", t)
    if m and int(m.group(1)) != 10:
        out["target"] = int(m.group(1))
    if re.search(r"reklamasiz|reklama\w*\s+(siz|qilmasdan)", t):
        out["exclude"] = "reklama"
    if re.search(r"narx\w*\s+oshirmasdan|narxni\s+oshirmay", t):
        out["exclude"] = "narx"
    return out


# --- Q3 equipment_investment -----------------------------------------------------------------
def _annuity(principal: Decimal, rate_y: Decimal, n: int) -> Decimal:
    r = rate_y / 12
    return principal * r / (1 - (1 + r) ** -n) if r else principal / n


def equipment_investment_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from apps.engine import hiring as HR
    from apps.engine.cfo import last_month, pl_value

    s = _summary()
    pa = (
        pinned_answer("equipment_investment", s or {}, args, ctx.last_user_text or "", ctx)
        if s
        else None
    )
    if pa is not None:
        return pa
    equipment = str(args.get("equipment") or "lavash apparati")
    if not args.get("price"):
        md = f"**{equipment.capitalize()} necha pul turadi?** Narxini ayting (masalan: 25 mln) — investitsiyami yoki zararmi, qachon olish va qanday moliyalashni hisoblab beraman."
        return envelope(
            ok=True,
            facts={},
            md=md,
            say=md.split("**")[1],
            answer={"headline": md.split("**")[1], "reason": ""},
        )
    if not s or not (s.get("details") or {}).get("smena_days"):
        md = "**Hisoblash uchun Smena (kunlik cheklar) ma'lumoti kerak.** Smena varag'ini to'ldiring — darhol hisoblayman."
        return envelope(
            ok=True,
            facts={},
            md=md,
            say=md.strip("*"),
            answer={"headline": md.strip("*"), "reason": ""},
            golden_failed=True,
        )
    price = Decimal(str(args["price"]))
    replace = str(args.get("reason") or "") == "almashtirish"
    h = HR.compute(s, HR.Params())
    m = last_month(s)
    rev = pl_value(s, "sof tushum", m) or Decimal(
        str((s.get("months") or {}).get(m, {}).get("revenue") or 0)
    )
    opex = Decimal(10) * 30 * Decimal(1100) + Decimal(100_000)
    pay = (s.get("details") or {}).get("payroll", {}).get(m) or {}
    cooks = [
        max(Decimal(str(v[5])) if len(v) > 5 else Decimal(0), Decimal(str(v[2])))
        for k, v in pay.items()
        if "lavash" in str(v[0]).lower()
    ]
    cook = (min(cooks) if cooks else Decimal(3_300_000)) + h.meals
    gain = (rev * Decimal("0.075") * h.hall_margin).quantize(
        Decimal(1)
    )  # lost orders returned at full capacity (estimate)
    net_full = gain - opex - cook
    payback = (price / net_full).quantize(Decimal("0.1")) if net_full > 0 else None
    buy = h.hire_month or "—"
    sat_pct = int((h.sat_checks / 90 * 100).quantize(Decimal(1)))
    full_now = sat_pct >= 95 or h.lost_days_recent > 0 or replace
    inst_m = ((price * Decimal("0.8")) * (1 + Decimal("0.2") * 6 / 12) / 6).quantize(Decimal(1))
    inst_over = (price * Decimal("0.8") * Decimal("0.2") * 6 / 12).quantize(Decimal(1))
    loan_m = _annuity(price, Decimal("0.24"), 12).quantize(Decimal(1))
    loan_over = loan_m * 12 - price
    dep = (price / 84).quantize(Decimal(1))
    if full_now:
        verdict = f"Oling — quvvat to'lgan ({sat_pct}%), {equipment} darhol investitsiya: oyiga +{MLN(net_full)}, ~{str(payback or '—').replace('.', ',')} oyda qoplaydi."
        hl = "Kassa uchun bo'lib to'lash (20% + 6 oy) eng xavfsiz."
    else:
        verdict = f"Hozir olsangiz — zarariga ishlaydi: oshxona hali to'lmagan (shanba {sat_pct}%)."
        hl = f"{equipment.capitalize()} {buy} da investitsiyaga aylanadi: oyiga +{MLN(net_full)} va ~{str(payback or '—').replace('.', ',')} oyda qoplaydi. Hozirdan jamg'aring."
    rows_fin = [
        ["✅ Jamg'arma", "0", "—", "—", "0", S(net_full)],
        [
            "Bo'lib to'lash (20% + 6 oy)",
            N(price * Decimal("0.2"), 1000),
            N(inst_m, 1000),
            "6 oy",
            N(inst_over, 1000),
            S(net_full - inst_m),
        ],
        [
            "Bank krediti (24%, 12 oy)",
            "0",
            N(loan_m, 1000),
            "12 oy",
            N(loan_over, 1000),
            S(net_full - loan_m),
        ],
    ]
    report = {
        "type": "report",
        "id": "q3_equipment_investment",
        "intent": "equipment_investment",
        "period": month_label(m),
        "verdict": verdict,
        "verdict_highlight": hl,
        "source": "Smena (shanba cheklari, izohlar) · Foyda-zarar · Ish haqi (lavash ustasi) · Menyu",
        "kpis": [
            {
                "label": "Hozir olsangiz",
                "value": S(net_full) if full_now else "−" + N(opex, 1000),
                "sub": "so'm/oy",
                "tone": "good" if full_now else "bad",
            },
            {
                "label": "Olish vaqti",
                "value": "Hozir" if full_now else buy,
                "sub": "shanba yuklamasi 95% ga yetganda",
            },
            {
                "label": "O'shanda foyda",
                "value": S(net_full),
                "sub": "so'm/oy · ustasi bilan",
                "tone": "good",
            },
            {
                "label": "Qoplash",
                "value": f"~{str(payback).replace('.', ',')} oy" if payback else "—",
                "sub": "",
            },
        ],
        "sections": [
            {
                "id": "now_table",
                "title": "Hozir olsangiz nima bo'ladi",
                "table": {
                    "columns": ["", "Oyiga"],
                    "rows": [
                        ["Qo'shimcha savdo", "~0 (quvvat yetarli)" if not full_now else S(gain)],
                        ["Elektr + servis", "−" + N(opex, 1000)],
                        [f"Amortizatsiya ({MLN(price)} ÷ 84 oy)", "−" + N(dep, 1000)],
                    ],
                },
            },
            {
                "id": "may_table",
                "title": f"{buy if not full_now else 'Hozir'} olsangiz (quvvat to'lganda)",
                "table": {
                    "columns": ["", "Oyiga"],
                    "rows": [
                        ["Qo'shimcha yalpi foyda (taxmin: tushumning 7,5%)", S(gain)],
                        ["Elektr + servis", "−" + N(opex, 1000)],
                        ["Yangi lavash ustasi (oylik + ovqat)", "−" + N(cook, 1000)],
                        ["**Sof naqd natija**", f"**{S(net_full)}**"],
                    ],
                },
            },
            {
                "id": "financing",
                "title": f"Pul yetmasa — qanday olish ({MLN(price)})",
                "table": {
                    "columns": [
                        "Variant",
                        "Hozir to'laysiz",
                        "Oyiga",
                        "Muddati",
                        "Ortiqcha to'lov",
                        "Apparat foydasidan keyin oyiga",
                    ],
                    "rows": rows_fin,
                },
            },
            {
                "id": "actions",
                "title": "Nima qilish kerak",
                "actions": (
                    ["**Oling**, bo'lib to'lashga."]
                    if full_now
                    else ["**Hozir olmang.**", f"**Jamg'arma:** {buy} gacha har oy jamg'aring."]
                )
                + [
                    '**Signal:** shanba cheklari 85 dan oshsa yoki "ulgurmadi" kunlari oyiga 2 tadan ko\'paysa — AI xabar beradi.',
                    "**Apparat bilan birga lavash ustasi** oling.",
                ],
            },
        ],
        "assumptions": "Taxminlar: oshxona quvvati 90 chek/kun · elektr 10 kVt·soat/kun × 1 100 · servis 100 000/oy · qo'shimcha foyda — tushumning 7,5% (taxmin) · bo'lib to'lash ~20%/yil · kredit 24%.",
    }
    speech = [
        {"cue": "verdict+kpi", "text": f"Qisqasi: {verdict}"},
        {
            "cue": "may_table",
            "text": f"Quvvat to'lganda oyiga {say(net_full, 100_000)} foyda beradi.",
        },
        {"cue": "financing", "text": f"Kreditga olsangiz oyiga {say(loan_m, 100_000)} to'laysiz."},
        {"cue": "approve_button", "text": "Rejani tasdiqlaysizmi?"},
    ]
    md = "\n".join(
        [
            f"**Xulosa: {verdict} {hl}**",
            "",
            "CHIPS: Eski apparat buzilsa-chi? | Kreditga olsam? | Bo'lib to'lasam oyiga qancha?",
        ]
    )
    due = ctx.base.today if not ctx.base.insufficient_data else None
    plan_obj = propose(
        ctx,
        "reminder",
        {"summary": f"{equipment}: jamg'arma + signal kuzatuvi (shanba ≥ 85)", "note": "golden:Q3"},
        (due + timedelta(days=30)) if due else None,
    )
    return envelope(
        ok=True,
        facts={"net_full": S(net_full), "buy": buy, "loan_m": N(loan_m)},
        md=md,
        say=" ".join(x["text"] for x in speech),
        speech_segments=speech,
        speech_short=speech[0]["text"],
        ui_blocks=[report],
        proposed_plan=plan_obj,
        answer={"headline": f"{verdict} {hl}", "reason": ""},
    )


EQUIP = (
    "lavash apparat",
    "lavash stansiya",
    "stansiya",
    "shaurma apparat",
    "fritur",
    "gril",
    "pech",
    "muzlatgich",
    "apparat",
    "jihoz",
    "uskuna",
)


def _q3_params(t: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    e = next((x for x in EQUIP if x in t), None)
    if e:
        out["equipment"] = {
            "lavash apparat": "lavash apparati",
            "lavash stansiya": "lavash apparati",
            "stansiya": "lavash apparati",
            "apparat": "lavash apparati",
        }.get(e, e)
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(mln|million|millionga|mlnga)", t)
    if m:
        out["price"] = int(float(m.group(1).replace(",", ".")) * 1_000_000)
    if re.search(r"buzil|almashtir", t):
        out["reason"] = "almashtirish"
    if re.search(r"bo'lib\s+to'la", t):
        out["financing"] = "installment"
    elif re.search(r"kredit", t):
        out["financing"] = "loan"
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
        "equipment_investment",
        "golden/Q3_lavash_aparat_olsam.md",
        "equipment_investment",
        re.compile(
            r"(apparat|stansiya|fritur|gril|pech|muzlatgich|jihoz|uskuna)\w*.{0,60}(olsam|olmoqchi|olay|sarflasam|arziydi|qoplaydi|investitsiya|zarar|kreditga|bo'lib)|(apparat|stansiya)\w*\s+olganim",
            re.I,
        ),
        _q3_params,
    ),
    Intent(
        "revenue_growth_plan",
        "golden/Q4_daromad_10_foiz_strategiya.md",
        "revenue_growth_plan",
        re.compile(
            r"daromad\w*\s+.*(oshir|ko'paytir)|tushum\w*\s+.*(oshir|ko'paytir)|savdo\w*\s+.*(oshir|ko'paytir)|sotuv\w*\s+.*(oshir|ko'paytir)|o'sish\s+strateg|\bstrategiya|mijoz\w*\s+.*ko'paytir|o'rtacha\s+chek\w*\s+.*oshir|qanday\s+aksiya|millionga\s+chiqish",
            re.I,
        ),
        _q4_params,
    ),
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
        "equipment_investment",
        "Uskuna/apparat (lavash apparati, fritur, gril, pech...) X so'mga olsam investitsiyami yoki zarariga ishlaydimi (golden Q3): bo'sh quvvat, qachon olish, foyda va qoplash, J-egri chiziq, jamg'arma / bo'lib to'lash / kredit.",
        {
            "type": "object",
            "properties": {
                "price": {"type": "integer", "minimum": 100000},
                "equipment": {"type": "string", "maxLength": 60},
                "reason": {
                    "type": "string",
                    "enum": ["quvvat", "almashtirish", "yangi mahsulot", "ish haqi"],
                },
                "financing": {"type": "string", "enum": ["own", "installment", "loan"]},
            },
        },
        equipment_investment_tool,
    ),
    Tool(
        "revenue_growth_plan",
        "Daromadni qisqa muddatda X% (standart 10%) oshirish strategiyasi (golden Q4): 5 ta richag (narx, qo'shimcha sotuv, lanch-set, reklama), tushum va foyda, 8 haftalik reja, dalillar.",
        {
            "type": "object",
            "properties": {
                "target": {"type": "integer", "minimum": 1, "maximum": 100},
                "exclude": {"type": "string", "enum": ["reklama", "narx"]},
            },
        },
        revenue_growth_plan_tool,
    ),
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
