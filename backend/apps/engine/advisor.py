"""Advisor calculations (pure Python + numpy, Decimal at the boundary).

Every function answers a planning question from the forecast and returns numbers only.
The tools layer (apps/ai/advisor_tools.py) turns them into display/speech/ui_blocks.
Anything that is not data (a growth %, extra portions per day, a loan rate) arrives as an
explicit argument and is echoed back in `assumptions` so the person can change it.

"Safe" everywhere means the forecast verdict stays `yes`: every day of the horizon keeps
the balance >= safe_min (the same rule as `compute_verdict`).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

import numpy as np

from .dates import add_months
from .forecast import forecast
from .money import from_tiyin, to_tiyin
from .scenario import delta_for
from .types import Change, EngineError, EngineInput, ForecastResult, IntArray

ADVISOR_HORIZON_DAYS = 180
CashSchedule = tuple[tuple[date, Decimal], ...]
Schedule = Callable[[date], CashSchedule]
STEP = Decimal(100_000)  # amounts the advisor suggests are rounded up to 0,1 mln
DAYS_PER_MONTH = Decimal(30)
DSCR_MIN = Decimal("1.5")  # monthly net cash must cover a loan payment 1.5 times


@dataclass(frozen=True)
class Assumption:
    key: str
    text: str
    value: str
    editable: bool = True


def round_up(x: Decimal, step: Decimal = STEP) -> Decimal:
    if x <= 0:
        return Decimal(0)
    return (x / step).to_integral_value(rounding=ROUND_CEILING) * step


def annuity(principal: Decimal, annual_rate_pct: Decimal, months: int) -> Decimal:
    """Monthly annuity payment (so'm, rounded to 1 000)."""
    if months < 1 or principal <= 0:
        raise EngineError("loan needs months >= 1 and a positive amount")
    r = annual_rate_pct / Decimal(1200)
    if r == 0:
        pay = principal / months
    else:
        pay = principal * r / (1 - (1 + r) ** -months)
    return pay.quantize(Decimal(1000), rounding=ROUND_HALF_UP)


def advisor_base(inp: EngineInput) -> ForecastResult:
    return forecast(inp, ADVISOR_HORIZON_DAYS)


# --- array helpers (tiyin) --------------------------------------------------------------
def _flows(
    base: ForecastResult, schedule: Sequence[tuple[date, Decimal]], sign: int = -1
) -> IntArray:
    flows = np.zeros(len(base.close), dtype=np.int64)
    for d, amount in schedule:
        i = (d - base.today).days
        if 0 <= i < len(flows):
            flows[i] += sign * to_tiyin(amount)
    return flows


def _after(close: IntArray, flows: IntArray) -> IntArray:
    out: IntArray = close + np.cumsum(flows)
    return out


def _safe(arr: IntArray, safe: int) -> bool:
    return int(arr.min()) >= safe


def _low(base: ForecastResult, arr: IntArray) -> tuple[Decimal, date]:
    i = int(arr.argmin())
    return from_tiyin(int(arr[i])), base.today + timedelta(days=i)


def _earliest(
    base: ForecastResult, close: IntArray, make: Schedule, *, last_offset: int = 0
) -> tuple[int, IntArray] | None:
    """First start index whose schedule keeps every day >= safe_min."""
    safe = to_tiyin(base.safe_min)
    for i in range(0, len(close) - last_offset):
        arr = _after(close, _flows(base, make(base.today + timedelta(days=i))))
        if _safe(arr, safe):
            return i, arr
    return None


def purchase_schedule(
    amount: Decimal,
    mode: str,
    *,
    n: int | None = None,
    rate: Decimal | None = None,
    months: int | None = None,
) -> tuple[Schedule, list[Assumption]]:
    """date -> cash-out schedule for paying `amount` in cash / installments(n) / loan."""
    if mode == "cash":
        return (lambda d: ((d, amount),)), []
    if mode == "installments":
        k = int(n or 3)
        if not 2 <= k <= 24:
            raise EngineError("installments must be 2..24 months")
        part = (amount / k).quantize(Decimal(1000), rounding=ROUND_CEILING)
        return (lambda d: tuple((add_months(d, j), part) for j in range(k))), [
            Assumption("n", f"Bo'lib to'lash: {k} oy, har oy {part:.0f} so'm", str(k))
        ]
    if mode == "loan":
        if rate is None or months is None:
            raise EngineError("loan needs rate and months")
        pay = annuity(amount, rate, months)
        return (lambda d: tuple((add_months(d, j), pay) for j in range(1, months + 1))), [
            Assumption("rate", f"Kredit foizi: yiliga {rate}%", str(rate)),
            Assumption("months", f"Muddat: {months} oy, oyiga {pay:.0f} so'm", str(months)),
        ]
    raise EngineError("mode must be cash, installments or loan")


# --- when_can_afford / savings_goal -----------------------------------------------------
@dataclass(frozen=True)
class AffordResult:
    amount: Decimal
    mode: str
    earliest: date | None
    lowest_after: Decimal | None
    lowest_after_date: date | None
    capacity_now: Decimal  # how much could be spent today and stay safe
    target: date
    shortfall: Decimal  # at the target date (0 when affordable by then)
    monthly_set_aside: Decimal
    revenue_pct_needed: Decimal | None  # to make it affordable by the target date
    earlier_with_revenue_10: date | None
    assumptions: tuple[Assumption, ...] = ()
    insufficient_data: bool = False


def _capacity(base: ForecastResult, close: IntArray, i: int) -> Decimal:
    """Largest one-off spend on day i that keeps every later day >= safe_min."""
    safe = to_tiyin(base.safe_min)
    if i > 0 and int(close[:i].min()) < safe:
        return Decimal(0)
    return max(Decimal(0), from_tiyin(int(close[i:].min()) - safe))


def _revenue_close(base: ForecastResult, inp: EngineInput, pct: Decimal) -> IntArray:
    delta, _ = delta_for(base, inp, Change("revenue_pct", pct))
    out: IntArray = base.close + np.cumsum(delta)
    return out


def when_can_afford(
    inp: EngineInput,
    amount: Decimal,
    *,
    mode: str = "cash",
    n: int | None = None,
    rate: Decimal | None = None,
    months: int | None = None,
    target: date | None = None,
    base: ForecastResult | None = None,
) -> AffordResult:
    if amount <= 0:
        raise EngineError("amount must be positive")
    base = base or advisor_base(inp)
    target = min(target or base.end, base.end)
    if base.insufficient_data:
        return AffordResult(
            amount,
            mode,
            None,
            None,
            None,
            Decimal(0),
            target,
            amount,
            Decimal(0),
            None,
            None,
            insufficient_data=True,
        )
    make, assumptions = purchase_schedule(amount, mode, n=n, rate=rate, months=months)
    last = 30 if mode == "cash" else 0  # see at least a month after a cash purchase
    hit = _earliest(base, base.close, make, last_offset=last)
    earliest = base.today + timedelta(days=hit[0]) if hit else None
    low, low_d = _low(base, hit[1]) if hit else (None, None)
    t_idx = (target - base.today).days
    cap_target = _capacity(base, base.close, t_idx)
    shortfall = (
        Decimal(0) if earliest and earliest <= target else max(Decimal(0), amount - cap_target)
    )
    months_left = max(Decimal(1), Decimal(t_idx) / DAYS_PER_MONTH)
    set_aside = round_up(shortfall / months_left) if shortfall else Decimal(0)

    def ok_with(pct: Decimal) -> date | None:
        close = _revenue_close(base, inp, pct)
        h = _earliest(base, close, make, last_offset=last)
        return base.today + timedelta(days=h[0]) if h else None

    needed: Decimal | None = None
    if shortfall:
        lo, hi = Decimal(0), Decimal(100)
        if (d := ok_with(hi)) is None or d > target:
            needed = None  # even +100 % sales would not do it
        else:
            for _ in range(12):
                mid = (lo + hi) / 2
                d = ok_with(mid)
                if d is not None and d <= target:
                    hi = mid
                else:
                    lo = mid
            needed = hi.quantize(Decimal("0.1"), rounding=ROUND_CEILING)
    earlier = ok_with(Decimal(10)) if earliest else None
    return AffordResult(
        amount,
        mode,
        earliest,
        low,
        low_d,
        _capacity(base, base.close, 0),
        target,
        shortfall,
        set_aside,
        needed,
        earlier,
        tuple(assumptions),
    )


def savings_goal(
    inp: EngineInput,
    amount: Decimal,
    by_date: date | None = None,
    base: ForecastResult | None = None,
) -> AffordResult:
    """When `amount` can be put aside without breaking any obligation (= a cash spend)."""
    return when_can_afford(inp, amount, mode="cash", target=by_date, base=base)


# --- debts --------------------------------------------------------------------------------
@dataclass(frozen=True)
class DebtOption:
    kind: str  # now | split | on_due
    schedule: tuple[tuple[date, Decimal], ...]
    lowest: Decimal
    lowest_date: date
    safe: bool


@dataclass(frozen=True)
class DebtPayoff:
    amount: Decimal
    options: tuple[DebtOption, ...]
    recommended: str
    assumptions: tuple[Assumption, ...] = ()


def debt_payoff(
    inp: EngineInput,
    amount: Decimal,
    due: date | None,
    *,
    n: int = 3,
    base: ForecastResult | None = None,
) -> DebtPayoff:
    """Pay a debt now, in n monthly parts, or on its due date: cash impact of each."""
    if amount <= 0:
        raise EngineError("debt amount must be positive")
    base = base or advisor_base(inp)
    safe = to_tiyin(base.safe_min)
    today = base.today
    assumptions: list[Assumption] = []
    if due is None:
        due = today + timedelta(days=30)
        assumptions.append(
            Assumption("due_date", "Qarz muddati noma'lum: 30 kun deb oldim", due.isoformat())
        )
    part = (amount / n).quantize(Decimal(1000), rounding=ROUND_CEILING)
    split = tuple(
        (add_months(today, j), part if j < n - 1 else amount - part * (n - 1)) for j in range(n)
    )
    assumptions.append(Assumption("n", f"Bo'lib to'lash: {n} oy", str(n)))
    opts = []
    for kind, sched in (
        ("now", ((today, amount),)),
        ("split", split),
        ("on_due", ((max(due, today), amount),)),
    ):
        arr = _after(base.close, _flows(base, sched))
        low, low_d = _low(base, arr)
        opts.append(DebtOption(kind, sched, low, low_d, _safe(arr, safe)))
    # the earliest safe option; if none is safe, the one that keeps the most cash
    rec = next((o.kind for o in opts if o.safe), max(opts, key=lambda o: o.lowest).kind)
    return DebtPayoff(amount, tuple(opts), rec, tuple(assumptions))


def payoff_order(
    inp: EngineInput,
    debts: Sequence[tuple[str, Decimal, date | None, bool]],
    base: ForecastResult | None = None,
) -> list[tuple[str, str]]:
    """Order: critical debts first, then smallest-first while paying now stays safe."""
    base = base or advisor_base(inp)
    safe = to_tiyin(base.safe_min)
    close = base.close
    order: list[tuple[str, str]] = []
    for name, amount, _due, critical in sorted(debts, key=lambda d: (not d[3], d[1])):
        arr = _after(close, _flows(base, ((base.today, amount),)))
        if critical or _safe(arr, safe):
            order.append((name, "now" if _safe(arr, safe) else "on_due"))
            if _safe(arr, safe):
                close = arr
        else:
            order.append((name, "on_due"))
    return order


# --- loans --------------------------------------------------------------------------------
@dataclass(frozen=True)
class LoanResult:
    rate: Decimal
    months: int
    amount: Decimal | None
    payment: Decimal | None
    max_safe_amount: Decimal
    max_safe_payment: Decimal
    dscr: Decimal | None  # monthly operating net cash / monthly payment
    monthly_operating_net: Decimal
    assumptions: tuple[Assumption, ...] = ()


def monthly_operating_net(base: ForecastResult) -> Decimal:
    """Average monthly trading net (sales - variable cost) minus the next 30 days' payments."""
    days = min(90, len(base.revenue) - 1)
    trading = from_tiyin(int((base.revenue[1 : days + 1] - base.variable_cost[1 : days + 1]).sum()))
    per_month = trading / Decimal(days) * DAYS_PER_MONTH
    end = base.today + timedelta(days=30)
    fixed = sum((o.amount for o in base.obligations if base.today < o.date <= end), Decimal(0))
    return (per_month - fixed).quantize(Decimal(1))


def loan_affordability(
    inp: EngineInput,
    rate: Decimal,
    months: int,
    amount: Decimal | None = None,
    base: ForecastResult | None = None,
) -> LoanResult:
    base = base or advisor_base(inp)
    safe = to_tiyin(base.safe_min)

    def safe_for(p: Decimal) -> bool:
        pay = annuity(p, rate, months)
        sched = tuple((add_months(base.today, j), pay) for j in range(1, months + 1))
        return _safe(_after(base.close, _flows(base, sched)), safe)

    lo, hi = Decimal(0), Decimal(2_000_000_000)
    if not safe_for(Decimal(1_000_000)):
        hi = Decimal(0)
    else:
        for _ in range(40):
            mid = ((lo + hi) / 2).quantize(Decimal(1))
            if mid <= lo:
                break
            if safe_for(mid):
                lo = mid
            else:
                hi = mid
        hi = (lo / STEP).to_integral_value(rounding=ROUND_FLOOR) * STEP
    net = monthly_operating_net(base)
    # the horizon sees only part of a long loan: also cap the payment at 2/3 of monthly net cash
    if months > ADVISOR_HORIZON_DAYS // 30 and net > 0:
        r = rate / Decimal(1200)
        cap_pay = net / DSCR_MIN
        cap = cap_pay * months if r == 0 else cap_pay * (1 - (1 + r) ** -months) / r
        hi = min(hi, (cap / STEP).to_integral_value(rounding=ROUND_FLOOR) * STEP)
    pay = annuity(amount, rate, months) if amount else None
    max_pay = annuity(hi, rate, months) if hi > 0 else Decimal(0)
    dscr = (net / pay).quantize(Decimal("0.01")) if pay else None
    return LoanResult(
        rate,
        months,
        amount,
        pay,
        hi,
        max_pay,
        dscr,
        net,
        (
            Assumption("rate", f"Kredit foizi: yiliga {rate}%", str(rate)),
            Assumption("months", f"Muddat: {months} oy", str(months)),
            Assumption(
                "dscr",
                "Kredit to'lovi oylik sof pulning 2/3 qismidan oshmasin",
                str(DSCR_MIN),
                editable=False,
            ),
        ),
    )


# --- investments --------------------------------------------------------------------------
@dataclass(frozen=True)
class PaybackCase:
    name: str
    monthly_net: Decimal
    payback_months: int | None
    roi_12m_pct: Decimal
    cumulative: tuple[Decimal, ...]  # month 0..life


@dataclass(frozen=True)
class InvestmentResult:
    cost: Decimal
    financing: str
    cases: tuple[PaybackCase, PaybackCase, PaybackCase]  # pessimistic, base, optimistic
    lowest: Decimal
    lowest_date: date
    safe: bool
    assumptions: tuple[Assumption, ...] = ()


def investment_payback(
    inp: EngineInput,
    cost: Decimal,
    *,
    extra_revenue_month: Decimal,
    margin: Decimal,
    extra_cost_month: Decimal = Decimal(0),
    financing: str = "cash",
    n: int | None = None,
    rate: Decimal | None = None,
    months: int | None = None,
    start: date | None = None,
    life_months: int = 36,
    spread: Decimal = Decimal("0.3"),
    assumptions: Sequence[Assumption] = (),
    base: ForecastResult | None = None,
) -> InvestmentResult:
    if cost <= 0:
        raise EngineError("cost must be positive")
    base = base or advisor_base(inp)
    start = start or base.today
    make, fin_assumptions = purchase_schedule(cost, financing, n=n, rate=rate, months=months)
    sched = make(start)
    if financing == "loan":
        upfront = Decimal(0)
    else:
        upfront = sum((a for d, a in sched if d <= start), Decimal(0))
    monthly_payments = {i: a for i, (d, a) in enumerate(sorted(sched)) if d > start}

    def case(name: str, rev_k: Decimal, cost_k: Decimal) -> PaybackCase:
        net = (extra_revenue_month * rev_k * margin - extra_cost_month * cost_k).quantize(
            Decimal(1)
        )
        cum = [-upfront]
        pays = sorted(monthly_payments.values())
        for m in range(1, life_months + 1):
            pay = pays[m - 1] if m - 1 < len(pays) else Decimal(0)
            cum.append(cum[-1] + net - pay)
        payback = next((m for m, v in enumerate(cum) if m > 0 and v >= 0), None)
        roi = (
            ((cum[min(12, life_months)] / cost) * 100).quantize(Decimal(1)) if cost else Decimal(0)
        )
        return PaybackCase(name, net, payback, roi, tuple(cum))

    lo_k, hi_k = 1 - spread, 1 + spread
    cases = (
        case("pessimistic", lo_k, hi_k),
        case("base", Decimal(1), Decimal(1)),
        case("optimistic", hi_k, lo_k),
    )
    # cash timeline: financing out, base monthly benefit in (spread over the month)
    flows = _flows(base, sched)
    daily = to_tiyin(cases[1].monthly_net) // 30
    s_idx = max(0, (start - base.today).days)
    flows[s_idx + 1 :] += daily
    arr = _after(base.close, flows)
    low, low_d = _low(base, arr)
    return InvestmentResult(
        cost,
        financing,
        cases,
        low,
        low_d,
        _safe(arr, to_tiyin(base.safe_min)),
        tuple([*assumptions, *fin_assumptions]),
    )


# --- growth, price, snapshot ----------------------------------------------------------------
@dataclass(frozen=True)
class GrowthResult:
    pct: Decimal
    months: int
    avg_month_revenue: Decimal
    extra_month: Decimal
    extra_day: Decimal
    extra_orders_day: int | None
    weekday_room: tuple[tuple[int, Decimal, Decimal], ...]  # (weekday, revenue/day, gap to best)
    lowest_before: Decimal
    lowest_after: Decimal
    cash_gain_horizon: Decimal  # extra cash by the end of the horizon
    assumptions: tuple[Assumption, ...] = ()


def avg_month_revenue(base: ForecastResult) -> Decimal:
    return (sum(base.weekday_revenue, Decimal(0)) / 7 * DAYS_PER_MONTH).quantize(Decimal(1))


def revenue_growth_target(
    inp: EngineInput,
    pct: Decimal,
    months: int = 3,
    avg_check: Decimal | None = None,
    base: ForecastResult | None = None,
) -> GrowthResult:
    if not Decimal(0) < pct <= Decimal(200):
        raise EngineError("pct must be within 0..200")
    base = base or advisor_base(inp)
    month = avg_month_revenue(base)
    extra_m = (month * pct / 100).quantize(Decimal(1))
    extra_d = (extra_m / DAYS_PER_MONTH).quantize(Decimal(1))
    orders = (
        int((extra_d / avg_check).to_integral_value(rounding=ROUND_CEILING)) if avg_check else None
    )
    best = max(base.weekday_revenue)
    room = sorted(
        ((w, r, best - r) for w, r in enumerate(base.weekday_revenue)), key=lambda x: -x[2]
    )[:3]
    close = _revenue_close(base, inp, pct)
    return GrowthResult(
        pct,
        months,
        month,
        extra_m,
        extra_d,
        orders,
        tuple(room),
        base.min_balance,
        from_tiyin(int(close.min())),
        from_tiyin(int(close[-1] - base.close[-1])),
        (Assumption("pct", f"Maqsad: savdo +{pct}%", str(pct)),),
    )


@dataclass(frozen=True)
class PriceResult:
    pct: Decimal
    volume_pct: Decimal
    margin_before: Decimal
    margin_after: Decimal
    gross_profit_month_delta: Decimal
    lowest_before: Decimal
    lowest_after: Decimal
    assumptions: tuple[Assumption, ...] = ()


def price_change(
    inp: EngineInput,
    pct: Decimal,
    volume_pct: Decimal = Decimal(0),
    base: ForecastResult | None = None,
) -> PriceResult:
    if not Decimal(-50) <= pct <= Decimal(100) or not Decimal(-90) <= volume_pct <= Decimal(200):
        raise EngineError("price change must be -50..100 %, volume -90..200 %")
    base = base or advisor_base(inp)
    vcr = base.variable_cost_ratio
    p, v = pct / 100, volume_pct / 100
    month = avg_month_revenue(base)
    before = month * (1 - vcr)
    after = month * (1 + p) * (1 + v) - month * vcr * (1 + v)
    delta = (after - before).quantize(Decimal(1))
    m_after = (1 - vcr / (1 + p)) if p > -1 else Decimal(0)
    flows = np.zeros(len(base.close), dtype=np.int64)
    flows[1:] += to_tiyin(delta) // 30
    arr = _after(base.close, flows)
    return PriceResult(
        pct,
        volume_pct,
        (1 - vcr) * 100,
        (m_after * 100).quantize(Decimal("0.1")),
        delta,
        base.min_balance,
        from_tiyin(int(arr.min())),
        (
            Assumption("pct", f"Narx o'zgarishi: {pct}%", str(pct)),
            Assumption("volume_pct", f"Sotuv hajmi o'zgarishi: {volume_pct}%", str(volume_pct)),
        ),
    )


@dataclass(frozen=True)
class Flag:
    text: str
    value: str


@dataclass(frozen=True)
class Snapshot:
    avg_month_revenue: Decimal
    avg_day_revenue: Decimal
    weekday_revenue: tuple[Decimal, ...]
    weakest_day: int
    strongest_day: int
    gross_margin_pct: Decimal
    fixed_costs: tuple[tuple[str, Decimal], ...]  # monthly obligations by title (next 30 days)
    top_categories: tuple[tuple[str, Decimal, Decimal | None], ...]  # (category, last month, mom %)
    energy_month: Decimal
    debts_total: Decimal
    upcoming: tuple[tuple[date, str, Decimal], ...]
    strengths: tuple[Flag, ...]
    weaknesses: tuple[Flag, ...]
    lowest: Decimal
    lowest_date: date
    revenue_mom_pct: Decimal | None = None
    extras: dict[str, Decimal] = field(default_factory=dict)


ENERGY_WORDS = ("gaz", "gas", "svet", "elektr", "energiya", "kommunal")


def business_snapshot(
    base: ForecastResult,
    *,
    month_categories: dict[str, Decimal],
    prev_month_categories: dict[str, Decimal],
    revenue_month: Decimal | None,
    revenue_prev_month: Decimal | None,
    debts_total: Decimal = Decimal(0),
) -> Snapshot:
    """Rule-based picture of the business: every flag carries its number."""
    wr = base.weekday_revenue
    avg_day = (sum(wr, Decimal(0)) / 7).quantize(Decimal(1))
    month = avg_month_revenue(base)
    weakest, strongest = (
        int(np.argmin([float(x) for x in wr])),
        int(np.argmax([float(x) for x in wr])),
    )
    margin = ((1 - base.variable_cost_ratio) * 100).quantize(Decimal("0.1"))
    end = base.today + timedelta(days=30)
    upcoming = tuple(
        sorted((o.date, o.title, o.amount) for o in base.obligations if base.today <= o.date <= end)
    )
    fixed: dict[str, Decimal] = {}
    for _, title, amount in upcoming:
        fixed[title] = fixed.get(title, Decimal(0)) + amount
    cats = []
    for c, v in sorted(month_categories.items(), key=lambda kv: -kv[1])[:5]:
        prev = prev_month_categories.get(c)
        mom = ((v - prev) / prev * 100).quantize(Decimal(1)) if prev else None
        cats.append((c, v, mom))
    energy = sum(
        (v for c, v in month_categories.items() if any(w in c.lower() for w in ENERGY_WORDS)),
        Decimal(0),
    )
    mom_rev = (
        ((revenue_month - revenue_prev_month) / revenue_prev_month * 100).quantize(Decimal("0.1"))
        if revenue_month and revenue_prev_month
        else None
    )
    gap = (
        ((wr[strongest] - wr[weakest]) / wr[strongest] * 100).quantize(Decimal(1))
        if wr[strongest]
        else Decimal(0)
    )
    strengths: list[Flag] = []
    weaknesses: list[Flag] = []
    if margin >= 50:
        strengths.append(Flag("Yalpi marja yuqori", f"{margin}%"))
    else:
        weaknesses.append(Flag("Yalpi marja past", f"{margin}%"))
    if base.min_balance >= base.safe_min:
        strengths.append(Flag("Kassa xavfsiz chegaradan pastga tushmaydi", str(base.min_balance)))
    else:
        weaknesses.append(Flag("Kassa xavfsiz chegaradan pastga tushadi", str(base.min_balance)))
    if mom_rev is not None and mom_rev > 0:
        strengths.append(Flag("Savdo o'tgan oydan o'sgan", f"+{mom_rev}%"))
    elif mom_rev is not None:
        weaknesses.append(Flag("Savdo o'tgan oydan kamaygan", f"{mom_rev}%"))
    strengths.append(Flag("Eng kuchli kun", str(strongest)))
    if gap >= 20:
        weaknesses.append(Flag("Eng zaif kun eng kuchli kundan past", f"{gap}%"))
    rising = [(c, m) for c, _, m in cats if m is not None and m >= 10]
    if rising:
        weaknesses.append(Flag(f'"{rising[0][0]}" xarajati o\'sgan', f"+{rising[0][1]}%"))
    if debts_total and month and debts_total / month >= Decimal("0.3"):
        weaknesses.append(
            Flag(
                "Qarzlar oylik savdoning katta qismi",
                f"{(debts_total / month * 100).quantize(Decimal(1))}%",
            )
        )
    return Snapshot(
        month,
        avg_day,
        tuple(wr),
        weakest,
        strongest,
        margin,
        tuple(fixed.items()),
        tuple(cats),
        energy,
        debts_total,
        upcoming,
        tuple(strengths[:3]),
        tuple(weaknesses[:3]),
        base.min_balance,
        base.min_date,
        mom_rev,
    )


def payback_months_ceil(cost: Decimal, monthly_net: Decimal) -> int | None:
    if monthly_net <= 0:
        return None
    return math.ceil(cost / monthly_net)
