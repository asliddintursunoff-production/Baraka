"""CFO analysis modules (pure Python, Decimal). Input: a financial-model source summary
(apps.ingestion.finmodel.summarize): journal breakdowns + the workbook's own report rows.

Accrual figures (food cost, EBITDA, net profit, plan) come from the workbook's P&L and
plan-vs-fact sheets; cash figures come from the journals. Every function returns numbers only.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_CEILING, Decimal
from typing import Any

D0 = Decimal(0)
# P&L lines that move with sales (contribution margin); everything else in opex is fixed
VARIABLE_PL = (
    "mahsulot tannarxi",
    "agregator komissiyasi",
    "bank va to'lov komissiyalari",
    "xo'jalik va qadoqlash",
)
TURNOVER_TAX = "aylanma solig'i"


def _d(x: Any) -> Decimal:
    try:
        return Decimal(str(x)) if x not in (None, "") else D0
    except Exception:
        return D0


def pl_value(s: dict[str, Any], prefix: str, month: str) -> Decimal:
    """A P&L row (by label prefix) for one month (ISO 'YYYY-MM-01')."""
    for label, by_month in s.get("reports", {}).get("pl", {}).items():
        if label.startswith(prefix):
            return _d(by_month.get(month))
    return D0


def plan_fact(s: dict[str, Any], kind: str, prefix: str, month: str) -> Decimal:
    for label, by_month in s.get("reports", {}).get("plan_fact", {}).items():
        if label.startswith(f"{kind}:{prefix}"):
            return _d(by_month.get(month))
    return D0


def last_month(s: dict[str, Any]) -> str:
    """The last COMPLETE month with data (ISO): a month whose data stops before its last
    days (e.g. 21-Nov) is partial, so analysis uses the previous month."""
    last = date.fromisoformat(str(s["last_date"])[:10])
    if last.day >= calendar.monthrange(last.year, last.month)[1] - 1:
        return last.replace(day=1).isoformat()
    prev = last.replace(day=1) - timedelta(days=1)
    return prev.replace(day=1).isoformat()


def days_in(month: str, s: dict[str, Any] | None = None) -> int:
    if s:
        n = s.get("journals", {}).get("smena_days", {}).get(month)
        if n:
            return int(n)
    d = date.fromisoformat(month)
    return calendar.monthrange(d.year, d.month)[1]


# --- 6. break-even ------------------------------------------------------------------------
@dataclass(frozen=True)
class BreakEven:
    month: str
    revenue: Decimal
    variable: Decimal
    cm_ratio: Decimal
    fixed: Decimal
    principal: Decimal
    avg_check: Decimal
    checks_per_day: Decimal
    be_revenue: Decimal
    be_checks_per_day: Decimal
    cash_be_checks_per_day: Decimal
    days: int


def break_even(s: dict[str, Any], month: str | None = None) -> BreakEven:
    m = month or last_month(s)
    rev = pl_value(s, "sof tushum", m)
    variable = sum((pl_value(s, p, m) for p in VARIABLE_PL), D0) + pl_value(s, TURNOVER_TAX, m)
    if not pl_value(s, TURNOVER_TAX, m):
        variable += plan_fact(s, "fakt", "soliqlar", m)
    opex = pl_value(s, "jami operatsion xarajatlar", m)
    fixed = (
        opex
        - sum((pl_value(s, p, m) for p in VARIABLE_PL[1:]), D0)
        + pl_value(s, "foiz xarajatlari", m)
    )
    principal = _d((s.get("loan") or {}).get("principal_monthly"))
    checks = _d(s.get("journals", {}).get("checks", {}).get(m))
    days = days_in(m, s)
    cm = (rev - variable) / rev if rev else D0
    avg_check = rev / checks if checks else D0
    be_rev = fixed / cm if cm > 0 else D0
    per_day = Decimal(days)
    be_checks = be_rev / avg_check / per_day if avg_check else D0
    cash_be = (fixed + principal) / cm / avg_check / per_day if cm > 0 and avg_check else D0
    return BreakEven(
        m,
        rev,
        variable,
        cm,
        fixed,
        principal,
        avg_check,
        checks / per_day if days else D0,
        be_rev,
        be_checks,
        cash_be,
        days,
    )


# --- 7. stress test -------------------------------------------------------------------------
@dataclass(frozen=True)
class Stress:
    drops: tuple[tuple[int, Decimal], ...]  # (drop %, monthly cash result)
    max_drop_pct: Decimal  # largest sales drop before the month loses cash
    base_result: Decimal


def stress_test(
    s: dict[str, Any], drops: tuple[int, ...] = (10, 20, 30, 40), month: str | None = None
) -> Stress:
    be = break_even(s, month)
    burden = be.fixed + be.principal
    margin = be.revenue * be.cm_ratio
    rows = tuple((d, (be.revenue * (1 - Decimal(d) / 100) * be.cm_ratio - burden)) for d in drops)
    max_drop = (1 - burden / margin) * 100 if margin > 0 else D0
    return Stress(rows, max_drop, margin - burden)


# --- 1. cash sources ------------------------------------------------------------------------
@dataclass(frozen=True)
class CashSources:
    first_month: str
    last_month: str
    opening: Decimal
    operating: Decimal
    investing: Decimal
    financing: Decimal
    other: Decimal
    owner_in: Decimal
    loan_in: Decimal
    loan_repaid: Decimal
    interest: Decimal
    dividend: Decimal
    closing: Decimal
    external_share: Decimal  # owner + loan money as a share of closing cash


def cash_sources(s: dict[str, Any], opening: Decimal) -> CashSources:
    acts = s.get("journals", {}).get("activities", {})
    tot: dict[str, Decimal] = {}
    for f in acts.values():
        for k, v in f.items():
            tot[k] = tot.get(k, D0) + _d(v)
    g = tot.get
    closing = (
        opening
        + (g("operating") or D0)
        + (g("investing") or D0)
        + (g("financing") or D0)
        + (g("other") or D0)
    )
    ext = (g("owner_in") or D0) + (g("loan_in") or D0)
    months = sorted(acts)
    return CashSources(
        months[0] if months else "",
        months[-1] if months else "",
        opening,
        g("operating") or D0,
        g("investing") or D0,
        g("financing") or D0,
        g("other") or D0,
        g("owner_in") or D0,
        g("loan_in") or D0,
        g("loan_repaid") or D0,
        g("interest") or D0,
        g("dividend") or D0,
        closing,
        ext / closing if closing > 0 else D0,
    )


# --- 2. net position ------------------------------------------------------------------------
@dataclass(frozen=True)
class NetPosition:
    month: str
    cash: Decimal
    receivables: tuple[tuple[str, Decimal], ...]
    payables: tuple[tuple[str, Decimal], ...]
    loan: Decimal
    net_cash: Decimal
    fixed_monthly: Decimal
    months_covered: Decimal


def _balans(s: dict[str, Any], prefix: str, month: str) -> Decimal:
    for label, by_month in s.get("reports", {}).get("balans", {}).items():
        if label.startswith(prefix):
            return _d(by_month.get(month))
    return D0


def net_position(s: dict[str, Any], month: str | None = None) -> NetPosition:
    m = month or last_month(s)
    cash = _d(s["months"].get(m, {}).get("cash_end"))
    recv = tuple(
        (b["name"], -_d(b["balance"])) for b in s.get("balances", []) if _d(b["balance"]) < 0
    )
    suppliers = sum(
        (
            _d(b["balance"])
            for b in s.get("balances", [])
            if _d(b["balance"]) > 0 and str(b.get("type", "")).lower().startswith("yetkazib")
        ),
        D0,
    )
    pay = [
        ("Yetkazib beruvchilar", suppliers or _balans(s, "yetkazib beruvchilarga qarz", m)),
        ("Soliq", _balans(s, "soliq va byudjet oldidagi qarz", m)),
        ("Ish haqi", _balans(s, "ish haqi bo'yicha qarz", m)),
    ]
    payables = tuple((n, v) for n, v in pay if v)
    loan = _d((s.get("loan") or {}).get("balance"))
    be = break_even(s, m)
    fixed = be.fixed + be.principal
    net = cash + sum((v for _, v in recv), D0) - sum((v for _, v in payables), D0) - loan
    return NetPosition(m, cash, recv, payables, loan, net, fixed, cash / fixed if fixed else D0)


# --- 5. KPI scorecard -----------------------------------------------------------------------
@dataclass(frozen=True)
class Kpi:
    key: str
    label: str
    value: Decimal  # ratio (0.362) or amount
    target: Decimal | None
    status: str  # good | problem | watch
    gap_money: Decimal = D0  # monthly money above target (costs)


@dataclass(frozen=True)
class Scorecard:
    month: str
    kpis: tuple[Kpi, ...]
    overall: str


def kpi_scorecard(s: dict[str, Any], month: str | None = None) -> Scorecard:
    m = month or last_month(s)
    rev = pl_value(s, "sof tushum", m)
    t = s.get("reports", {}).get("kpi_targets", {})
    food = pl_value(s, "mahsulot tannarxi", m) / rev if rev else D0
    labor = (
        (
            pl_value(s, "ish haqi", m)
            + pl_value(s, "ijtimoiy soliq", m)
            + pl_value(s, "xodimlar ovqati", m)
        )
        / rev
        if rev
        else D0
    )
    rent = pl_value(s, "ijara", m) / rev if rev else D0
    ebitda = pl_value(s, "ebitda", m) / rev if rev else D0
    net = pl_value(s, "sof foyda", m) / rev if rev else D0
    op_cash = _d(s.get("journals", {}).get("activities", {}).get(m, {}).get("operating"))
    checks, plan_checks = (
        plan_fact(s, "fakt", "cheklar soni", m),
        plan_fact(s, "reja", "cheklar soni", m),
    )

    def cost(key: str, label: str, v: Decimal, tk: str) -> Kpi:
        target = _d(t.get(tk)) or None
        if target is None:
            return Kpi(key, label, v, None, "watch")
        status = "good" if v <= target else "problem"
        return Kpi(key, label, v, target, status, max(D0, (v - target) * rev))

    kpis = [
        cost("food", "Food cost", food, "food cost"),
        cost("labor", "Labor cost", labor, "labor cost"),
        cost("prime", "Prime cost", food + labor, "prime cost"),
        cost("rent", "Ijara", rent, "ijara"),
        Kpi(
            "ebitda", "EBITDA marja", ebitda, None, "good" if ebitda >= Decimal("0.15") else "watch"
        ),
        Kpi("net", "Sof marja", net, None, "good" if net > 0 else "problem"),
        Kpi("cash", "Operatsion pul oqimi", op_cash, None, "good" if op_cash > 0 else "problem"),
        Kpi(
            "flow",
            "Mijozlar oqimi (cheklar rejaga nisbatan)",
            (checks / plan_checks - 1) if plan_checks else D0,
            D0,
            "watch" if plan_checks and checks < plan_checks else "good",
        ),
    ]
    problems = sum(1 for k in kpis if k.status == "problem")
    overall = (
        "Yaxshi"
        if problems == 0
        else "Muammoli"
        if problems >= 2
        else "Yaxshi, lekin bitta muammo bor"
    )
    return Scorecard(m, tuple(kpis), overall)


# --- 4. plan vs actual ----------------------------------------------------------------------
PLAN_LINES = (
    ("cheklar soni", "Cheklar soni", "count", 1),
    ("o'rtacha chek", "O'rtacha chek", "money", 1),
    ("sof tushum", "Sof tushum", "money", 1),
    ("mahsulot tannarxi", "Mahsulot tannarxi (food cost)", "money", -1),
    ("ish haqi", "Ish haqi + ijtimoiy soliq", "money", -1),
    ("ijara", "Ijara", "money", -1),
    ("kommunal", "Kommunal xizmatlar", "money", -1),
    ("marketing", "Marketing", "money", -1),
    ("agregator komissiyasi", "Agregator komissiyasi", "money", -1),
    ("boshqa operatsion", "Boshqa operatsion xarajatlar", "money", -1),
    ("ebitda", "EBITDA", "money", 1),
    ("sof foyda", "Sof foyda", "money", 1),
)


@dataclass(frozen=True)
class PlanLine:
    key: str
    label: str
    plan: Decimal
    fact: Decimal
    diff: Decimal
    diff_pct: Decimal
    favourable: bool
    unit: str


@dataclass(frozen=True)
class PlanVsActual:
    month: str
    lines: tuple[PlanLine, ...]
    worst: tuple[PlanLine, ...]  # top-3 unfavourable money variances
    ytd_checks_pct: Decimal


def plan_vs_actual(s: dict[str, Any], month: str | None = None) -> PlanVsActual:
    m = month or last_month(s)
    lines = []
    for key, label, unit, sign in PLAN_LINES:
        p, f = plan_fact(s, "reja", key, m), plan_fact(s, "fakt", key, m)
        diff = f - p
        lines.append(
            PlanLine(key, label, p, f, diff, diff / p if p else D0, diff * sign >= 0, unit)
        )
    worst = tuple(
        sorted(
            (x for x in lines if not x.favourable and x.unit == "money"), key=lambda x: -abs(x.diff)
        )[:3]
    )
    ytd_p = ytd_f = D0
    for label, by_month in s.get("reports", {}).get("plan_fact", {}).items():
        if label.startswith("reja:cheklar soni"):
            ytd_p = sum((_d(v) for k, v in by_month.items() if k <= m), D0)
        if label.startswith("fakt:cheklar soni"):
            ytd_f = sum((_d(v) for k, v in by_month.items() if k <= m), D0)
    return PlanVsActual(m, tuple(lines), worst, (ytd_f / ytd_p - 1) if ytd_p else D0)


# --- 3. driver decomposition ----------------------------------------------------------------
@dataclass(frozen=True)
class Drivers:
    month: str
    prev_month: str
    revenue: Decimal
    prev_revenue: Decimal
    checks: Decimal
    prev_checks: Decimal
    avg_check: Decimal
    prev_avg_check: Decimal
    effect_checks: Decimal  # revenue change from the number of checks
    effect_avg_check: Decimal  # revenue change from the average check
    weekday_checks: tuple[tuple[int, Decimal], ...]
    channels: tuple[tuple[str, Decimal, Decimal], ...] = field(
        default=()
    )  # (channel, revenue, after commission)


_UZ_MONTHS = ("yan", "fev", "mar", "apr", "may", "iyun", "iyul", "avg", "sen", "okt", "noy", "dek")


def norm_month(s: dict[str, Any], month: Any) -> str:
    """Model-given month ("2026-10", "2026-10-01", "oktyabr", 10, None) -> "YYYY-MM-01"."""
    lm = last_month(s)
    if month is None or month == "":
        return lm
    txt = str(month).strip().lower()
    if len(txt) >= 7 and txt[:4].isdigit() and txt[5:7].isdigit():
        return f"{txt[:4]}-{txt[5:7]}-01"
    n = (
        int(txt)
        if txt.isdigit()
        else next((i + 1 for i, w in enumerate(_UZ_MONTHS) if txt.startswith(w)), 0)
    )
    if not 1 <= n <= 12:
        return lm
    y = int(lm[:4]) if n <= int(lm[5:7]) else int(lm[:4]) - 1
    return f"{y}-{n:02d}-01"


def driver_decomposition(s: dict[str, Any], month: Any = None) -> Drivers:
    m = norm_month(s, month)
    d = date.fromisoformat(m)
    pm = date(d.year - (d.month == 1), (d.month - 2) % 12 + 1, 1).isoformat()
    rev, prev = pl_value(s, "sof tushum", m), pl_value(s, "sof tushum", pm)
    ch = s.get("journals", {}).get("checks", {})
    c, pc = _d(ch.get(m)), _d(ch.get(pm))
    ac, pac = (rev / c if c else D0), (prev / pc if pc else D0)
    wd = tuple(
        sorted((int(k), _d(v)) for k, v in s.get("journals", {}).get("weekday_checks", {}).items())
    )
    agg_comm = pl_value(s, "agregator komissiyasi", m)
    channels = tuple(
        (
            name,
            pl_value(s, key, m),
            pl_value(s, key, m) - (agg_comm if key.startswith("agregatorlar") else D0),
        )
        for key, name in (
            ("zal savdosi", "Zal"),
            ("olib ketish", "Olib ketish"),
            ("o'z dostavka", "O'z dostavka"),
            ("agregatorlar yandex", "Agregatorlar"),
        )
    )
    return Drivers(m, pm, rev, prev, c, pc, ac, pac, (c - pc) * pac, (ac - pac) * c, wd, channels)


# --- 8. debt schedule -----------------------------------------------------------------------
@dataclass(frozen=True)
class DebtSchedule:
    balance: Decimal
    rate_pct: Decimal
    principal_monthly: Decimal
    months_left: int
    payoff_month: str
    remaining_interest: Decimal
    rows: tuple[
        tuple[str, Decimal, Decimal, Decimal], ...
    ]  # (month, principal, interest, balance after)


def debt_schedule(s: dict[str, Any], horizon_months: int = 24) -> DebtSchedule | None:
    loan = s.get("loan")
    if not loan:
        return None
    bal, rate, principal = (
        _d(loan["balance"]),
        _d(loan.get("rate_pct")) / 1200,
        _d(loan["principal_monthly"]),
    )
    if principal <= 0 or bal <= 0:
        return None
    months_left = int((bal / principal).to_integral_value(rounding=ROUND_CEILING))
    m = date.fromisoformat(last_month(s))
    rows = []
    total_interest = D0
    b = bal
    for k in range(1, months_left + 1):
        y, mo = divmod(m.month - 1 + k, 12)
        when = date(m.year + y, mo + 1, 1).isoformat()
        interest = (b * rate).quantize(Decimal(1))
        pay = min(principal, b)
        b -= pay
        total_interest += interest
        if k <= horizon_months:
            rows.append((when, pay, interest, b))
        last = when
    return DebtSchedule(
        bal, _d(loan.get("rate_pct")), principal, months_left, last, total_interest, tuple(rows)
    )
