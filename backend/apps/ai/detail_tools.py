"""Item-level tools over DataSource.summary["details"] (apps/ingestion/finmodel_details.py).

The person asks about a product ("un", "kartoshka", "mol go'shti"), a dish, losses, staff or
stock and gets names, quantities, prices and amounts straight from the workbook, never
"boshqa xarajatlar". Each tool returns facts, a ready Uzbek markdown `md` and captioned cards.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from apps.ingestion.normalize import text_key
from apps.integrations.models import DataSource

from . import uz_format as uz
from .tools import TOOLS, Tool, ToolContext, envelope

D0 = Decimal(0)


def M(x: Decimal) -> str:
    """Amounts under 1 mln in so'm ("152 000 so'm"), larger ones in mln ("48,6 mln")."""
    return uz.format_som(x.quantize(Decimal(1))) if abs(x) < 1_000_000 else uz.format_mln(x)


def S(x: Decimal) -> str:
    return uz.format_som(x.quantize(Decimal(1)))


def P(x: Decimal, digits: str = "0.1") -> str:
    return f"{(x * 100).quantize(Decimal(digits))}%".replace(".", ",")


def Q(x: Decimal) -> str:
    q = x.quantize(Decimal("0.01")).normalize()
    return f"{q:,f}".replace(",", " ").replace(".", ",")


def cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def date_iso(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{uz.format_date(d)} {d.year}"


def month_label(iso: str) -> str:
    y, m = int(iso[:4]), int(iso[5:7])
    return f"{uz.MONTHS[m - 1]} {y}"


def details_of(ctx: ToolContext) -> dict[str, Any]:
    src = DataSource.objects.exclude(summary={}).first()
    return (src.summary or {}).get("details") or {} if src else {}


def missing(what: str) -> dict[str, Any]:
    text = f"Bu ma'lumot ({what}) jadvalingizda yo'q."
    return envelope(
        ok=True,
        md=text,
        say=text,
        answer={"verdict": "info", "headline": text, "reason": "", "steps": []},
    )


def done(
    facts: dict[str, Any], md: str, blocks: list[dict[str, Any]], headline: str
) -> dict[str, Any]:
    return envelope(
        ok=True,
        facts=facts,
        md=md,
        say=headline,
        ui_blocks=blocks,
        answer={
            "verdict": "info",
            "headline": headline[:80],
            "reason": md.split("\n")[0][:300],
            "steps": [],
        },
    )


_SHORT_SUFFIX = r"(?:ga|ni|da|dan|ning|lar|ni)?"


def find_names(text: str, names: list[str]) -> list[str]:
    """Names mentioned in the text (Uzbek case endings allowed: "unga", "kartoshkaning")."""
    t = f" {text_key(text)} "
    found: list[str] = []
    for n in sorted(names, key=len, reverse=True):
        k = text_key(n)
        if not k:
            continue
        pat = (
            rf"\b{re.escape(k)}{_SHORT_SUFFIX}\b"
            if len(k) <= 3
            else rf"\b{re.escape(k)}\w{{0,6}}\b"
        )
        if re.search(pat, t) and not any(k in text_key(f) for f in found):
            found.append(n)
    return found


def best_name(query: str, names: list[str]) -> str | None:
    hit = find_names(query, names)
    if hit:
        return hit[0]
    q = text_key(query)
    return next((n for n in names if q and (q in text_key(n) or text_key(n) in q)), None)


def last_month(months: list[str]) -> str | None:
    return max(months) if months else None


# --- products ---------------------------------------------------------------------------


def _dishes_using(d: dict[str, Any], product: str) -> list[str]:
    semis = [
        y
        for y, e in (d.get("semi_recipes") or {}).items()
        if any(i[0] == product for i in e["items"])
    ]
    out = []
    for dish, items in (d.get("recipes") or {}).items():
        names = {i["ingredient"] for i in items}
        if product in names or names & set(semis):
            out.append(dish)
    return out


def product_costs(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    d = details_of(ctx)
    pur: dict[str, Any] = d.get("purchases") or {}
    if not pur:
        return missing("mahsulot xaridlari")
    name = best_name(str(args.get("product") or ""), list(pur)) if args.get("product") else None
    if args.get("product") and name is None:
        text = (
            f'"{args["product"]}" degan mahsulot jadvalda topilmadi. Bor mahsulotlar: '
            + ", ".join(pur)
            + "."
        )
        return envelope(
            ok=True,
            md=text,
            say=text,
            facts={"products": list(pur)},
            answer={
                "verdict": "info",
                "headline": "Mahsulot topilmadi",
                "reason": text,
                "steps": [],
            },
        )
    if name:
        return _one_product(d, name)
    month = str(args.get("month") or "")[:7]
    months = sorted({m for p in pur.values() for m in p.get("months", {})})
    m = next((x for x in months if x.startswith(month)), None) if month else last_month(months)
    if m is None:
        return missing("shu oy uchun xaridlar")
    first = months[0]
    rows = []
    for n, p in pur.items():
        cur = p["months"].get(m)
        if not cur:
            continue
        f = p["months"].get(first) or next(iter(p["months"].values()))
        change = (
            (Decimal(cur["price"]) - Decimal(f["price"])) / Decimal(f["price"])
            if Decimal(f["price"])
            else D0
        )
        rows.append((n, p, cur, change))
    rows.sort(key=lambda r: -Decimal(r[2]["amount"]))
    total = sum((Decimal(r[2]["amount"]) for r in rows), D0)
    table = "\n".join(
        f"| {n} | {Q(Decimal(c['qty']))} {p['unit']} | {M(Decimal(c['amount']))} | {S(Decimal(c['price']))} | {('+' if ch >= 0 else '')}{P(ch)} |"
        for n, p, c, ch in rows
    )
    risers = sorted(rows, key=lambda r: -r[3])[:3]
    top3 = sum((Decimal(r[2]["amount"]) for r in rows[:3]), D0)
    md = (
        f"**{month_label(m).capitalize()}da mahsulot xaridlari: jami {M(total)}** ({len(rows)} xil mahsulot). "
        f"Eng kattasi: {rows[0][0]} {M(Decimal(rows[0][2]['amount']))}; birinchi 3 tasi xaridlarning {P(top3 / total if total else D0, '1')} qismi.\n\n"
        f"| Mahsulot | Miqdor | Summa | O'rtacha narx | Narx o'zgarishi ({month_label(first)}dan) |\n|---|---|---|---|---|\n{table}\n\n"
        "Narxi eng ko'p oshganlar: "
        + "; ".join(
            f"{n} {S(Decimal(pur[n]['months'][first]['price'] if first in pur[n]['months'] else c['price']))} → {S(Decimal(c['price']))} ({('+' if ch >= 0 else '')}{P(ch)})"
            for n, _, c, ch in risers
        )
        + "."
    )
    facts = {
        "month": m,
        "total": M(total),
        "products": [
            {
                "name": n,
                "qty": f"{Q(Decimal(c['qty']))} {p['unit']}",
                "amount": M(Decimal(c["amount"])),
                "price": S(Decimal(c["price"])),
                "price_change": P(ch),
                "supplier": next(iter(p.get("suppliers", {})), ""),
            }
            for n, p, c, ch in rows
        ],
    }
    blocks = [
        {
            "type": "metric_grid",
            "id": "products",
            "title": f"Mahsulot xaridlari · {month_label(m)}",
            "caption": "Qaysi mahsulotga eng ko'p pul ketyapti va narxi qanchaga o'zgargan.",
            "items": [
                {
                    "label": n,
                    "value": M(Decimal(c["amount"])),
                    "note": f"{Q(Decimal(c['qty']))} {p['unit']} × {S(Decimal(c['price']))}",
                    "tone": "warn" if ch > Decimal("0.1") else "muted",
                }
                for n, p, c, ch in rows[:8]
            ],
        }
    ]
    return done(facts, md, blocks, f"{month_label(m).capitalize()}: mahsulotlarga {M(total)}")


def _one_product(d: dict[str, Any], name: str) -> dict[str, Any]:
    p = d["purchases"][name]
    months = p["months"]
    keys = sorted(months)
    unit = p.get("unit", "")
    table = "\n".join(
        f"| {month_label(m)} | {Q(Decimal(months[m]['qty']))} {unit} | {M(Decimal(months[m]['amount']))} | {S(Decimal(months[m]['price']))} |"
        for m in keys
    )
    first, last = Decimal(months[keys[0]]["price"]), Decimal(months[keys[-1]]["price"])
    change = (last - first) / first if first else D0
    total = sum((Decimal(v["amount"]) for v in months.values()), D0)
    sup = ", ".join(f"{k} {M(Decimal(v))}" for k, v in list(p.get("suppliers", {}).items())[:3])
    dishes = _dishes_using(d, name)
    wo = sum(
        (
            Decimal(i[3])
            for items in (d.get("writeoffs") or {}).get("items", {}).values()
            for i in items
            if i[0] == name
        ),
        D0,
    )
    short = sum(
        (
            Decimal(i[3])
            for items in (d.get("stock_counts") or {}).values()
            for i in items
            if i[0] == name
        ),
        D0,
    )
    st = ((d.get("stock") or {}).get("items") or {}).get(name)
    extra = []
    if wo:
        extra.append(f"hisobdan chiqarilgan (buzilgan va h.k.) jami {M(wo)}")
    if short < 0:
        extra.append(f"inventarizatsiyada kamomad jami {M(-short)}")
    if st:
        extra.append(
            f"omborda {Q(Decimal(st['end_qty']))} {unit} qoldi (min {Q(Decimal(st['min']))}), holati: {st['status']}"
        )
    md = (
        f"**{name}: {month_label(keys[0])} – {month_label(keys[-1])} davomida {M(total)} xarid qilingan.** "
        f"Narxi {S(first)} → {S(last)} ({('+' if change >= 0 else '')}{P(change)}). Yetkazib beruvchi: {sup or '—'}.\n\n"
        f"| Oy | Miqdor | Summa | O'rtacha narx |\n|---|---|---|---|\n{table}\n\n"
        + (f"Qaysi taomlarga ketadi: {', '.join(dishes)}. " if dishes else "")
        + (cap("; ".join(extra)) + "." if extra else "")
    )
    facts = {
        "product": name,
        "unit": unit,
        "total": M(total),
        "price_first": S(first),
        "price_last": S(last),
        "price_change": P(change),
        "months": {
            m: {
                "qty": Q(Decimal(v["qty"])),
                "amount": M(Decimal(v["amount"])),
                "price": S(Decimal(v["price"])),
            }
            for m, v in months.items()
        },
        "suppliers": {k: M(Decimal(v)) for k, v in p.get("suppliers", {}).items()},
        "dishes": dishes,
        "writeoffs": M(wo),
        "shortage": M(-short) if short < 0 else "0",
        "stock": st,
    }
    blocks = [
        {
            "type": "metric_grid",
            "id": "product",
            "title": name,
            "caption": "Oyma-oy qancha olingan va narx qanday o'zgargan.",
            "items": [
                {
                    "label": month_label(m),
                    "value": M(Decimal(months[m]["amount"])),
                    "note": f"{Q(Decimal(months[m]['qty']))} {unit} × {S(Decimal(months[m]['price']))}",
                    "tone": "muted",
                }
                for m in keys[-6:]
            ],
        }
    ]
    return done(
        facts,
        md,
        blocks,
        f"{name}: narx {('+' if change >= 0 else '')}{P(change)}, jami {M(total)}",
    )


# --- menu and dishes ----------------------------------------------------------------------

GROUP = {
    (True, True): "Yulduz — saqlang",
    (True, False): "Mashhur, lekin foydasi past — narx yoki retseptni ko'ring",
    (False, True): "Foydali, lekin kam sotiladi — reklama qiling",
    (False, False): "Zaif — menyudan olishni o'ylang",
}


def _high(v: str) -> bool:
    return text_key(v).startswith("yuq")


def menu_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    d = details_of(ctx)
    ma = (d.get("menu_analysis") or {}).get("dishes") or {}
    menu = d.get("menu") or {}
    if not ma and not menu:
        return missing("menyu va taomlar")
    names = list(menu) or list(ma)
    dish = best_name(str(args.get("dish") or ""), names) if args.get("dish") else None
    if dish:
        return _one_dish(d, dish)
    period = d["menu_analysis"].get("from"), d["menu_analysis"].get("to")
    rows = sorted(ma.items(), key=lambda kv: -Decimal(kv[1]["gross_profit"]))
    table = "\n".join(
        f"| {n} | {Q(Decimal(v['sold']))} | {M(Decimal(v['revenue']))} | {P(Decimal(v['food_cost']))} | {S(Decimal(v['portion_profit']))} | {GROUP[(_high(v['popularity']), _high(v['margin_class']))]} |"
        for n, v in rows
    )
    worst_fc = max(ma.items(), key=lambda kv: Decimal(kv[1]["food_cost"]))
    total_rev = sum((Decimal(v["revenue"]) for v in ma.values()), D0)
    total_gp = sum((Decimal(v["gross_profit"]) for v in ma.values()), D0)
    when = f"{date_iso(period[0])} – {date_iso(period[1])}" if period[0] and period[1] else ""
    md = (
        f"**Menyu tahlili ({when}): {len(ma)} taom, tushum {M(total_rev)}, yalpi foyda {M(total_gp)}.** "
        f"Eng foydalisi — {rows[0][0]} ({M(Decimal(rows[0][1]['gross_profit']))}); food cost eng yuqori — {worst_fc[0]} ({P(Decimal(worst_fc[1]['food_cost']))}).\n\n"
        f"| Taom | Sotildi (porsiya) | Tushum | Food cost | 1 porsiya foydasi | Guruh |\n|---|---|---|---|---|---|\n{table}"
    )
    facts = {
        "period": when,
        "dishes": {
            n: {
                "sold": Q(Decimal(v["sold"])),
                "revenue": M(Decimal(v["revenue"])),
                "food_cost": P(Decimal(v["food_cost"])),
                "portion_profit": S(Decimal(v["portion_profit"])),
                "gross_profit": M(Decimal(v["gross_profit"])),
                "group": GROUP[(_high(v["popularity"]), _high(v["margin_class"]))],
            }
            for n, v in rows
        },
    }
    blocks = [
        {
            "type": "scenario_table",
            "id": "menu",
            "title": f"Menyu tahlili · {when}",
            "caption": "Qaysi taom ko'p foyda beradi, qaysi biri food cost'ni oshiryapti.",
            "columns": ["Sotildi", "Food cost", "Porsiya foydasi"],
            "rows": [
                {
                    "label": n,
                    "values": [
                        Q(Decimal(v["sold"])),
                        P(Decimal(v["food_cost"])),
                        S(Decimal(v["portion_profit"])),
                    ],
                }
                for n, v in rows
            ],
        }
    ]
    return done(facts, md, blocks, f"Eng foydali taom: {rows[0][0]}")


def _one_dish(d: dict[str, Any], dish: str) -> dict[str, Any]:
    mn = (d.get("menu") or {}).get(dish) or {}
    ma = ((d.get("menu_analysis") or {}).get("dishes") or {}).get(dish) or {}
    rec = (d.get("recipes") or {}).get(dish) or []
    price, cost = Decimal(mn.get("price") or 0), Decimal(mn.get("cost") or 0)
    cb = mn.get("cost_by_month") or {}
    ck = sorted(cb)
    trend = (
        f" 1 porsiya tannarxi {month_label(ck[0])}da {S(Decimal(cb[ck[0]]))} edi, {month_label(ck[-1])}da {S(Decimal(cb[ck[-1]]))}."
        if len(ck) > 1
        else ""
    )
    rec_sorted = sorted(rec, key=lambda i: -Decimal(i["cost"]))
    rtable = "\n".join(
        f"| {i['ingredient']} | {Q(Decimal(i['qty']))} {i['unit']} | {S(Decimal(i['cost']))} | {P(Decimal(i['cost']) / cost if cost else D0, '1')} |"
        for i in rec_sorted
    )
    sold = mn.get("sold") or {}
    sk = sorted(sold)[-3:]
    md = (
        f"**{dish}: narxi {S(price)}, 1 porsiya tannarxi {S(cost)}, food cost {P(Decimal(mn.get('food_cost') or 0))}, porsiyadan foyda {S(Decimal(mn.get('margin') or 0))}.**{trend}\n\n"
        f"| Ingredient | 1 porsiyaga | Tannarx | Ulushi |\n|---|---|---|---|\n{rtable}\n\n"
        + (
            "Sotuv: "
            + ", ".join(f"{month_label(m)} {Q(Decimal(sold[m]))} porsiya" for m in sk)
            + ". "
            if sk
            else ""
        )
        + (f"Guruhi: {GROUP[(_high(ma['popularity']), _high(ma['margin_class']))]}." if ma else "")
    )
    facts = {
        "dish": dish,
        "price": S(price),
        "cost": S(cost),
        "food_cost": P(Decimal(mn.get("food_cost") or 0)),
        "margin": S(Decimal(mn.get("margin") or 0)),
        "recipe": [
            {
                "ingredient": i["ingredient"],
                "qty": f"{Q(Decimal(i['qty']))} {i['unit']}",
                "cost": S(Decimal(i["cost"])),
            }
            for i in rec_sorted
        ],
        "cost_by_month": {m: S(Decimal(v)) for m, v in cb.items()},
        "sold": {m: Q(Decimal(v)) for m, v in sold.items()},
    }
    blocks = [
        {
            "type": "metric_grid",
            "id": "dish",
            "title": dish,
            "caption": "1 porsiya tannarxi qaysi ingredientdan yig'iladi.",
            "items": [
                {
                    "label": i["ingredient"],
                    "value": S(Decimal(i["cost"])),
                    "note": f"{Q(Decimal(i['qty']))} {i['unit']}",
                    "tone": "muted",
                }
                for i in rec_sorted[:8]
            ],
        }
    ]
    return done(facts, md, blocks, f"{dish}: food cost {P(Decimal(mn.get('food_cost') or 0))}")


# --- losses, staff, stock, assets ---------------------------------------------------------------


def losses_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    d = details_of(ctx)
    wo, sc = d.get("writeoffs") or {}, d.get("stock_counts") or {}
    if not wo and not sc:
        return missing("hisobdan chiqarish va inventarizatsiya")
    months = sorted(set(wo.get("months", {})) | set(sc))
    want = str(args.get("month") or "")[:7]
    m = next((x for x in months if x.startswith(want)), None) if want else months[-1]
    if m is None:
        return missing("shu oy uchun yo'qotishlar")
    reasons = {k: Decimal(v) for k, v in wo.get("months", {}).get(m, {}).items()}
    items = sorted(wo.get("items", {}).get(m, []), key=lambda i: -Decimal(i[3]))
    short = sorted((i for i in sc.get(m, []) if Decimal(i[3]) < 0), key=lambda i: Decimal(i[3]))
    short_total = -sum((Decimal(i[3]) for i in short), D0)
    year_wo = sum((Decimal(v) for rs in wo.get("months", {}).values() for v in rs.values()), D0)
    year_short = -sum((Decimal(i[3]) for its in sc.values() for i in its if Decimal(i[3]) < 0), D0)
    md = (
        f"**{month_label(m).capitalize()}: hisobdan chiqarish {M(sum(reasons.values(), D0))}, inventarizatsiya kamomadi {M(short_total)}.** "
        f"Yil boshidan jami: hisobdan chiqarish {M(year_wo)}, kamomad {M(year_short)}.\n\n"
        + (
            "Sabablar: "
            + "; ".join(f"{k} {M(v)}" for k, v in sorted(reasons.items(), key=lambda kv: -kv[1]))
            + ".\n\n"
            if reasons
            else ""
        )
        + (
            "| Hisobdan chiqarilgan | Miqdor | Summa | Sabab |\n|---|---|---|---|\n"
            + "\n".join(
                f"| {i[0]} | {Q(Decimal(i[1]))} {i[2]} | {M(Decimal(i[3]))} | {i[4]} |"
                for i in items[:8]
            )
            + "\n\n"
            if items
            else ""
        )
        + (
            "| Kamomad (sanoqda yo'q) | Miqdor | Summa |\n|---|---|---|\n"
            + "\n".join(
                f"| {i[0]} | {Q(-Decimal(i[1]))} {i[2]} | {M(-Decimal(i[3]))} |" for i in short[:8]
            )
            if short
            else ""
        )
    )
    facts = {
        "month": m,
        "writeoffs": {k: M(v) for k, v in reasons.items()},
        "shortage_total": M(short_total),
        "shortages": [
            {"name": i[0], "qty": f"{Q(-Decimal(i[1]))} {i[2]}", "amount": M(-Decimal(i[3]))}
            for i in short[:10]
        ],
        "year_writeoffs": M(year_wo),
        "year_shortage": M(year_short),
    }
    blocks = [
        {
            "type": "metric_grid",
            "id": "losses",
            "title": f"Yo'qotishlar · {month_label(m)}",
            "caption": "Buzilgan, bepul berilgan va sanoqda chiqmagan mahsulotlar.",
            "items": [
                {
                    "label": i[0],
                    "value": M(-Decimal(i[3])),
                    "note": f"kamomad {Q(-Decimal(i[1]))} {i[2]}",
                    "tone": "warn",
                }
                for i in short[:6]
            ],
        }
    ]
    return done(facts, md, blocks, f"Kamomad {M(short_total)}")


def staff_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    pay = details_of(ctx).get("payroll") or {}
    if not pay:
        return missing("xodimlar ish haqi")
    want = str(args.get("month") or "")[:7]
    m = next((x for x in sorted(pay) if x.startswith(want)), None) if want else max(pay)
    if m is None:
        return missing("shu oy uchun ish haqi")
    rows = sorted(pay[m].items(), key=lambda kv: -Decimal(kv[1][3]))
    deps: dict[str, Decimal] = {}
    for _, v in rows:
        deps[v[1] or "—"] = deps.get(v[1] or "—", D0) + Decimal(v[3])
    total = sum(deps.values(), D0)
    md = (
        f"**{month_label(m).capitalize()}: {len(rows)} xodim, ish haqi xarajati jami {M(total)}** (soliqlar bilan). "
        "Bo'limlar: "
        + ", ".join(f"{k} {M(v)}" for k, v in sorted(deps.items(), key=lambda kv: -kv[1]))
        + ".\n\n"
        "| Xodim | Lavozim | Bo'lim | Hisoblangan | Jami xarajat |\n|---|---|---|---|---|\n"
        + "\n".join(
            f"| {n} | {v[0]} | {v[1]} | {M(Decimal(v[2]))} | {M(Decimal(v[3]))} |" for n, v in rows
        )
    )
    facts = {
        "month": m,
        "total": M(total),
        "departments": {k: M(v) for k, v in deps.items()},
        "staff": [
            {
                "name": n,
                "position": v[0],
                "department": v[1],
                "accrued": M(Decimal(v[2])),
                "total": M(Decimal(v[3])),
            }
            for n, v in rows
        ],
    }
    return done(facts, md, [], f"Ish haqi {M(total)}, {len(rows)} xodim")


def stock_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    st = details_of(ctx).get("stock") or {}
    items = st.get("items") or {}
    if not items:
        return missing("ombor qoldig'i")
    low = [(n, v) for n, v in items.items() if text_key(v["status"]) != "ok"]
    value = sum((Decimal(v["value"]) for v in items.values()), D0)
    md = f"**Ombor ({st.get('month', '')}): {len(items)} mahsulot, qiymati {M(value)}.** " + (
        f"Buyurtma kerak: {len(low)} ta.\n\n| Mahsulot | Qoldiq | Min | Oylik sarf | Holat |\n|---|---|---|---|---|\n"
        + "\n".join(
            f"| {n} | {Q(Decimal(v['end_qty']))} {v['unit']} | {Q(Decimal(v['min']))} | {Q(Decimal(v['used']))} | {v['status']} |"
            for n, v in low
        )
        if low
        else "Hamma mahsulot minimal zaxiradan yuqori."
    )
    facts = {
        "month": st.get("month"),
        "value": M(value),
        "to_order": [
            {"name": n, "qty": f"{Q(Decimal(v['end_qty']))} {v['unit']}", "min": v["min"]}
            for n, v in low
        ],
    }
    return done(facts, md, [], f"Buyurtma kerak: {len(low)} ta mahsulot")


def assets_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    a = details_of(ctx).get("assets") or []
    if not a:
        return missing("asosiy vositalar")
    total = sum((Decimal(x["value"]) for x in a), D0)
    depr = sum((Decimal(x["monthly_depr"]) for x in a), D0)
    md = (
        f"**Asosiy vositalar: {len(a)} ta, qiymati {M(total)}, oylik amortizatsiya {M(depr)}.**\n\n"
        "| Nomi | Sana | Qiymati | Muddat (oy) | Oylik amortizatsiya |\n|---|---|---|---|---|\n"
        + "\n".join(
            f"| {x['name']} | {date_iso(x['date']) if x['date'] else '—'} | {M(Decimal(x['value']))} | {Q(Decimal(x['life_months']))} | {M(Decimal(x['monthly_depr']))} |"
            for x in a
        )
    )
    facts = {
        "total": M(total),
        "monthly_depr": M(depr),
        "assets": [
            {"name": x["name"], "value": M(Decimal(x["value"])), "date": x["date"]} for x in a
        ],
    }
    return done(facts, md, [], f"Asosiy vositalar {M(total)}")


def products_for_month(ctx: ToolContext, month_iso: str, n: int = 10) -> list[dict[str, str]]:
    """Top purchased products for get_expenses (product names instead of "food")."""
    pur = details_of(ctx).get("purchases") or {}
    rows = [
        (k, v["months"][month_iso], v.get("unit", ""))
        for k, v in pur.items()
        if month_iso in v.get("months", {})
    ]
    rows.sort(key=lambda r: -Decimal(r[1]["amount"]))
    return [
        {
            "name": k,
            "qty": f"{Q(Decimal(c['qty']))} {u}",
            "amount": M(Decimal(c["amount"])),
            "price": S(Decimal(c["price"])),
        }
        for k, c, u in rows[:n]
    ]


OPT = {"type": "string"}
DETAIL_TOOLS: list[Tool] = [
    Tool(
        "product_costs",
        "Mahsulot xaridlari nomma-nom (un, kartoshka, go'sht, yog'...): miqdor, summa, o'rtacha narx, narx o'zgarishi, yetkazib beruvchi, qaysi taomga ketadi, isrof va kamomad. product bo'lmasa — oy bo'yicha hamma mahsulotlar.",
        {
            "type": "object",
            "properties": {"product": OPT, "month": {"type": "string", "format": "date"}},
        },
        product_costs,
    ),
    Tool(
        "menu_analysis",
        "Taomlar: sotilgan porsiya, tushum, food cost, porsiya foydasi, guruh (yulduz/zaif). dish berilsa — narx, 1 porsiya tannarxi, retsept (ingredientlar narxi bilan), tannarx o'zgarishi.",
        {"type": "object", "properties": {"dish": OPT}},
        menu_tool,
    ),
    Tool(
        "losses",
        "Yo'qotishlar: hisobdan chiqarish (buzilgan, xodimlar ovqati, bepul) va inventarizatsiya kamomadi nomma-nom.",
        {"type": "object", "properties": {"month": {"type": "string", "format": "date"}}},
        losses_tool,
    ),
    Tool(
        "staff_costs",
        "Xodimlar: har bir xodim, lavozim, bo'lim, hisoblangan ish haqi va jami xarajat; bo'limlar bo'yicha jami.",
        {"type": "object", "properties": {"month": {"type": "string", "format": "date"}}},
        staff_tool,
    ),
    Tool(
        "stock_status",
        "Ombor qoldig'i: qaysi mahsulotni buyurtma qilish kerak, qiymati.",
        {"type": "object", "properties": {}},
        stock_tool,
    ),
    Tool(
        "fixed_assets",
        "Asosiy vositalar (jihozlar, mebel, ta'mir): qiymati, sanasi, amortizatsiya.",
        {"type": "object", "properties": {}},
        assets_tool,
    ),
]

TOOLS.update({t.name: t for t in DETAIL_TOOLS})
