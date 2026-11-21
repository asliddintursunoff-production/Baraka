"""Business digest: one compact markdown of the whole business for the chat/Live model.

Built deterministically from the workbook summary + the forecast (no LLM). The model reads it as
context; every number in it comes from Python.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from apps.engine import growth as G
from apps.tenancy.models import Business

from . import uz_format as uz

D0 = Decimal(0)


def _d(x: Any) -> Decimal:
    try:
        return Decimal(str(x))
    except Exception:
        return D0


def M(x: Any) -> str:
    v = _d(x)
    return uz.format_som(v.quantize(Decimal(1))) if abs(v) < 1_000_000 else uz.format_mln(v)


def _mon(m: str) -> str:
    return f"{uz.MONTHS[int(m[5:7]) - 1][:3]} {m[:4]}"


def build(business: Business) -> str:
    """Inside the tenant context."""
    from apps.insights.forecasting import get_forecast
    from apps.integrations.models import DataSource

    out: list[str] = [
        f"# Biznes: {business.name}",
        f"Turi: {business.kind or 'restoran'}; shahar: {business.city or 'Toshkent'}.",
    ]
    src = DataSource.objects.exclude(summary={}).order_by("-last_synced_at").first()
    s: dict[str, Any] = (src.summary or {}) if src else {}
    q = business.data_quality or {}
    if q.get("accuracy"):
        out.append(
            f"Prognoz aniqligi: {q['accuracy'].get('text')}"
            + (" (TAXMINIY)" if q.get("approximate") else "")
        )
    if s.get("first_date"):
        out.append(f"Ma'lumot davri: {s.get('first_date')} – {s.get('last_date')}.")
    # cash + forecast
    try:
        f = get_forecast(business).result
        if not f.insufficient_data:
            today = f.today
            out += [
                "",
                "## Kassa",
                f"Bugungi kassa ({today}): {M(f.close_on(today))}. Xavfsiz chegara: {M(f.safe_min)}.",
                f"60 kun ichida eng past: {M(f.min_balance)} ({f.min_date}).",
            ]
            out.append(
                "Prognoz 60 kun (har 5 kun): "
                + ", ".join(
                    f"{(today + timedelta(days=i)).strftime('%d.%m.%Y')} {M(f.close_on(today + timedelta(days=i)))}"
                    for i in range(0, min(61, f.horizon_days), 5)
                )
            )
            obl = [o for o in f.obligations if today < o.date <= today + timedelta(days=60)][:25]
            if obl:
                out += [
                    "",
                    "## Yaqin 60 kun to'lovlari",
                    "| Sana | To'lov | Summa |",
                    "|---|---|---|",
                ]
                out += [
                    f"| {o.date.strftime('%d.%m.%Y')} | {o.title} | {M(o.amount)} |" for o in obl
                ]
    except Exception:
        pass
    months = s.get("months") or {}
    pl = (s.get("reports") or {}).get("pl") or {}
    if months:
        out += [
            "",
            "## Oylar (pul va foyda)",
            "| Oy | Tushum | Sof foyda | Oy oxiri kassa | Ish haqi to'landi | Ta'minotchilarga |",
            "|---|---|---|---|---|---|",
        ]
        for m in sorted(months):
            v = months[m]
            part = (
                " (to'liq emas)"
                if s.get("last_date")
                and m[:7] == str(s.get("last_date"))[:7]
                and not str(s.get("last_date")).endswith(("-30", "-31", "-28", "-29"))
                else ""
            )
            out.append(
                f"| {_mon(m)}{part} | {M(v.get('revenue'))} | {M((pl.get('sof foyda') or {}).get(m, v.get('net')))} | {M(v.get('cash_end'))} | {M(v.get('payroll_paid'))} | {M(v.get('supplier_payments'))} |"
            )
    if pl:
        keys = [
            k
            for k in (
                "sof tushum",
                "yalpi foyda",
                "food cost sof tushumga",
                "ish haqi",
                "ijara",
                "kommunal xizmatlar",
                "agregator komissiyasi",
                "marketing va reklama",
                "amortizatsiya",
                "foiz xarajatlari",
                "sof foyda",
                "cheklar soni smena",
                "o'rtacha chek so'm",
            )
            if k in pl
        ]
        ms = sorted(m for m in (pl.get("sof tushum") or {}) if _d(pl["sof tushum"][m]) > 0)[-6:]
        if ms:
            out += [
                "",
                "## Foyda-zarar (oxirgi 6 oy)",
                "| Qator | " + " | ".join(_mon(m) for m in ms) + " |",
                "|---|" + "---|" * len(ms),
            ]
            for k in keys:
                row = pl[k]
                vals = [
                    (
                        f"{_d(row.get(m)) * 100:.1f}%".replace(".", ",")
                        if "food cost" in k
                        else M(row.get(m))
                    )
                    for m in ms
                ]
                out.append(f"| {k} | " + " | ".join(vals) + " |")
    if s.get("reports", {}).get("pl"):
        try:
            sc = G.kpi_scorecard(s)
            out += ["", "## KPI (maqsadga nisbatan)"] + [
                f"- {k.label}: {(k.value * 100).quantize(Decimal('0.1')) if k.value is not None and abs(k.value) < 5 else M(k.value)}{'%' if k.value is not None and abs(k.value) < 5 else ''}"
                + (f" (maqsad {(k.target * 100):.0f}%)" if k.target is not None else "")
                + f" — {k.status}"
                for k in sc.kpis
            ]
        except Exception:
            pass
    det = s.get("details") or {}
    menu = det.get("menu") or {}
    if menu:
        lm = G.last_month(s) if s.get("reports", {}).get("pl") else None
        out += [
            "",
            "## Menyu rentabelligi",
            "| Taom | Narx | Tannarx | Porsiya foydasi | Food cost | Sotildi (oxirgi oy) |",
            "|---|---|---|---|---|---|",
        ]
        for n, d in menu.items():
            sold = (d.get("sold") or {}).get(lm, "") if lm else ""
            out.append(
                f"| {n} | {M(d.get('price'))} | {M(d.get('cost'))} | {M(_d(d.get('price')) - _d(d.get('cost')))} | {_d(d.get('food_cost')) * 100:.0f}% | {sold} |"
            )
    pur = det.get("purchases") or {}
    if pur:
        rows = []
        for n, p in pur.items():
            mm = p.get("months") or {}
            ks = sorted(mm)
            if ks:
                rows.append(
                    (
                        n,
                        _d(mm[ks[-1]].get("amount")),
                        _d(mm[ks[0]].get("price")),
                        _d(mm[ks[-1]].get("price")),
                        p.get("unit", ""),
                        ", ".join(list(p.get("suppliers") or {})[:2])
                        if isinstance(p.get("suppliers"), dict)
                        else "",
                    )
                )
        rows.sort(key=lambda r: -r[1])
        out += [
            "",
            "## Xomashyo (oxirgi oy xaridi, narx o'zgarishi)",
            "| Mahsulot | Oxirgi oy xarid | Narx boshida → oxirida | Ta'minotchi |",
            "|---|---|---|---|",
        ]
        out += [
            f"| {r[0]} | {M(r[1])} | {M(r[2])} → {M(r[3])} /{r[4]} | {r[5]} |" for r in rows[:25]
        ]
    pay = det.get("payroll") or {}
    if pay:
        last = sorted(pay)[-1]
        staff = pay[last]
        total = sum((_d(v[3]) for v in staff.values()), D0)
        out += ["", f"## Xodimlar ({_mon(last)}: {len(staff)} kishi, jami xarajat {M(total)})"]
        out += [
            f"- {k}: {v[0]}, {v[1]}, xarajat {M(v[3])}, qo'lga {M(v[4])}"
            for k, v in list(staff.items())[:30]
        ]
    bal = s.get("balances") or []
    if bal:
        out += ["", "## Kontragentlar saldosi (musbat = biz qarzdormiz, manfiy = bizga qarzdor)"]
        out += [
            f"- {b['name']} ({b.get('type', '')}): {M(b['balance'])}"
            for b in sorted(bal, key=lambda b: -abs(_d(b["balance"])))[:25]
        ]
    loan = s.get("loan")
    if loan:
        out += [
            "",
            "## Kredit",
            f"{loan.get('lender')}: qoldiq {M(loan.get('balance'))}, {loan.get('rate_pct')}% yillik, har oy {M(loan.get('principal_monthly'))} asosiy qarz, to'lov kuni {loan.get('pay_day')}, muddat {loan.get('term_months')} oy.",
        ]
    assets = det.get("assets") or {}
    if assets:
        items = (
            assets.items()
            if isinstance(assets, dict)
            else [(a.get("name", "?") if isinstance(a, dict) else str(a), a) for a in assets]
        )
        out += ["", "## Asosiy vositalar"] + [
            f"- {n}: "
            + (
                ", ".join(f"{k}={v}" for k, v in a.items() if k != "name")
                if isinstance(a, dict)
                else str(a)
            )
            for n, a in list(items)[:15]
        ]
    j = s.get("journals") or {}
    wz = j.get("weekday_z") or {}
    if wz:
        out += [
            "",
            "## Hafta kunlari (o'rtacha kunlik savdo)",
            ", ".join(
                f"{uz.WEEKDAYS[int(k)] if hasattr(uz, 'WEEKDAYS') else k}: {M(v)}"
                for k, v in sorted(wz.items())
            ),
        ]
    ch = j.get("checks") or {}
    if ch:
        out.append(
            "Cheklar soni oyma-oy: "
            + ", ".join(f"{_mon(m)} {int(_d(v))}" for m, v in sorted(ch.items()))
        )
    flags = q.get("flags") or []
    if flags:
        out += ["", "## Ogohlantirishlar"] + [f"- {fl.get('text')}" for fl in flags[:8]]
    inv = s.get("inventory") or []
    if inv:
        out += ["", "## Fayldagi varaqlar"] + [
            f"- {i['sheet']}: {i['role_label']}, {i['rows']} qator"
            + (f", {i['from']} – {i['to']}" if i.get("from") else "")
            for i in inv
        ]
    try:
        from .growth_tools import market_facts_text

        out += ["", "## Bozor (Toshkent fast-food, internetdan)", market_facts_text()]
    except Exception:
        pass
    return "\n".join(x for x in out if x is not None)[:120_000]


def digest_for(business: Business) -> str:
    """Cached on the data source summary; rebuilt when the data changed (new sync)."""
    from apps.integrations.models import DataSource

    src = DataSource.objects.exclude(summary={}).order_by("-last_synced_at").first()
    stamp = src.last_synced_at.isoformat() if src and src.last_synced_at else ""
    summ = (src.summary or {}) if src else {}
    if summ.get("digest") and summ.get("digest_stamp") == stamp:
        return str(summ["digest"])
    text = build(business)
    if src:
        src.summary = {**summ, "digest": text, "digest_stamp": stamp}
        src.save(update_fields=["summary"])
    return text
