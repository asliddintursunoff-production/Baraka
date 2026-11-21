"""Answer policy tools: never stop at "ma'lumot yo'q" — look up any entity in the normalized tables,
and compute salary what-ifs on the P&L + cash. Every number from Python."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from apps.engine import growth as G

from . import uz_format as uz
from .growth_tools import M, _fc, _summary
from .tools import TOOLS, Tool, ToolContext, envelope, speech_of

D0 = Decimal(0)
ROLE_WORDS = {
    "oshpaz": ("oshpaz", "lavash usta", "fritur", "burger", "povar"),
    "kassir": ("kassir",),
    "kuryer": ("kuryer",),
    "menejer": ("menejer", "boshqaruvchi"),
    "farrosh": ("farrosh",),
    "yordamchi": ("yordamchi",),
    "ofitsiant": ("ofitsiant",),
}
SALARY = re.compile(r"oylik|oylig|ish\s*haqi|maosh|oklad|zarplat", re.I)


def _D(x: Any) -> Decimal:
    try:
        return Decimal(str(x))
    except Exception:
        return D0


def role_in(text: str) -> str | None:
    t = text.lower()
    if re.search(r"\bxodim|\bishchi|hamma|barcha", t) and not any(
        w in t for ws in ROLE_WORDS.values() for w in ws
    ):
        return "hamma"
    for role, words in ROLE_WORDS.items():
        if any(w in t for w in words):
            return role
    return None


def staff_rows(
    s: dict[str, Any], role: str, month: str | None = None
) -> tuple[str, list[dict[str, Any]]]:
    pay = (s.get("details") or {}).get("payroll") or {}
    m = month or G.last_month(s)
    if m not in pay and pay:
        m = sorted(k for k in pay if k <= m)[-1] if any(k <= m for k in pay) else sorted(pay)[-1]
    out = []
    for name, v in (pay.get(m) or {}).items():
        blob = f"{name} {v[0]}".lower()
        if role != "hamma" and not any(w in blob for w in ROLE_WORDS.get(role, (role,))):
            continue
        brutto, total = _D(v[2]), _D(v[3])
        out.append(
            {
                "name": name,
                "position": v[0],
                "dept": v[1],
                "brutto": brutto,
                "total": total,
                "social": max(D0, total - brutto),
                "net": _D(v[4]),
                "oklad": _D(v[5]) if len(v) > 5 else brutto,
                "official": (str(v[6]).lower().startswith("ha") if len(v) > 6 else total > brutto),
            }
        )
    return m, out


def _mon(m: str) -> str:
    return f"{uz.MONTHS[int(m[5:7]) - 1]} {m[:4]}"


def lookup_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Generic lookup over the normalized tables (staff, menu, products, counterparties)."""
    s = _summary() or {}
    ent = str(args.get("entity") or "").strip()
    role = role_in(ent) or ("hamma" if SALARY.search(ent) else None)
    det = s.get("details") or {}
    if role:
        m, rows = staff_rows(s, role)
        if rows:
            tot = sum((r["brutto"] for r in rows), D0)
            head = f"**{_mon(m)}: {len(rows)} ta {'xodim' if role == 'hamma' else role} — oklad jami {M(sum((r['oklad'] for r in rows), D0))}, hisoblangan (brutto) {M(tot)}.**"
            lines = [
                head,
                "",
                "| Xodim | Lavozim | Oklad | Hisoblangan (brutto) | Ijtimoiy soliq | Jami xarajat | Rasmiy |",
                "|---|---|---:|---:|---:|---:|---|",
            ]
            for r in sorted(rows, key=lambda r: -r["oklad"]):
                lines.append(
                    f"| {r['name']} | {r['position']} | {uz.group_digits(int(r['oklad']))} | {uz.group_digits(int(r['brutto']))} | {uz.group_digits(int(r['social']))} | {uz.group_digits(int(r['total']))} | {'Ha' if r['official'] else 'Yo‘q'} |"
                )
            lines += [
                "",
                f"_Manba: Ish haqi varag'i ({_mon(m)}); brutto — ishlagan kunlarga qarab._",
                "",
                "CHIPS: Oyligini 20% oshirsam? | Yana bitta oshpaz olsam? | Xodimlar xarajati foydaga nisbatan",
            ]
            facts = {f"oklad_{r['name']}": M(r["oklad"]) for r in rows} | {"total_brutto": M(tot)}
            return envelope(
                ok=True,
                facts=facts,
                speech=speech_of(facts),
                md="\n".join(lines),
                say=head.strip("*"),
                answer={"headline": head.strip("*"), "reason": ""},
            )
    for kind, table in (("taom", det.get("menu") or {}), ("mahsulot", det.get("purchases") or {})):
        hit = next(
            (n for n in table if ent and (ent.lower() in n.lower() or n.lower() in ent.lower())),
            None,
        )
        if hit:
            d = table[hit]
            md = (
                f"**{hit}** ({kind}): "
                + ", ".join(f"{k}: {v}" for k, v in d.items() if isinstance(v, (str, int, float)))[
                    :600
                ]
            )
            return envelope(
                ok=True,
                facts={"entity": hit},
                md=md,
                say=md.replace("**", ""),
                answer={"headline": hit, "reason": ""},
            )
    for b in det.get("counterparties") or []:
        if ent and ent.lower() in b["name"].lower():
            md = f"**{b['name']}** ({b.get('type', '')}): saldo {M(_D(b['balance']))} (musbat — biz qarzdormiz, manfiy — bizga qarzdor)."
            return envelope(
                ok=True,
                facts={"entity": b["name"]},
                md=md,
                say=md.replace("**", ""),
                answer={"headline": b["name"], "reason": ""},
            )
    md = (
        f"«{ent}» bo'yicha aniq qator topmadim (Ish haqi, Menyu, Kirim, Kontragentlar varaqlarida qidirdim). Eng yaqin ma'lumot: "
        f"{', '.join(list(det.get('menu') or {})[:3]) or '—'}. Nomini aniqroq yozing yoki varaqqa qo'shing — darhol hisoblayman."
    )
    return envelope(
        ok=True, facts={}, md=md, say=md, answer={"headline": md.split(".")[0], "reason": ""}
    )


def salary_change_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = _summary() or {}
    role = str(args.get("role") or "hamma")
    m, rows = staff_rows(s, role)
    if not rows:
        return lookup_tool(ctx, {"entity": role})
    factor = Decimal(str(args["factor"])) if args.get("factor") else None
    pct = Decimal(str(args["pct"])) / 100 if args.get("pct") is not None else None
    add = Decimal(str(args["amount"])) if args.get("amount") else None
    base_cost = sum((r["brutto"] + r["social"] for r in rows), D0)
    brutto = sum((r["brutto"] for r in rows), D0)
    social = sum((r["social"] for r in rows), D0)
    if factor is not None:
        k, label = factor - 1, f"{str(factor.normalize()).replace('.', ',')} barobar"
    elif pct is not None:
        k, label = pct, f"+{str((pct * 100).normalize()).replace('.', ',')}%"
    elif add is not None:
        k, label = (add * len(rows)) / brutto if brutto else D0, f"+{M(add)} har biriga"
    else:
        k, label = Decimal("0.2"), "+20%"
    extra = (base_cost * k).quantize(Decimal(1))
    lm = G.last_month(s)
    net = G.pl_value(s, "sof foyda", lm)
    new_net = net - extra
    cash, _fmin, _fd, _safe = _fc(ctx)
    runway = (cash / -new_net).quantize(Decimal("0.1"), ROUND_HALF_UP) if new_net < 0 else None
    alt20 = (base_cost * Decimal("0.2")).quantize(Decimal(1))
    bad = new_net < 0 or extra > net * Decimal("0.5")
    who = "xodimlar" if role == "hamma" else f"{role}lar"
    verdict = (
        (
            f"Qilmang: {who} oyligini {label} oshirsangiz, xarajat oyiga +{M(extra)} oshadi va sof foyda {M(net)} dan {M(new_net)} ga tushadi"
            + (
                f" — kassadagi {M(cash)} ~{str(runway).replace('.', ',')} oyga yetadi."
                if runway
                else "."
            )
        )
        if bad
        else (
            f"Mumkin: {who} oyligini {label} oshirish oyiga +{M(extra)} turadi, sof foyda {M(net)} → {M(new_net)}."
        )
    )
    lines = [
        f"**{verdict}**",
        "",
        f"### Hisob ({_mon(m)} oyligi asosida)",
        "| | So'm / oy |",
        "|---|---:|",
        f"| {len(rows)} ta {role if role != 'hamma' else 'xodim'}: brutto | {uz.group_digits(int(brutto))} |",
        f"| Ijtimoiy soliq (rasmiylar, 12%) | {uz.group_digits(int(social))} |",
        f"| Hozirgi jami xarajat | {uz.group_digits(int(base_cost))} |",
        f"| **Qo'shimcha xarajat ({label})** | **+{uz.group_digits(int(extra))}** |",
        f"| Sof foyda ({_mon(lm)}) | {uz.group_digits(int(net))} → **{uz.group_digits(int(new_net))}** |",
    ]
    if runway:
        lines.append(f"| Kassa ({M(cash)}) yetadi | ~{str(runway).replace('.', ',')} oy |")
    lines += [
        "",
        "### Alternativalar",
        f"1. **+20% oshirish:** oyiga +{M(alt20)}, sof foyda ~{M(net - alt20)} — xodimlar mamnun, biznes xavfsiz.",
        "2. **KPI bonus:** oylikni emas, natijani to'lang — savdo rejasi bajarilsa yoki tayyorlash vaqti ≤ 7 daqiqa bo'lsa, oylikning 10–15% i bonus (bonus faqat qo'shimcha foydadan chiqadi).",
        "",
        f"_Manba: Ish haqi ({_mon(m)}), Foyda-zarar ({_mon(lm)}), kassa prognozi._",
        "",
        "CHIPS: 20% oshirsam? | KPI bonus qanday? | Oshpazlar qancha oylik oladi?",
    ]
    facts = {
        "extra": M(extra),
        "net": M(net),
        "new_net": M(new_net),
        "brutto": M(brutto),
        "social": M(social),
        "alt20": M(alt20),
    }
    if runway:
        facts["runway"] = str(runway)
    return envelope(
        ok=True,
        facts=facts,
        speech=speech_of(facts),
        md="\n".join(lines),
        say=verdict,
        answer={"headline": verdict, "reason": ""},
    )


POLICY_TOOLS = [
    Tool(
        "lookup",
        "Istalgan ma'lumotni topish: xodim/lavozim oyligi (oshpaz, kassir, kuryer...), taom, mahsulot, kontragent — barcha varaqlardan.",
        {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "maxLength": 80},
                "field": {"type": "string", "maxLength": 40},
                "period": {"type": "string", "maxLength": 20},
            },
            "required": ["entity"],
        },
        lookup_tool,
    ),
    Tool(
        "salary_change",
        "Oylikni o'zgartirish what-if: lavozim (oshpaz/kassir/hamma), N barobar yoki % yoki + so'm — qo'shimcha xarajat, sof foyda, kassa necha oyga yetadi, verdikt, 2 alternativa.",
        {
            "type": "object",
            "properties": {
                "role": {"type": "string", "maxLength": 30},
                "factor": {"type": "number"},
                "pct": {"type": "number"},
                "amount": {"type": "integer"},
            },
        },
        salary_change_tool,
    ),
]
TOOLS.update({t.name: t for t in POLICY_TOOLS})


def policy_route(text: str) -> list[tuple[str, dict[str, Any]]]:
    t = re.sub(r"[‘’ʻʼ`]", "'", text).lower()
    if not SALARY.search(t):
        return []
    role = role_in(t) or "hamma"
    if re.search(r"oshir|ko'tar|barobar|kamaytir|qo'sh|%", t):
        args: dict[str, Any] = {"role": role}
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(barobar|marta|baravar)", t) or re.search(
            r"(ikki|uch|to'rt|besh)\s*(barobar|marta|baravar)", t
        )
        if m:
            words = {"ikki": 2, "uch": 3, "to'rt": 4, "besh": 5}
            args["factor"] = words.get(m.group(1)) or float(m.group(1).replace(",", "."))
        elif mp := re.search(r"(\d{1,3})\s*%", t):
            args["pct"] = int(mp.group(1))
        elif ma := re.search(r"(\d+(?:[.,]\d+)?)\s*(mln|ming)", t):
            args["amount"] = int(
                float(ma.group(1).replace(",", ".")) * (1_000_000 if ma.group(2) == "mln" else 1000)
            )
        return [("salary_change", args)]
    return [("lookup", {"entity": role})]
