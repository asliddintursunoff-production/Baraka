"""Owner questions with proof: profitability + top dishes, promotion targets, supplier debts,
equipment timing/payment check, hiring payback, where to put extra money. Numbers in code only."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from apps.engine import growth as G

from . import uz_format as uz
from .growth_tools import Dt, M, P, _fc, _no_data, _summary
from .tools import TOOLS, Tool, ToolContext, envelope, speech_of

D0 = Decimal(0)


def _D(x: Any) -> Decimal:
    try:
        return Decimal(str(x))
    except Exception:
        return D0


def _mon(m: str) -> str:
    return f"{uz.MONTHS[int(m[5:7]) - 1]} {m[:4]}"


def _done(
    facts: dict[str, Any], lines: list[str], head: str, blocks: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    md = "\n".join(lines)
    return envelope(
        ok=True,
        facts=facts,
        speech=speech_of(facts),
        md=md,
        say=head.strip("*"),
        ui_blocks=blocks or [],
        answer={"headline": head.strip("*"), "reason": ""},
    )


# 1. profitability for N months + top dishes raising / lowering it --------------------------
def profitability_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = _summary()
    if s is None:
        return _no_data()
    n = int(args.get("months") or 4)
    months = G._months(s)[-n:]
    rev = {m: G.pl_value(s, "sof tushum", m) for m in months}
    net = {m: G.pl_value(s, "sof foyda", m) for m in months}
    gp = {m: G.pl_value(s, "yalpi foyda", m) for m in months}
    tr, tn = sum(rev.values(), D0), sum(net.values(), D0)
    head = f"**{_mon(months[0])} – {_mon(months[-1])} ({n} oy): tushum {M(tr)}, sof foyda {M(tn)}, rentabellik {P(tn / tr if tr else D0)}.**"
    lines = [
        head,
        "",
        "### Oyma-oy (isbot: Foyda-zarar varag'i)",
        "| Oy | Tushum | Yalpi foyda | Sof foyda | Sof marja |",
        "|---|---|---|---|---|",
    ]
    facts: dict[str, Any] = {"revenue": M(tr), "net": M(tn), "margin": P(tn / tr if tr else D0)}
    for m in months:
        lines.append(
            f"| {_mon(m)} | {M(rev[m])} | {M(gp[m])} | {M(net[m])} | {P(net[m] / rev[m] if rev[m] else D0)} |"
        )
        facts[f"net_{m}"], facts[f"rev_{m}"], facts[f"gp_{m}"] = M(net[m]), M(rev[m]), M(gp[m])
    ds = s.get("details", {}).get("dish_sales", {}) or {}
    rows = []
    for name, d in ds.items():
        mm = d.get("months") or {}
        q = sum((_D(mm.get(m, {}).get("qty")) for m in months), D0)
        r = sum((_D(mm.get(m, {}).get("revenue")) for m in months), D0)
        g = sum((_D(mm.get(m, {}).get("gross_profit")) for m in months), D0)
        if r:
            rows.append((name, q, r, g, g / r))
    total_g = sum((x[3] for x in rows), D0)
    top = sorted(rows, key=lambda x: -x[3])[:10]
    low = sorted(rows, key=lambda x: x[4])[:10]
    lines += [
        "",
        f"### Rentabellikni OSHIRAYOTGAN top {len(top)} (yalpi foyda bo'yicha; isbot: Sotuv + Texkarta)",
        "| # | Taom | Sotildi | Tushum | Yalpi foyda | Marja | Foydadagi ulushi |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, x in enumerate(top, 1):
        lines.append(
            f"| {i} | {x[0]} | {uz.group_digits(int(x[1]))} | {M(x[2])} | {M(x[3])} | {P(x[4])} | {P(x[3] / total_g if total_g else D0)} |"
        )
        facts[f"top_{x[0]}"] = M(x[3])
    lines += [
        "",
        f"### Rentabellikni PASAYTIRAYOTGAN top {len(low)} (marja eng past)",
        "| # | Taom | Marja | Yalpi foyda | Muammo |",
        "|---|---|---|---|---|",
    ]
    for i, x in enumerate(low, 1):
        why = (
            "food cost juda yuqori"
            if x[4] < Decimal("0.4")
            else ("marja o'rtachadan past" if x[4] < Decimal("0.6") else "yaxshi")
        )
        lines.append(f"| {i} | {x[0]} | {P(x[4])} | {M(x[3])} | {why} |")
        facts[f"low_{x[0]}"] = P(x[4])
    lines += [
        "",
        "### Guideline",
        "- Marjasi 40% dan past taomlar: narxni oshiring yoki retseptni (porsiya grammi) qayta ko'ring.",
        "- Top-3 foyda keltiruvchi taomlarni menyuda birinchi o'ringa, kombo setlarga qo'ying.",
        "",
        "CHIPS: Qaysi taomni reklama qilay? | Foydani qanday oshiraman? | Food cost nega yuqori?",
    ]
    return _done(facts, lines, head)


# 2. which items to promote and how much to reach a target ----------------------------------
def promote_target_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = _summary()
    if s is None:
        return _no_data()
    m = G.last_month(s)
    rev, net = G.pl_value(s, "sof tushum", m), G.pl_value(s, "sof foyda", m)
    pp = _D(args.get("margin_points") or 0)
    extra = _D(args.get("extra_profit") or 0)
    if not extra:
        if not pp:
            pp = Decimal(5)
        extra = (rev * pp / 100).quantize(Decimal(1))  # +X points of net margin at today's revenue
    dishes = [x for x in G.menu_engineering(s) if x.margin > 0]
    best = sorted(dishes, key=lambda x: -(x.margin / x.price if x.price else D0))[:5]
    head = f"**Oyiga +{M(extra)} qo'shimcha foyda uchun{f' (sof marja +{pp} punkt)' if pp else ''} eng foydali taomlarni kuchaytiring: {', '.join(x.name for x in best[:3])}.**"
    lines = [
        head,
        "",
        f"Hozir: tushum {M(rev)}, sof foyda {M(net)} ({P(net / rev if rev else D0)}), {_mon(m)}.",
        "",
        "### Har bir taom bo'yicha kerakli qo'shimcha sotuv",
        "| Taom | Porsiya foydasi | Marja | Hozir/oy | Kerak +porsiya/oy | +kuniga | O'sish |",
        "|---|---|---|---|---|---|---|",
    ]
    facts: dict[str, Any] = {"extra": M(extra), "rev": M(rev), "net": M(net)}
    for x in best:
        need = (extra / x.margin).quantize(Decimal(1))
        lines.append(
            f"| {x.name} | {M(x.margin)} | {P(x.margin / x.price)} | {uz.group_digits(int(x.sold))} | +{uz.group_digits(int(need))} | +{int(need / 30)} | {P(need / x.sold) if x.sold else '—'} |"
        )
        facts[f"need_{x.name}"] = uz.group_digits(int(need))
    mix = best[:3]
    per = sum((x.margin for x in mix), D0) / len(mix) if mix else D0
    if per:
        need3 = (extra / per / 3).quantize(Decimal(1))
        lines += [
            "",
            f"**Aralash reja:** 3 taomning har biridan oyiga ~{uz.group_digits(int(need3))} porsiya ko'proq (kuniga ~{int(need3 / 30)}) sotsangiz, maqsadga yetasiz.",
        ]
    lines += [
        "",
        "### Qanday qilib (guideline)",
        "- Reklama byudjeti: kutilgan qo'shimcha foydaning 10–15% idan oshmasin; har kampaniyani 2 hafta o'lchang.",
        "- Instagram/Telegram: shu taomlar rasmi + kombo narx; Yandex/Uzum'da 'tavsiya' joyiga chiqarish.",
        "- Kassada birinchi taklif: shu taomlar (upsell skripti).",
        "",
        "CHIPS: 4 oylik rentabellik | Qaysi taom zarar qilyapti? | Foydani qanday oshiraman?",
    ]
    return _done(facts, lines, head)


# 3. supplier debts (payables) top 10 -------------------------------------------------------
def payables_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = _summary()
    if s is None:
        return _no_data()
    cps = (s.get("details") or {}).get("counterparties") or []
    last = date.fromisoformat(str(s.get("last_date"))[:10]) if s.get("last_date") else None
    m = last.replace(day=1).isoformat() if last else G.last_month(s)
    import calendar

    partial = bool(last and last.day < calendar.monthrange(last.year, last.month)[1])
    period = f"{uz.MONTHS[int(m[5:7]) - 1]} 1–{last.day}" if partial and last else _mon(m)

    def sal(b: dict[str, Any]) -> Decimal:
        return _D((b.get("months") or {}).get(m, b.get("balance")))

    rows = (
        [(b, sal(b)) for b in cps]
        if cps
        else [(b, _D(b["balance"])) for b in (s.get("balances") or [])]
    )
    rows = [(b, v) for b, v in rows if abs(v) >= 1000]
    t = lambda b: str(b.get("type", "")).lower()  # noqa: E731
    loan = [(b, v) for b, v in rows if "kredit" in t(b) or "bank" in b["name"].lower()]
    deposit = [(b, v) for b, v in rows if "ijara" in t(b) and v < 0]
    aggs = [(b, v) for b, v in rows if "agregator" in t(b) and v < 0]
    staff = [(b, v) for b, v in rows if "xodim" in t(b) and v > 0]
    used = {id(b) for b, _ in loan + deposit + aggs + staff}
    other_owe = sorted(
        [(b, v) for b, v in rows if id(b) not in used and v > 0], key=lambda x: -x[1]
    )
    other_recv = sorted(
        [(b, v) for b, v in rows if id(b) not in used and v < 0], key=lambda x: x[1]
    )
    owe_total = sum((v for _, v in loan + staff + other_owe), D0)
    recv_total = -sum((v for _, v in aggs + other_recv), D0)
    head = (
        f"**{period} holatiga: siz qarzdorsiz {M(owe_total)}, sizga qarzdorlar {M(recv_total)}"
        + (
            f" (+ ijara depoziti {M(-sum((v for _, v in deposit), D0))}, qaytariladigan)"
            if deposit
            else ""
        )
        + ".**"
    )
    lines = [head, ""]
    facts: dict[str, Any] = {"owe_total": M(owe_total), "recv_total": M(recv_total)}
    base = ctx.base
    if loan:
        b, v = loan[0]
        hist = sorted((k, _D(x)) for k, x in (b.get("months") or {}).items() if k <= m)
        principal = (
            (hist[-2][1] - hist[-1][1]) if len(hist) > 1 and hist[-2][1] > hist[-1][1] else D0
        )
        if not principal and len(hist) > 2:
            principal = hist[-3][1] - hist[-2][1]
        lm = G.last_month(s)
        interest = G.pl_value(s, "foiz xarajatlari", lm)
        prev_m = (date.fromisoformat(lm) - timedelta(days=1)).replace(day=1).isoformat()
        opening = (
            _D((b.get("months") or {}).get(prev_m)) or v
        )  # interest of month lm accrues on the balance at its start
        rate = (interest * 12 / opening * 100).quantize(Decimal(1)) if opening else D0
        nxt = (
            next(
                (o for o in base.obligations if o.category == "loan" and o.date > base.today), None
            )
            if not base.insufficient_data
            else None
        )
        months_left = int((v / principal).to_integral_value()) if principal else None
        save = (v * rate / 100 / 12).quantize(Decimal(1))
        lines += [
            "### Bank krediti",
            "| Qoldiq | Foiz | Har oy | Keyingi to'lov | Yopiladi |",
            "|---:|---:|---:|---|---|",
            f"| {M(v)} | {rate}% | {M(principal)} asosiy + ~{M(interest)} foiz | {Dt(nxt.date) + ' · ' + M(Decimal(nxt.amount)) if nxt else '25-sana'} | ~{months_left} oyda |"
            if months_left
            else f"| {M(v)} | {rate}% | ~{M(interest)} foiz | {Dt(nxt.date) if nxt else '—'} | — |",
            f"Maslahat: muddatidan oldin to'liq yopsangiz, foizdan oyiga ~{M(save)} tejaysiz — lekin kassada kamida 3 oylik doimiy xarajat qolishi shart.",
            "",
        ]
        facts.update(
            {
                "loan": M(v),
                "loan_rate": f"{rate}%",
                "loan_principal": M(principal),
                "loan_save": M(save),
            }
        )
    if aggs:
        due = {"yandex": 8, "uzum": 10}
        lines += [
            "### Agregatorlar sizga qarzdor (keyingi oyda tushadi)",
            "| Agregator | Summa | Kutilgan sana |",
            "|---|---:|---|",
        ]
        for b, v in sorted(aggs, key=lambda x: x[1]):
            d = next((dd for k, dd in due.items() if k in b["name"].lower()), 10)
            lines.append(f"| {b['name']} | {M(-v)} | har oyning ~{d}-sanasi |")
            facts[f"recv_{b['name']}"] = M(-v)
        lines.append("")
    if deposit:
        lines += (
            ["### Ijara depoziti (qaytariladigan — undiriladigan qarz emas)"]
            + [f"- {b['name']}: {M(-v)}" for b, v in deposit]
            + [""]
        )
    if staff:
        lines += [
            f"### Xodimlarga ish haqi qarzi: {M(sum((v for _, v in staff), D0))} (keyingi oyning 5-sanasida to'lanadi)",
            "",
        ]
    if other_owe:
        lines += (
            [
                "### Boshqa kreditorlar (siz qarzdor)",
                "| Kontragent | Turi | Summa |",
                "|---|---|---:|",
            ]
            + [f"| {b['name']} | {b.get('type', '')} | {M(v)} |" for b, v in other_owe[:10]]
            + [""]
        )
    if other_recv:
        lines += (
            ["### Boshqa debitorlar (sizga qarzdor)"]
            + [f"- {b['name']} ({b.get('type', '')}): {M(-v)}" for b, v in other_recv[:10]]
            + [""]
        )
    if not loan and not aggs and not other_owe:
        lines.append(f"Yetkazib beruvchilarga qarz yo'q ({period}).")
    lines += [
        f"_Manba: Kontragentlar varag'i, saldo ({period}); 1 000 so'mdan kichik saldolar yashirilgan._",
        "",
        "CHIPS: Kreditni yopsam-chi? | Kassa yetadimi? | Yaqin to'lovlar",
    ]
    md = "\n".join(lines)
    return envelope(
        ok=True,
        facts=facts,
        speech=speech_of(facts),
        md=md,
        say=head.strip("*"),
        answer={"headline": head.strip("*"), "reason": ""},
    )


# 6. hiring payback -------------------------------------------------------------------------
def hire_payback_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = _summary()
    if s is None:
        return _no_data()
    m = G.last_month(s)
    pay = s.get("details", {}).get("payroll") or {}
    last = pay.get(sorted(pay)[-1]) if pay else {}
    role = str(args.get("role") or "ofitsiant").lower()
    same = [
        v for k, v in (last or {}).items() if role[:5] in str(v[0]).lower() or role[:5] in k.lower()
    ]
    cost = _D(args.get("salary")) or (
        sum((_D(v[3]) for v in same), D0) / len(same) if same else Decimal(5_000_000)
    )
    cost = cost.quantize(Decimal(1))
    rev = G.pl_value(s, "sof tushum", m)
    checks = _D((s.get("journals", {}).get("checks") or {}).get(m))
    avg = (rev / checks) if checks else Decimal(100000)
    cm = G.break_even(s, m).cm_ratio if hasattr(G.break_even(s, m), "cm_ratio") else Decimal("0.5")
    extra_checks = _D(args.get("extra_checks_per_day") or 8)
    gain = (extra_checks * 30 * avg * cm).quantize(Decimal(1))
    net_gain = gain - cost
    onboarding = cost  # first month: training, lower productivity
    payback = (onboarding / net_gain).quantize(Decimal("0.1")) if net_gain > 0 else None
    be_checks = (cost / (30 * avg * cm)).quantize(Decimal("0.1")) if avg and cm else D0
    ok = payback is not None
    head = (
        f"**Yangi {role} oyiga {M(cost)} turadi; kuniga +{int(extra_checks)} chek bersa, oyiga +{M(net_gain)} sof foyda — {str(payback).replace('.', ',')} oyda o'zini oqlaydi.**"
        if ok
        else f"**Yangi {role} ({M(cost)}/oy) kuniga +{int(extra_checks)} chek bilan o'zini oqlamaydi: kamida {str(be_checks).replace('.', ',')} chek/kun kerak.**"
    )
    wd = G.weekday_avgs(s)
    lines = [
        head,
        "",
        "### Hisob (isbot)",
        f"- Xarajat: {M(cost)}/oy (Ish haqi varag'i, shu lavozimning o'rtacha to'liq xarajati, soliq bilan).",
        f"- O'rtacha chek {M(avg)}, marja (o'zgaruvchan xarajatdan keyin) {P(cm)} → 1 chek {M(avg * cm)} foyda.",
        f"- +{int(extra_checks)} chek/kun × 30 = oyiga +{M(gain)} foyda, minus maosh = {M(net_gain)}.",
        f"- Zararsizlik: kuniga kamida {str(be_checks).replace('.', ',')} qo'shimcha chek.",
    ]
    if len(wd) == 7:
        mx = max(wd, key=lambda w: w[1])
        lines.append(
            f"- Talab bormi: {mx[0]} kuni savdo {M(mx[1])} — eng band kun; xodimni shu kunlar va 13–15, 19–22 soatlarga qo'ying."
        )
    lines += [
        "",
        "### Guideline",
        "- Avval 1 oy sinov muddati bilan oling; chek soni va kutish vaqtini o'lchang.",
        "- To'liq stavka o'rniga dam olish kunlari uchun yarim stavka — xavf 2 baravar kam.",
        "",
        "CHIPS: Kuniga 15 chek bersa? | 50 mln qayerga tikay? | Xodimlar xarajati",
    ]
    facts = {
        "cost": M(cost),
        "gain": M(gain),
        "net_gain": M(net_gain),
        "payback": str(payback),
        "be_checks": str(be_checks),
        "avg_check": M(avg),
    }
    return _done(facts, lines, head)


# 7. where to put extra money ----------------------------------------------------------------
def allocate_capital_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = _summary()
    if s is None:
        return _no_data()
    amount = _D(args["amount"])
    cash, fmin, fdate, safe = _fc(ctx)
    m = G.last_month(s)
    be = G.break_even(s, m)
    reserve = (be.fixed * 3).quantize(Decimal(1))
    loan = s.get("loan") or {}
    rate = _D(loan.get("rate_pct") or 24) / 100
    lb = _D(loan.get("balance"))
    opts = []
    # reserve
    gap = max(D0, reserve - (fmin or cash))
    opts.append(
        (
            "Zaxira (kassa)",
            D0,
            "Xavf yo'q",
            f"Zaxira kerak: {M(reserve)} (3 oylik doimiy xarajat); hozir eng past nuqta {M(fmin or cash)} — "
            + (
                "zaxira YETARLI, qo'shimcha pul daromad bermaydi"
                if gap == 0
                else f"{M(gap)} yetishmaydi — avval shu"
            ),
        )
    )
    # loan prepay
    if lb > 0:
        pre = min(amount, lb)
        opts.append(
            (
                "Kreditni oldindan yopish",
                (pre * rate / 12).quantize(Decimal(1)),
                "Xavf yo'q (kafolatli)",
                f"{M(pre)} × {P(rate)}/12 foiz tejaladi",
            )
        )
    # equipment (fritur example from menu best dish)
    menu = s.get("details", {}).get("menu", {})
    fri = next((n for n in menu if "fri" in n.lower()), None)
    if fri:
        d = menu[fri]
        mg = _D(d.get("price")) - _D(d.get("cost"))
        units = max(10, int(_D((d.get("sold") or {}).get(m)) / 30 * Decimal("0.3")))
        price = min(amount, Decimal(30_000_000))
        r = G.evaluate_investment(
            price, Decimal(units), mg, extra_opex=Decimal(1_500_000), rate=rate
        )
        opts.append(
            (
                f"Jihoz (fritur {M(price)}, +{units} porsiya/kun)",
                r.monthly[2] - r.depreciation,
                "O'rtacha (talab taxmin)",
                f"qoplanish {str(r.payback_months).replace('.', ',')} oy; talab −30% bo'lsa ham qoplaydi",
            )
        )
    # worker
    hp = hire_payback_tool(ctx, {"role": "ofitsiant"})
    ng = (
        _D(
            str(hp["facts"]["net_gain"])
            .replace(" mln", "")
            .replace(",", ".")
            .replace(" so'm", "")
            .replace(" ", "")
        )
        if False
        else None
    )
    rev = G.pl_value(s, "sof tushum", m)
    checks = _D((s.get("journals", {}).get("checks") or {}).get(m))
    avg = rev / checks if checks else Decimal(100000)
    cm = be.cm_ratio if hasattr(be, "cm_ratio") else Decimal("0.5")
    pay = s.get("details", {}).get("payroll") or {}
    last = pay.get(sorted(pay)[-1]) if pay else {}
    of = [v for v in (last or {}).values() if "ofitsiant" in str(v[0]).lower()]
    wcost = (sum((_D(v[3]) for v in of), D0) / len(of)) if of else Decimal(4_000_000)
    wgain = (8 * 30 * avg * cm - wcost).quantize(Decimal(1))
    opts.append(
        (
            "Yangi ishchi (ofitsiant)",
            wgain,
            "Yuqori (oylik har oy ketadi)",
            f"maosh {M(wcost)}/oy; +8 chek/kun taxmini; 50 mln ni emas, oyiga maoshni talab qiladi",
        )
    )
    # marketing of best dish
    opts.append(
        (
            "Reklama (Sezar salat/burger, 5 mln/oy)",
            (Decimal(5_000_000) * Decimal("0.6")).quantize(Decimal(1)),
            "O'rtacha",
            "har 1 so'm reklamaga ~1,6 so'm foyda (sanoat o'rtachasi taxmini) — 2 haftada o'lchanadi",
        )
    )
    ranked = sorted(opts, key=lambda o: -o[1])
    best = ranked[0]
    head = f"**{M(amount)} ni avval «{best[0]}» ga tiking — oyiga ~+{M(best[1])}; zaxira allaqachon yetarli bo'lsa, zaxiraga qo'yish daromad bermaydi.**"
    lines = [
        head,
        "",
        f"Hozir kassa {M(cash)}, 90 kunda eng past {M(fmin or cash)} ({Dt(fdate)}), xavfsiz zaxira {M(reserve)}.",
        "",
        "### Variantlar (oyiga foyda va xavf)",
        "| Variant | Oyiga foyda | Xavf | Izoh |",
        "|---|---|---|---|",
    ]
    facts: dict[str, Any] = {"amount": M(amount), "cash": M(cash), "reserve": M(reserve)}
    for i, o in enumerate(ranked):
        lines.append(f"| {o[0]} | +{M(o[1])} | {o[2]} | {o[3]} |")
        facts[f"opt{i}"] = M(o[1])
    lines += [
        "",
        "### Investitsiya rejasi (pulni yo'qotmaslik qoidasi)",
        f"1. Zaxira: kassada doim kamida {M(reserve)} qolsin — bu chiziqdan pastga hech qanday investitsiya yo'q.",
        "2. Qimmat qarz (24%) — eng xavfsiz 'daromad': foizni tejash kafolatlangan.",
        "3. Jihoz — faqat qoplanishi 12 oydan qisqa va talab −30% bo'lsa ham qoplasa.",
        "4. Ishchi — faqat band soatlarda chek soni rejadan oshganini ko'rsangiz (1 oy sinov).",
        "5. Har investitsiyani 2–4 haftada o'lchang; natija bermasa to'xtating (yo'qotishni cheklash).",
        "",
        "CHIPS: Fritur hozir olaymi yoki keyin? | Yana bitta ishchi olsam? | Kreditni yopsam-chi?",
    ]
    _ = ng, hp
    return _done(facts, lines, head)


# 4+5. equipment purchase: payroll/loan check + timing/payment options ---------------------
def purchase_check(
    ctx: ToolContext, price: Decimal, contribution: Decimal
) -> tuple[list[str], dict[str, Any]]:
    base = ctx.base
    n = min(90, base.horizon_days)
    days = [base.date_at(i) for i in range(n)]
    close = {d: Decimal(str(base.close_on(d))) for d in days}
    obl = [o for o in base.obligations if days[0] < o.date <= days[-1]]
    pays = [o for o in obl if o.category in ("payroll", "loan")][:6]
    lines = [
        "### Oylik va kredit to'lovlari vaqtida to'lanadimi (xariddan keyin)",
        "| Sana | To'lov | Summa | Kassa (xariddan keyin) | Holat |",
        "|---|---|---|---|---|",
    ]
    facts: dict[str, Any] = {}
    safe = Decimal(base.safe_min)
    for o in pays:
        after = close[o.date] - price
        lines.append(
            f"| {Dt(o.date)} | {'Ish haqi' if o.category == 'payroll' else 'Kredit'} | {M(Decimal(o.amount))} | {M(after)} | {'✓ yetadi' if after >= safe else '✗ yetmaydi'} |"
        )
        facts[f"pay_{o.date.isoformat()}"] = M(after)
    payroll = next((o.date for o in obl if o.category == "payroll"), None)

    def low(sub: dict[date, Decimal]) -> tuple[Decimal, date]:
        d = min(days, key=lambda x: close[x] - sub.get(x, D0))
        return close[d] - sub.get(d, D0), d

    now = {d: price for d in days}
    after_pay = {d: (price if payroll and d >= payroll + timedelta(days=1) else D0) for d in days}
    inst = {d: price * min(3, 1 + (d - days[0]).days // 30) / 3 for d in days}
    opts = [
        ("Hozir, o'z pulingizdan", now, D0),
        (
            f"Ish haqidan keyin ({Dt(payroll + timedelta(days=1)) if payroll else '—'})",
            after_pay,
            (contribution * Decimal((payroll - days[0]).days if payroll else 0) / 30).quantize(
                Decimal(1)
            ),
        ),
        ("3 oyga bo'lib to'lash", inst, (price * Decimal("0.24") / 12 * 2).quantize(Decimal(1))),
    ]
    lines += [
        "",
        "### Qachon va qanday olish yaxshi",
        "| Variant | Kassa eng past nuqta | Qo'shimcha xarajat / yo'qotilgan foyda |",
        "|---|---|---|",
    ]
    best = None
    for name, sub, extra in opts:
        lo, ld = low(sub)
        lines.append(f"| {name} | {M(lo)} ({Dt(ld)}) | {M(extra)} |")
        if best is None or (lo >= safe and extra < best[2]):
            best = (name, lo, extra)
    if best:
        lines.append(
            f"\n**Tavsiya: {best[0]}** — kassa eng past {M(best[1])}, chegaradan ({M(safe)}) yuqori; qo'shimcha xarajat eng kam."
        )
        facts["best_option"] = best[0]
    return lines, facts


QA_TOOLS = [
    Tool(
        "profitability",
        "N oylik (standart 4) rentabellik: oyma-oy tushum/foyda/marja + rentabellikni oshirayotgan va pasaytirayotgan top 10 taom (isbot bilan).",
        {
            "type": "object",
            "properties": {"months": {"type": "integer", "minimum": 1, "maximum": 12}},
        },
        profitability_tool,
    ),
    Tool(
        "promote_target",
        "Qaysi taomlarni reklama/savdosini kuchaytirish va maqsadga (sof marja +X punkt yoki +X so'm foyda) yetish uchun har biridan qancha ko'p sotish kerak.",
        {
            "type": "object",
            "properties": {
                "margin_points": {"type": "number"},
                "extra_profit": {"type": "integer"},
            },
        },
        promote_target_tool,
    ),
    Tool(
        "payables",
        "Kontragentlar (yetkazib beruvchilar) oldidagi qarz: jami va top 10, sizga qarzdorlar (agregatorlar).",
        {"type": "object", "properties": {}},
        payables_tool,
    ),
    Tool(
        "hire_payback",
        "Yana bitta ishchi olsam o'zini necha oyda oqlaydi: maosh, qo'shimcha chek, zararsizlik.",
        {
            "type": "object",
            "properties": {
                "role": {"type": "string"},
                "salary": {"type": "integer"},
                "extra_checks_per_day": {"type": "integer"},
            },
        },
        hire_payback_tool,
    ),
    Tool(
        "allocate_capital",
        "Qo'shimcha X so'm qayerga tikish: zaxira, kredit, jihoz, ishchi, reklama — oyiga foyda va xavf bo'yicha tartib + investitsiya rejasi.",
        {
            "type": "object",
            "properties": {"amount": {"type": "integer", "minimum": 1}},
            "required": ["amount"],
        },
        allocate_capital_tool,
    ),
]
TOOLS.update({t.name: t for t in QA_TOOLS})
