"""Demo dataset generator (pure: no DB, no network). Used by `seed_demo` and its tests.

Everything is relative to `today`:
- 8 months of daily sales by weekday (the last 8 weeks average exactly the DESIGN.md
  weekday numbers; older months have seasonal drift and noise), daily variable costs,
  monthly payments on the real calendar (1st rent, 10th salaries + NBU loan, 15th tax,
  25th supplier), and "Svet" (electricity) around the 3rd that the AI later notices.
- Today's closing cash is solved so that the lowest balance in the next 60 days is
  TARGET_LOWEST (18,8 mln). With the DESIGN.md dates (today = 2026-11-21) this reproduces
  the mockups exactly (48,2 mln today).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from apps.engine import (
    EngineInput,
    ObligationIn,
    ParamsIn,
    RuleIn,
    TxnIn,
    aggregate_daily,
    forecast,
)
from apps.engine.dates import add_months, on_day_of_month

M = Decimal(1_000_000)
TARGET_LOWEST = Decimal("18800000.00")
HISTORY_DAYS = 243  # ~8 months
FUTURE_MONTHS = 5
# 42 % (DESIGN.md uses 45 %): with 45 % the monthly cash growth is too small (~0 in
# February) for a safe purchase date to exist on every day of the year. Measured: 0.45 fails
# 22/186 days, 0.42 passes all (see tests/test_seed_demo.py). Golden tests keep 45 %.
VARIABLE_COST_RATIO = Decimal("0.42")
SAFE_MIN = Decimal("10000000.00")
NAVROZ_WEEKDAY_REVENUE = ("5.8", "5.9", "6.0", "6.2", "7.6", "8.9", "8.2")  # Mon..Sun, mln

# variable-cost categories (share of the 45 %) and typical counterparties
VARIABLE_COSTS = (
    ("sabzavot", Decimal("0.30"), "Chorsu bozori"),
    ("non va un", Decimal("0.15"), "Non sexi"),
    ("ichimliklar", Decimal("0.25"), "Coca-Cola ichimliklari"),
    ("xo'jalik", Decimal("0.15"), ""),
    ("gaz", Decimal("0.15"), "Hududgaz"),
)


@dataclass
class DemoTxn:
    date: date
    amount: Decimal
    direction: str  # in | out
    category: str
    counterparty: str = ""
    method: str = ""
    note: str = ""


@dataclass
class DemoObligation:
    title: str
    amount: Decimal
    due_date: date
    priority: str
    category: str
    counterparty: str
    status: str  # paid | planned


@dataclass
class DemoRule:
    type: str
    target: dict[str, object]
    effect: dict[str, object]
    text_uz: str
    source: str  # user | ai_confirmed
    author: str  # owner | accountant
    days_ago: int


@dataclass
class DemoEmployee:
    name: str
    role: str
    salary: Decimal


@dataclass
class DemoBusiness:
    name: str
    kind: str
    city: str
    staff_count: int
    safe_min: Decimal
    today: date
    closing_cash_today: Decimal
    weekday_revenue: tuple[Decimal, ...]
    variable_cost_ratio: Decimal
    txns: list[DemoTxn]
    obligations: list[DemoObligation]
    employees: list[DemoEmployee]
    rules: list[DemoRule] = field(default_factory=list)
    accuracy: list[tuple[date, Decimal]] = field(default_factory=list)
    svet_amount: Decimal = Decimal(0)

    def engine_txns(self) -> list[TxnIn]:
        return [
            TxnIn(
                t.date, t.amount, "in" if t.direction == "in" else "out", t.category, t.counterparty
            )
            for t in self.txns
        ]

    def last_payroll_amount(self) -> Decimal | None:
        paid = [o for o in self.obligations if o.category == "payroll" and o.status == "paid"]
        return max(paid, key=lambda o: o.due_date).amount if paid else None


def _q(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round_thousand(x: Decimal) -> Decimal:
    return (x / 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP) * 1000


def _zero_sum_noise(rng: random.Random, n: int, spread: Decimal) -> list[Decimal]:
    raw = [Decimal(rng.randint(-100, 100)) / 100 * spread for _ in range(n)]
    raw = [_round_thousand(x) for x in raw]
    raw[-1] -= sum(raw)  # exact zero sum -> exact weekday averages
    return raw


SEASON = {
    1: "0.86",
    2: "0.88",
    3: "0.97",
    4: "0.95",
    5: "0.98",
    6: "1.04",
    7: "1.08",
    8: "1.06",
    9: "0.96",
    10: "0.97",
    11: "1.0",
    12: "1.03",
}

NAVROZ_STAFF = [
    ("Shuhrat", "oshpaz", "4.5"),
    ("Malika", "oshpaz", "4.0"),
    ("Bekzod", "oshpaz yordamchisi", "3.0"),
    ("Jasur", "ofitsiant", "2.6"),
    ("Nilufar", "ofitsiant", "2.6"),
    ("Sardor", "ofitsiant", "2.6"),
    ("Kamola", "ofitsiant", "2.6"),
    ("Otabek", "barmen", "3.0"),
    ("Gulnora", "kassir", "2.8"),
    ("Rustam", "qorovul", "2.4"),
    ("Zarina", "tozalovchi", "2.3"),
    ("Aziz", "haydovchi", "2.9"),
    ("Dilshod", "omborchi", "2.8"),
    ("Madina", "administrator", "3.6"),
    ("Ulug'bek", "somsapaz", "3.3"),
]  # sums to 45.0 mln


@dataclass(frozen=True)
class Profile:
    name: str
    scale: Decimal
    rent: Decimal
    payroll: Decimal
    loan: Decimal
    tax: Decimal
    supplier: Decimal
    supplier_name: str
    staff: int
    seed: int


NAVROZ = Profile(
    "Navro'z Kafe",
    Decimal(1),
    15 * M,
    45 * M,
    Decimal("18.5") * M,
    8 * M,
    22 * M,
    "Agro Go'sht",
    15,
    42,
)
PEERS = (
    Profile(
        "Bahor Kafe", Decimal("0.85"), 12 * M, 38 * M, 14 * M, 7 * M, 18 * M, "Halol Go'sht", 13, 7
    ),
    Profile(
        "Shirin Choyxona",
        Decimal("0.95"),
        13 * M,
        42 * M,
        16 * M,
        7 * M,
        20 * M,
        "Toshkent Un",
        14,
        11,
    ),
    Profile(
        "Yulduz Fast Food",
        Decimal("1.15"),
        18 * M,
        52 * M,
        21 * M,
        9 * M,
        25 * M,
        "Agro Go'sht",
        17,
        13,
    ),
    Profile(
        "Mehr Oshxona",
        Decimal("1.25"),
        20 * M,
        56 * M,
        23 * M,
        10 * M,
        28 * M,
        "Sharq Savdo",
        18,
        17,
    ),
    Profile(
        "Sharq Kofe", Decimal("0.80"), 11 * M, 35 * M, 12 * M, 6 * M, 16 * M, "Kofe Import", 12, 19
    ),
)


def monthly_obligations(p: Profile, today: date) -> list[DemoObligation]:
    out: list[DemoObligation] = []
    first = date(today.year, today.month, 1)
    for k in range(-(HISTORY_DAYS // 28 + 1), FUTURE_MONTHS + 1):
        m = add_months(first, k)
        y, mo = m.year, m.month
        items = [
            (1, "Ijara", p.rent, "critical", "rent", "Ijara beruvchi"),
            (10, f"Ish haqi · {p.staff} xodim", p.payroll, "critical", "payroll", ""),
            (10, "NBU kredit to'lovi", p.loan, "critical", "loan", "NBU"),
            (15, "Soliq", p.tax, "critical", "tax", "Soliq qo'mitasi"),
            (
                25,
                f"Ta'minotchi · {p.supplier_name}",
                p.supplier,
                "deferrable",
                "supplier",
                p.supplier_name,
            ),
        ]
        for day, title, amount, prio, cat, cp in items:
            d = on_day_of_month(y, mo, day)
            if d < today - timedelta(days=HISTORY_DAYS):
                continue
            out.append(
                DemoObligation(title, amount, d, prio, cat, cp, "paid" if d <= today else "planned")
            )
    return sorted(out, key=lambda o: (o.due_date, o.title))


def _build(p: Profile, today: date, *, with_rules: bool) -> DemoBusiness:
    rng = random.Random(p.seed)
    weekday_rev = tuple(_q(Decimal(x) * M * p.scale) for x in NAVROZ_WEEKDAY_REVENUE)
    start = today - timedelta(days=HISTORY_DAYS - 1)
    recent_start = today - timedelta(days=55)  # last 8 weeks: exact weekday averages
    noise = {wd: _zero_sum_noise(rng, 8, Decimal("0.6") * M * p.scale) for wd in range(7)}
    seen = [0] * 7
    txns: list[DemoTxn] = []
    for i in range(HISTORY_DAYS):
        d = start + timedelta(days=i)
        wd = d.weekday()
        base = weekday_rev[wd]
        if d >= recent_start:
            revenue = base + noise[wd][seen[wd]]
            seen[wd] += 1
        else:
            season = Decimal(SEASON[d.month])
            jitter = Decimal(rng.randint(-8, 8)) / 100
            revenue = _round_thousand(base * season * (1 + jitter) * Decimal("0.97"))
        cash = _round_thousand(revenue * Decimal("0.4"))
        txns.append(DemoTxn(d, cash, "in", "savdo", method="naqd", note="Kunlik savdo"))
        txns.append(DemoTxn(d, revenue - cash, "in", "savdo", method="karta", note="Uzcard/Humo"))
        variable = revenue * VARIABLE_COST_RATIO
        remaining = _round_thousand(variable)
        for j, (cat, share, cp) in enumerate(VARIABLE_COSTS):
            if j == len(VARIABLE_COSTS) - 1:
                amount = remaining
            else:
                amount = _round_thousand(variable * share)
                remaining -= amount
            txns.append(DemoTxn(d, amount, "out", cat, cp, method="naqd" if j % 2 else "karta"))

    obligations = monthly_obligations(p, today)
    for o in obligations:
        if o.status == "paid" and o.due_date >= start:
            txns.append(
                DemoTxn(
                    o.due_date,
                    o.amount,
                    "out",
                    o.category,
                    o.counterparty,
                    method="bank",
                    note=o.title,
                )
            )
    # electricity around the 3rd (history only: the "AI sezdi" pattern)
    svet = _round_thousand(Decimal("2.1") * M * p.scale)
    m = date(start.year, start.month, 1)
    while m <= today:
        d = on_day_of_month(m.year, m.month, 3) + timedelta(days=rng.choice((-1, 0, 0, 1)))
        if start <= d <= today:
            amt = _round_thousand(svet * (1 + Decimal(rng.randint(-5, 5)) / 100))
            txns.append(
                DemoTxn(
                    d,
                    amt,
                    "out",
                    "kommunal",
                    "Hududiy elektr tarmoqlari",
                    method="bank",
                    note="Svet",
                )
            )
        m = add_months(m, 1)

    names = (
        NAVROZ_STAFF
        if p is NAVROZ
        else [(f"Xodim {i + 1}", "xodim", str(_q(p.payroll / p.staff / M))) for i in range(p.staff)]
    )
    employees = [DemoEmployee(n, r, _q(Decimal(s) * M)) for n, r, s in names]
    if p is not NAVROZ:  # make the per-person list add up to the payroll exactly
        employees[-1].salary += p.payroll - sum(e.salary for e in employees)

    rules: list[DemoRule] = []
    if with_rules:
        rules = [
            DemoRule(
                "priority",
                {"category": "payroll"},
                {"level": "critical"},
                "Oylik har oy 10-sanada, kechiktirib bo'lmaydi",
                "user",
                "owner",
                19,
            ),
            DemoRule(
                "weekday_factor",
                {"weekdays": [4, 5]},
                {"multiplier": "1.15", "period": {"from": "03-14", "to": "03-21"}},
                "Navro'z oldidan juma–shanba savdosi yuqori",
                "ai_confirmed",
                "owner",
                1,
            ),
        ]

    biz = DemoBusiness(
        name=p.name,
        kind="cafe",
        city="Toshkent",
        staff_count=p.staff,
        safe_min=SAFE_MIN,
        today=today,
        closing_cash_today=Decimal(0),
        weekday_revenue=weekday_rev,
        variable_cost_ratio=VARIABLE_COST_RATIO,
        txns=sorted(txns, key=lambda t: t.date),
        obligations=obligations,
        employees=employees,
        rules=rules,
        svet_amount=svet,
    )
    monday = today - timedelta(days=today.weekday())
    biz.accuracy = [
        (monday - timedelta(weeks=4 - k), Decimal(x))
        for k, x in enumerate(("0.14", "0.11", "0.08", "0.06"))
    ]
    biz.closing_cash_today = solve_closing_cash(biz)
    return biz


def engine_input(biz: DemoBusiness, opening: Decimal) -> EngineInput:
    rules = [RuleIn(type=r.type, target=r.target, effect=r.effect) for r in biz.rules]  # type: ignore[arg-type]
    history = aggregate_daily(
        biz.engine_txns(), rules, start=biz.today - timedelta(days=55), end=biz.today
    )
    return EngineInput(
        today=biz.today,
        opening_balance=opening,
        history=history,
        obligations=[
            ObligationIn(
                title=o.title,
                amount=o.amount,
                due_date=o.due_date,
                priority=o.priority,  # type: ignore[arg-type]
                counterparty=o.counterparty,
                category=o.category,
            )
            for o in biz.obligations
            if o.status == "planned"
        ],
        rules=rules,
        params=ParamsIn(variable_cost_ratio=biz.variable_cost_ratio),
        safe_min=biz.safe_min,
        staff_count=biz.staff_count,
        last_payroll_amount=biz.last_payroll_amount(),
    )


def solve_closing_cash(biz: DemoBusiness, horizon: int = 60) -> Decimal:
    """Today's close such that the lowest balance in the next `horizon` days = target."""
    lowest_from_zero = forecast(engine_input(biz, Decimal("0.00")), horizon).min_balance
    return _q(TARGET_LOWEST - lowest_from_zero)


def build_navroz(today: date) -> DemoBusiness:
    return _build(NAVROZ, today, with_rules=True)


def build_peers(today: date) -> list[DemoBusiness]:
    return [_build(p, today, with_rules=False) for p in PEERS]


def revenue_band(monthly_revenue: Decimal) -> str:
    for lo, hi in ((0, 50), (50, 100), (100, 300), (300, 800)):
        if monthly_revenue < hi * M:
            return f"{lo}_{hi}"
    return "800_plus"
