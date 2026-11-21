"""Growth CFO (P1 verdict + levers, P2 investment advisor). Pure Python, Decimal only.

Input: the workbook summary dict (DataSource.summary) + forecast facts passed in by the caller.
Cash is the safety constraint; monthly PROFIT is the objective. Buying an asset turns cash into
an asset: only depreciation, interest and lost margin hit profit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from .cfo import break_even, kpi_scorecard, last_month, pl_value, plan_fact

D0 = Decimal(0)
WEEKDAYS = ("Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba")
DRINKS = ("ichimlik", "choy", "amerikano", "kofe", "suv", "sharbat")


def _d(x: Any) -> Decimal:
    try:
        return Decimal(str(x))
    except Exception:
        return D0


def _months(s: dict[str, Any]) -> list[str]:
    pl = s.get("reports", {}).get("pl", {}).get("sof tushum", {})
    last = last_month(s)
    return sorted(m for m, v in pl.items() if m <= last and _d(v) > 0)


# --- diagnostics ------------------------------------------------------------------------------
@dataclass
class Dish:
    name: str
    category: str
    price: Decimal
    cost: Decimal
    margin: Decimal
    fc: Decimal
    sold: Decimal  # last month portions
    cls: str = ""  # Yulduz / Ishchi ot / Jumboq / Past
    cost_change: Decimal = D0  # unit cost change since first month (ratio)


def menu_engineering(s: dict[str, Any]) -> list[Dish]:
    menu = s.get("details", {}).get("menu", {}) or {}
    m = last_month(s)
    out = []
    for name, d in menu.items():
        price, cost = _d(d.get("price")), _d(d.get("cost"))
        sold = _d((d.get("sold") or {}).get(m))
        cbm = d.get("cost_by_month") or {}
        ks = sorted(cbm)
        ch = (_d(cbm[ks[-1]]) / _d(cbm[ks[0]]) - 1) if len(ks) > 1 and _d(cbm[ks[0]]) else D0
        out.append(
            Dish(
                name,
                str(d.get("category", "")),
                price,
                cost,
                price - cost,
                cost / price if price else D0,
                sold,
                cost_change=ch,
            )
        )
    if out:
        avg_sold = sum((x.sold for x in out), D0) / len(out)
        avg_margin = sum((x.margin for x in out), D0) / len(out)
        for x in out:
            hi_pop, hi_mar = x.sold >= avg_sold * Decimal("0.7"), x.margin >= avg_margin
            x.cls = {
                (True, True): "Yulduz",
                (True, False): "Ishchi ot",
                (False, True): "Jumboq",
                (False, False): "Past",
            }[(hi_pop, hi_mar)]
    return sorted(out, key=lambda x: -x.sold)


def food_cost_trend(s: dict[str, Any]) -> list[tuple[str, Decimal]]:
    row = s.get("reports", {}).get("pl", {}).get("food cost sof tushumga", {})
    return [(m, _d(row.get(m))) for m in _months(s) if row.get(m) is not None]


def ingredient_inflation(s: dict[str, Any], top: int = 6) -> list[tuple[str, Decimal, Decimal]]:
    """(product, price change ratio first->last month, last-month spend), biggest spend first."""
    pur = s.get("details", {}).get("purchases", {}) or {}
    rows = []
    for name, p in pur.items():
        ms = sorted(k for k, v in (p.get("months") or {}).items() if _d(v.get("price")) > 0)
        if len(ms) < 2:
            continue
        first, lastp = _d(p["months"][ms[0]]["price"]), _d(p["months"][ms[-1]]["price"])
        spend = _d(p["months"][ms[-1]].get("amount"))
        rows.append((name, lastp / first - 1 if first else D0, spend))
    return sorted(rows, key=lambda r: -r[2])[:top]


def weekday_avgs(s: dict[str, Any]) -> list[tuple[str, Decimal]]:
    z = s.get("journals", {}).get("weekday_z", {}) or {}
    return [(WEEKDAYS[int(k)], _d(v)) for k, v in sorted(z.items(), key=lambda kv: int(kv[0]))]


def profit_trend(s: dict[str, Any]) -> list[tuple[str, Decimal]]:
    row = s.get("reports", {}).get("pl", {}).get("sof foyda", {})
    return [(m, _d(row.get(m))) for m in _months(s)]


# --- levers -----------------------------------------------------------------------------------
@dataclass
class Lever:
    key: str
    title: str
    lo: Decimal  # monthly profit impact, so'm
    hi: Decimal
    confidence: str  # Yuqori / O'rtacha / Past
    assumptions: list[str]
    steps: list[str]

    @property
    def mid(self) -> Decimal:
        return (self.lo + self.hi) / 2


@dataclass
class GrowthPlan:
    month: str
    verdict: str  # XAVFLI / E'TIBOR / BARQAROR / O'SISH
    verdict_reason: str
    net_profit: Decimal
    profit_trend: list[tuple[str, Decimal]]
    food_cost: list[tuple[str, Decimal]]
    fc_target: Decimal
    fc_leak: Decimal
    inflation: list[tuple[str, Decimal, Decimal]]
    dishes: list[Dish]
    weekdays: list[tuple[str, Decimal]]
    checks_vs_plan: Decimal
    avg_check_vs_plan: Decimal
    cash: Decimal
    reserve: Decimal
    idle_cash: Decimal
    loan_balance: Decimal
    loan_rate: Decimal
    levers: list[Lever] = field(default_factory=list)

    @property
    def uplift_lo(self) -> Decimal:
        return sum((x.lo for x in self.levers), D0)

    @property
    def uplift_hi(self) -> Decimal:
        return sum((x.hi for x in self.levers), D0)


def growth_plan(
    s: dict[str, Any], *, forecast_min: Decimal | None, safe_min: Decimal, cash: Decimal
) -> GrowthPlan:
    m = last_month(s)
    sc = kpi_scorecard(s, m)
    food = next(k for k in sc.kpis if k.key == "food")
    flow = next(k for k in sc.kpis if k.key == "flow")
    be = break_even(s, m)
    reserve = (be.fixed * 3).quantize(Decimal(1))
    loan = s.get("loan") or {}
    loan_bal, rate = _d(loan.get("balance")), _d(loan.get("rate_pct")) / 100
    pt = profit_trend(s)
    fct = food_cost_trend(s)
    dishes = menu_engineering(s)
    infl = ingredient_inflation(s)
    wd = weekday_avgs(s)
    c_plan = plan_fact(s, "reja", "o'rtacha chek", m)
    c_fact = plan_fact(s, "fakt", "o'rtacha chek", m)
    avg_check_gap = (c_fact / c_plan - 1) if c_plan else D0

    # verdict (deterministic)
    down3 = len(pt) >= 4 and all(pt[i][1] < pt[i - 1][1] for i in range(len(pt) - 3, len(pt)))
    fc_drift = (
        len(fct) >= 2 and fct[-1][1] - fct[0][1] >= Decimal("0.015") and food.status == "problem"
    )
    if forecast_min is not None and forecast_min < safe_min:
        verdict, why = "XAVFLI", "90 kun ichida kassa xavfsiz chegaradan pastga tushadi"
    elif down3 or fc_drift:
        verdict = "E'TIBOR"
        why = (
            "sof foyda 3 oydan beri pasaymoqda"
            if down3
            else (
                (
                    f"food cost {fct[0][1] * 100:.1f}% dan {(food.value or fct[-1][1]) * 100:.1f}% ga oshdi (maqsad {food.target * 100:.0f}%), oyiga ~{food.gap_money / 1_000_000:.1f} mln yo'qotish"
                ).replace(".", ",")
            )
        )
    elif len(pt) >= 4 and pt[-1][1] > pt[-4][1] * Decimal("1.1"):
        verdict, why = "O'SISH", "sof foyda 3 oyda 10% dan ko'p o'sdi"
    else:
        verdict, why = "BARQAROR", "foyda va kassa barqaror"

    gp = GrowthPlan(
        m,
        verdict,
        why,
        pl_value(s, "sof foyda", m),
        pt,
        fct,
        food.target or Decimal("0.32"),
        food.gap_money,
        infl,
        dishes,
        wd,
        flow.value,
        avg_check_gap,
        cash,
        reserve,
        max(D0, cash - reserve),
        loan_bal,
        rate,
    )
    levers: list[Lever] = []
    target = gp.fc_target
    # 1. reprice dishes above target FC by their own unit-cost inflation
    over = [x for x in dishes if x.fc > target and x.sold > 0 and x.price > 0]
    if over:
        hi = lo = D0
        names = []
        for x in over:
            inc = max(x.cost_change, Decimal("0.05"))
            new_price = (x.price * (1 + inc) / 1000).quantize(Decimal(1)) * 1000
            hi += (new_price - x.price) * x.sold
            lo += x.sold * Decimal("0.95") * (new_price - x.cost) - x.sold * x.margin
            names.append(f"{x.name} {int(x.price):,}→{int(new_price):,}".replace(",", " "))
        avg_infl = sum((r[1] for r in infl[:4]), D0) / max(1, len(infl[:4]))
        levers.append(
            Lever(
                "reprice",
                "Narxni xomashyo inflyatsiyasiga moslash",
                lo.quantize(Decimal(1)),
                hi.quantize(Decimal(1)),
                "Yuqori",
                [
                    f"Xomashyo narxi yil boshidan o'rtacha +{avg_infl * 100:.0f}%, menyu narxi o'zgarmagan",
                    "Hajm 0% (yuqori) yoki −5% (past) kamayadi",
                ],
                [
                    f"Yangi narxlar: {', '.join(names[:5])}",
                    "Menyu va POS'da narxni bir kunda yangilang",
                    "2 hafta sotuv sonini kuzating",
                ],
            )
        )
    # 2. mix shift: high-volume low-margin item (FC > 50%) -> higher-margin substitute in same group
    low = [x for x in dishes if x.fc > Decimal("0.5") and x.sold > 0]
    for x in low[:1]:
        is_drink = any(w in x.name.lower() or w in x.category.lower() for w in DRINKS)
        subs = [
            y
            for y in dishes
            if y is not x
            and y.margin > x.margin
            and (any(w in y.name.lower() or w in y.category.lower() for w in DRINKS) == is_drink)
        ]
        if subs:
            sub = max(subs, key=lambda y: y.margin)
            per = sub.margin - x.margin
            levers.append(
                Lever(
                    "mix",
                    f"{x.name} o'rniga {sub.name} taklif qilish",
                    (x.sold * Decimal("0.10") * per).quantize(Decimal(1)),
                    (x.sold * Decimal("0.30") * per).quantize(Decimal(1)),
                    "O'rtacha",
                    [
                        f"{x.name}: food cost {x.fc * 100:.0f}%, porsiya foydasi {int(x.margin):,} so'm".replace(
                            ",", " "
                        ),
                        f"{sub.name}: porsiya foydasi {int(sub.margin):,} so'm".replace(",", " "),
                        "Hajmning 10–30% i almashadi",
                    ],
                    [
                        f"Kassir {x.name} o'rniga {sub.name} ni birinchi taklif qilsin",
                        f"Kombo setlarda {sub.name} ni standart qiling",
                    ],
                )
            )
    # 3. promote Jumboq (high margin, low volume)
    jum = sorted([x for x in dishes if x.cls == "Jumboq" and x.sold > 0], key=lambda x: -x.margin)
    for x in jum[:1]:
        levers.append(
            Lever(
                "promote",
                f"{x.name} ni ko'proq sotish (Jumboq: yuqori foyda, kam sotiladi)",
                (x.sold * Decimal("0.20") * x.margin).quantize(Decimal(1)),
                (x.sold * Decimal("0.40") * x.margin).quantize(Decimal(1)),
                "O'rtacha",
                [
                    f"Porsiya foydasi {int(x.margin):,} so'm, oyiga atigi {int(x.sold)} porsiya".replace(
                        ",", " "
                    ),
                    "Sotuv +20–40% oshadi",
                ],
                [
                    "Menyuda birinchi sahifaga, rasm bilan chiqaring",
                    "Ofitsiantlarga har sotuvdan bonus bering",
                    "Kunlik 'tavsiya' taomi qiling",
                ],
            )
        )
    # 4. weak weekdays combo
    if len(wd) == 7:
        best = max(wd, key=lambda w: w[1])
        weak = sorted(wd, key=lambda w: w[1])[:4]
        rev = pl_value(s, "sof tushum", m)
        cm = be.cm_ratio if hasattr(be, "cm_ratio") else (1 - (food.value or D0))
        avg_chk = c_fact or Decimal(85000)
        days = Decimal(len(weak) * 52) / 12  # weak days per month
        levers.append(
            Lever(
                "weekday",
                "Sust kunlarga lanch-kombo",
                (Decimal(5) * avg_chk * Decimal("0.5") * days).quantize(Decimal(1)),
                (Decimal(12) * avg_chk * Decimal("0.5") * days).quantize(Decimal(1)),
                "O'rtacha",
                [
                    f"{weak[0][0]} o'rtacha {weak[0][1] / 1_000_000:.1f} mln vs {best[0]} {best[1] / 1_000_000:.1f} mln",
                    "Sust kunlarda kuniga +5–12 chek, kombo marjasi ~50%",
                ],
                [
                    f"{', '.join(w[0] for w in weak)} 12:00–15:00 lanch-kombo (taom + fri + ichimlik)",
                    "Yaqin ofislarga Telegram orqali taklif",
                    "Natijani 4 haftada tekshiring",
                ],
            )
        )
        _ = rev, cm
    # 5. prepay expensive debt from idle cash (keep the reserve)
    if loan_bal > 0 and gp.idle_cash > loan_bal and rate > 0:
        save = (loan_bal * rate / 12).quantize(Decimal(1))
        levers.append(
            Lever(
                "prepay",
                f"Kreditni ({int(loan_bal / 1_000_000)} mln, {rate * 100:.0f}%) muddatidan oldin yopish",
                save,
                save,
                "Yuqori",
                [
                    f"Bo'sh pul {gp.idle_cash / 1_000_000:.0f} mln (zaxira 3 oylik doimiy xarajat {reserve / 1_000_000:.0f} mln qoladi)",
                    f"Foiz {rate * 100:.0f}% — investitsiya daromadidan qimmat",
                ],
                [
                    "Bank bilan muddatidan oldin to'lash shartini kelishing",
                    "Zaxirani alohida hisobda saqlang",
                ],
            )
        )
    gp.levers = sorted(levers, key=lambda x: -x.mid)
    return gp


# --- P2 investment ----------------------------------------------------------------------------
@dataclass
class InvestmentResult:
    price: Decimal
    monthly: list[Decimal]  # contribution by month (ramp applied), 24 months
    full_contribution: Decimal
    payback_months: Decimal | None
    profit_12: Decimal  # cumulative incremental profit after depreciation
    profit_24: Decimal
    roi_12: Decimal
    npv: Decimal
    depreciation: Decimal
    downside_payback: Decimal | None
    breakeven_units: Decimal
    cash_after: Decimal
    cash_low: Decimal
    cash_low_date: date | None
    buffer: Decimal
    verdict: str  # OLING / KUTING / OLMANG
    best_date: date | None
    reason: str
    loan_cost: Decimal
    cum_with: list[Decimal]
    cum_without: list[Decimal]


def _payback(price: Decimal, monthly: list[Decimal]) -> Decimal | None:
    cum = D0
    for i, c in enumerate(monthly):
        if c > 0 and cum + c >= price:
            return (Decimal(i) + (price - cum) / c).quantize(Decimal("0.1"))
        cum += c
    return None


def evaluate_investment(
    price: Decimal,
    units_per_day: Decimal,
    unit_margin: Decimal,
    *,
    extra_opex: Decimal = D0,
    ramp: tuple[Decimal, ...] = (Decimal("0.5"), Decimal("0.75"), Decimal(1)),
    life_months: int = 60,
    rate: Decimal = Decimal("0.24"),
    today: date | None = None,
    cash: Decimal = D0,
    forecast_min: Decimal | None = None,
    forecast_min_date: date | None = None,
    buffer: Decimal = D0,
    base_net: Decimal = D0,
    days: int = 30,
) -> InvestmentResult:
    full = units_per_day * unit_margin * days
    monthly = [
        (full * (ramp[i] if i < len(ramp) else Decimal(1)) - extra_opex).quantize(Decimal("0.01"))
        for i in range(24)
    ]
    dep = (price / life_months).quantize(Decimal(1))
    pb = _payback(price, monthly)
    p12 = sum(monthly[:12], D0) - dep * 12
    p24 = sum(monthly[:24], D0) - dep * 24
    r = rate / 12
    npv = -price + sum(
        (
            c / (1 + r) ** (i + 1)
            for i, c in enumerate(monthly[:life_months] + [monthly[-1]] * max(0, life_months - 24))
        ),
        D0,
    )
    down = [
        (full * Decimal("0.7") * (ramp[i] if i < len(ramp) else 1) - extra_opex) for i in range(60)
    ]
    be_units = (
        ((price / Decimal(life_months / 2) + extra_opex) / (unit_margin * days)).quantize(
            Decimal("0.1")
        )
        if unit_margin
        else D0
    )
    low = (forecast_min if forecast_min is not None else cash) - price
    after = cash - price
    if pb is None or npv < 0:
        verdict, best, why = "OLMANG", None, "foyda xarajatni qoplamaydi"
    elif low < buffer:
        verdict, best, why = (
            "KUTING",
            None,
            "xariddan keyin kassa xavfsiz chegaradan pastga tushadi",
        )
    else:
        t = today or date.today()
        season = date(t.year, 12, 1) if t < date(t.year, 12, 1) else t + timedelta(days=7)
        verdict, best, why = (
            "OLING",
            min(season, t + timedelta(days=14)),
            "kassa chegaradan yuqori qoladi va foyda tez qoplaydi",
        )
    cum_w, cum_wo, a, b = [], [], D0, D0
    for c in monthly[:24]:
        b += base_net
        a += base_net + c - dep
        cum_w.append(a.quantize(Decimal(1)))
        cum_wo.append(b.quantize(Decimal(1)))
    return InvestmentResult(
        price,
        monthly,
        full,
        pb,
        p12.quantize(Decimal(1)),
        p24.quantize(Decimal(1)),
        (p12 / price * 100).quantize(Decimal(1)) if price else D0,
        npv.quantize(Decimal(1)),
        dep,
        _payback(price, down),
        be_units,
        after,
        low,
        forecast_min_date,
        buffer,
        verdict,
        best,
        why,
        (price * rate * Decimal(12) / 2 / 12).quantize(Decimal(1)),
        cum_w,
        cum_wo,
    )
