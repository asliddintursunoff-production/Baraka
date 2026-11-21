"""web_price_lookup: equipment / product price in Tashkent from the web (Gemini + Google Search),
plus capacity-based payback advice computed in code (never by the LLM).

Found -> price range, sources, capacity and "at X portions/day it pays back in N months".
Not found -> says so and asks the person for the price.
Never sends business data to the web: only the item name and city.
"""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal
from typing import Any

from google.genai import types

from . import uz_format as uz
from .tools import TOOLS, Tool, ToolContext, envelope, speech_of

log = logging.getLogger(__name__)
MODEL = "gemini-3.5-flash-lite"

PROMPT = """Internetdan qidir: "{item}" narxi Toshkent (O'zbekiston) bozorida, so'mda.
olx.uz, uzum.uz, texnomart.uz, mediapark.uz, prom.uz, telegram do'konlari kabi manbalardan foydalan.
Restoran/kafe uchun mos professional variantni nazarda tut. Agar so'mda topilmasa, USD narxni so'mga 12 100 kurs bilan aylantir.
Faqat JSON qaytar, boshqa matn yozma:
{{"found": true|false, "low": son_so'm, "typical": son_so'm, "high": son_so'm,
 "capacity_per_hour": "masalan: soatiga 15-20 kg kartoshka fri" yoki "",
 "portions_per_hour": son yoki null,
 "variants": [{{"name": "...", "price": son_so'm, "where": "sayt nomi"}}],
 "note": "qisqa izoh o'zbekcha"}}
Topa olmasang: {{"found": false}}."""


def _search(item: str, ctx: ToolContext) -> tuple[dict[str, Any], list[dict[str, str]]]:
    from .budget import generate_sync

    r = generate_sync(
        "web_lookup",
        model=MODEL,
        contents=PROMPT.format(item=item[:120]),
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.1
        ),
        business_id=ctx.business.pk,
    )
    text = (getattr(r, "text", None) or "").strip()
    m = re.search(r"\{.*\}", text, re.S)
    data: dict[str, Any] = {}
    if m:
        try:
            data = json.loads(m.group(0))
        except ValueError:
            data = {}
    sources: list[dict[str, str]] = []
    try:
        gm = r.candidates[0].grounding_metadata
        for ch in (gm.grounding_chunks or [])[:5]:
            if ch.web:
                sources.append({"title": ch.web.title or "", "url": ch.web.uri or ""})
    except (AttributeError, IndexError, TypeError):
        pass
    return data, sources


def M(x: Decimal) -> str:
    from .detail_tools import M as _m

    return _m(x)


def _d(v: Any) -> Decimal | None:
    try:
        x = Decimal(str(v).replace(" ", "").replace(",", "."))
        return x if x > 0 else None
    except Exception:
        return None


def _dish_for(item: str, dish: str | None, menu: dict[str, Any]) -> str | None:
    from .detail_tools import best_name

    names = list(menu)
    if dish:
        return best_name(dish, names)
    low = item.lower()
    if "fritur" in low or "fri" in low:
        return next((n for n in names if "fri" in n.lower()), None)
    if "gril" in low or "grill" in low:
        return next((n for n in names if "burger" in n.lower()), None)
    return None


def web_price_lookup(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    item = str(args["item"]).strip()
    try:
        data, sources = _search(item, ctx)
    except Exception as exc:
        log.warning("web lookup failed: %s", type(exc).__name__)
        data, sources = {}, []
    low, typ, high = _d(data.get("low")), _d(data.get("typical")), _d(data.get("high"))
    typ = typ or low or high
    if not data.get("found") or typ is None:
        md = (
            f"**Internetda Toshkent bo'yicha «{item}» narxini topa olmadim.**\n\n"
            "Narxini o'zingiz ayting (masalan: 15 mln) — qoplanish muddatini, oylik foydani "
            "va kassaga ta'sirini darhol hisoblab beraman.\n\n"
            "CHIPS: 10 mln bo'lsa | 15 mln bo'lsa | 25 mln bo'lsa"
        )
        return envelope(
            ok=True,
            facts={"found": False, "item": item},
            md=md,
            say=md.split("\n\n")[0],
            answer={
                "headline": f"«{item}» narxi internetda topilmadi",
                "reason": "Narxini ayting.",
            },
        )
    facts: dict[str, Any] = {
        "found": True,
        "item": item,
        "price_typical": M(typ),
        "price_low": M(low or typ),
        "price_high": M(high or typ),
        "price_typical_raw": str(typ),
    }
    lines = [
        f"**Toshkentda {item} narxi taxminan {M(typ)} (oralig'i {M(low or typ)} – {M(high or typ)}).**",
        "",
    ]
    variants = [v for v in (data.get("variants") or []) if isinstance(v, dict)][:4]
    if variants:
        lines += ["### Topilgan variantlar", "| Model | Narx | Qayerda |", "|---|---|---|"]
        for v in variants:
            p = _d(v.get("price"))
            lines.append(
                f"| {str(v.get('name', ''))[:60]} | {M(p) if p else '—'} | {str(v.get('where', ''))[:30]} |"
            )
        lines.append("")
    cap = str(data.get("capacity_per_hour") or "").strip()
    pph = _d(data.get("portions_per_hour"))
    if cap:
        facts["capacity"] = cap
        lines += [f"Quvvati: {cap}.", ""]
    # payback by utilisation, all arithmetic here
    from .detail_tools import details_of

    menu = details_of(ctx).get("menu") or {}
    dish = _dish_for(item, args.get("dish"), menu)
    if dish and menu.get(dish):
        d = menu[dish]
        price, cost = _d(d.get("price")), _d(d.get("cost")) or Decimal(0)
        per = (price - cost) if price else None
        if per and per > 0:
            facts["dish"] = dish
            facts["dish_margin"] = M(per)
            cap_day = (pph * 10) if pph else None  # 10 working hours
            levels = [Decimal(20), Decimal(30), Decimal(50)]
            if args.get("extra_units_per_day"):
                levels = [Decimal(int(args["extra_units_per_day"]))]
            lines += [
                "### Qancha sotsangiz o'zini qoplaydi",
                f"«{dish}» bir porsiyasidan {M(per)} foyda qoladi (narx {M(price)} − tannarx {M(cost)}).",
                "",
                "| Qo'shimcha porsiya/kun | Oylik foyda | Qoplanish |",
                "|---|---|---|",
            ]
            for i, u in enumerate(levels):
                month = (u * 30 * per).quantize(Decimal(1))
                months = (typ / month).quantize(Decimal("0.1")) if month else None
                facts[f"case{i}_units"] = str(int(u))
                facts[f"case{i}_profit"] = M(month)
                facts[f"case{i}_months"] = str(months).replace(".", ",") if months else "—"
                lines.append(f"| {int(u)} | {M(month)} | {str(months).replace('.', ',')} oy |")
            lines.append("")
            if cap_day:
                facts["capacity_portions_day"] = str(int(cap_day))
                lines.append(
                    f"Bu uskuna kuniga ~{int(cap_day)} porsiyagacha chiqara oladi (10 soat ishlasa) — "
                    "rejangiz shundan oshmasin."
                )
            sold = d.get("sold") or {}
            if sold:
                from .detail_tools import month_label

                last_m = sorted(sold)[-1]
                n_sold = uz.group_digits(int(Decimal(str(sold[last_m]))))
                facts["dish_sold_last_month"] = n_sold
                lines.append(
                    f"Hozir «{dish}» oyiga {n_sold} porsiya sotilyapti ({month_label(last_m)})."
                )
            lines.append("")
    if sources:
        lines += ["### Manbalar"] + [
            f"- [{s['title'] or s['url']}]({s['url']})" for s in sources[:4]
        ]
        lines.append("")
    if data.get("note"):
        lines.append(f"_{str(data['note'])[:200]}_")
        lines.append("")
    lines.append("Narxlar internetdan olingan taxmin; aniq narxni sotuvchidan so'rang.")
    lines.append("")
    lines.append(
        "CHIPS: Shu narxda kassaga ta'siri | Bo'lib to'lasam-chi? | Kuniga 30 porsiya sotsam"
    )
    md = "\n".join(lines)
    return envelope(
        ok=True,
        speech=speech_of(facts),
        facts=facts,
        md=md,
        say=lines[0].strip("*"),
        sources=sources,
        answer={"headline": lines[0].strip("*"), "reason": "Narx internetdan topildi."},
    )


WEB_TOOLS = [
    Tool(
        "web_price_lookup",
        "Uskuna yoki mahsulot narxini INTERNETDAN topish (Toshkent bozori): narx oralig'i, variantlar, "
        "quvvati, va menyudagi taom foydasi bilan necha porsiyada o'zini qoplashi. Foydalanuvchi "
        "narxni aytmasa, birinchi shu tool'ni chaqir.",
        {
            "type": "object",
            "properties": {
                "item": {
                    "type": "string",
                    "maxLength": 120,
                    "description": "Masalan: fritur, pech, kofemashina",
                },
                "dish": {
                    "type": "string",
                    "maxLength": 80,
                    "description": "Shu uskunada tayyorlanadigan taom (ixtiyoriy)",
                },
                "extra_units_per_day": {"type": "integer", "minimum": 1, "maximum": 10000},
            },
            "required": ["item"],
        },
        web_price_lookup,
    )
]
TOOLS.update({t.name: t for t in WEB_TOOLS})
