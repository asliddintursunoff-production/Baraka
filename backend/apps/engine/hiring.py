"""Golden Q2 (hire_payback): does one more worker pay back? Recipe: golden/Q2_ishchi_olsam_oqlaydimi.md."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from .cfo import last_month

D0 = Decimal(0)
ROLE_ALIASES = {
    "ofitsiant": ("ofitsiant", "ofitsam", "ofitsiyant", "ofisiant", "zal xodim"),
    "oshpaz": ("oshpaz", "lavash usta", "povar"),
    "kassir": ("kassir",),
    "kuryer": ("kuryer", "dostavkachi"),
    "farrosh": ("farrosh", "uborshitsa"),
}
MARKET_SALARY = {
    "ofitsiant": Decimal(2_000_000),
    "oshpaz": Decimal(3_800_000),
    "kassir": Decimal(3_000_000),
    "kuryer": Decimal(2_500_000),
    "farrosh": Decimal(1_800_000),
}


def _d(x: Any) -> Decimal:
    try:
        return Decimal(str(x))
    except Exception:
        return D0


def role_of(text: str) -> str | None:
    t = text.lower()
    for role, words in ROLE_ALIASES.items():
        if any(w in t for w in words):
            return role
    return None


@dataclass
class Params:
    role: str = "ofitsiant"
    salary: Decimal | None = None
    sales_pct: Decimal = Decimal("0.003")
    official: bool = False
    uplift: Decimal = Decimal("0.04")  # waiter: +4 % average check in the hall
    onboarding: Decimal = Decimal(300_000)
    first_month_eff: Decimal = Decimal("0.5")
    kitchen_cap: Decimal = Decimal(90)
    cashier_cap: Decimal = Decimal(30)
    cashiers: int = 2
    courier_cap: Decimal = Decimal(450)
    bonus_pct: Decimal = Decimal("0.03")
    courier_orders: Decimal | None = None


@dataclass
class Hire:
    month: str
    role: str
    salary: Decimal
    salary_source: str
    sales_share: Decimal
    social_tax: Decimal
    meals: Decimal
    meal_dish: str
    cost: Decimal
    gain_revenue: Decimal
    gain_gp: Decimal
    net: Decimal
    payback_months: Decimal | None
    cumulative: list[Decimal]
    hall_revenue: Decimal
    hall_margin: Decimal
    hall_avg_check: Decimal
    breakeven_uplift: Decimal
    breakeven_hall_rev: Decimal
    hall_growth: Decimal
    months_to_breakeven: int | None
    sat_checks: Decimal
    weekday_checks: Decimal
    peak_checks: Decimal
    peak_label: str
    courier_orders: Decimal
    lost_days_recent: int
    last_lost_day: str | None
    alt_cost: Decimal
    alt_revenue: Decimal
    alt_gp: Decimal
    alt_net: Decimal
    alt_cumulative: list[Decimal]
    sat_threshold: Decimal
    hire_month: str | None
    months_labels: list[str]
    missing: list[str] = field(default_factory=list)

    def load(self, kind: str) -> Decimal:
        return {
            "sat": self.sat_checks / 90,
            "wk": self.weekday_checks / 90,
            "peak": self.peak_checks / 60,
            "courier": self.courier_orders / 450,
        }[kind]


UZ_MON = ["Yan", "Fev", "Mar", "Apr", "May", "Iyun", "Iyul", "Avg", "Sen", "Okt", "Noy", "Dek"]


def compute(s: dict[str, Any], p: Params | None = None) -> Hire:
    p = p or Params()
    m = last_month(s)
    det = s.get("details") or {}
    missing: list[str] = []
    chm = (det.get("channels") or {}).get("months") or {}
    cur = chm.get(m) or {}
    hall = next((v for k, v in cur.items() if "zal" in k.lower()), None)
    take = next((v for k, v in cur.items() if "olib" in k.lower()), None)
    hall_rev = _d(hall["revenue"]) if hall else D0
    hall_cost = _d(hall["cost"]) if hall else D0
    hall_margin = (hall_rev - hall_cost) / hall_rev if hall_rev else Decimal("0.7")
    take_rev = _d(take["revenue"]) if take else D0
    take_margin = (take_rev - _d(take["cost"])) / take_rev if take and take_rev else hall_margin
    if not hall:
        missing.append("Zal kanali bo'yicha sotuv (Sotuv 'Kanal')")
    # hall growth: monthly CAGR first -> last full month
    hall_hist = [
        (k, _d(v[next(n for n in v if "zal" in n.lower())]["revenue"]))
        for k, v in sorted(chm.items())
        if k <= m and any("zal" in n.lower() for n in v)
    ]
    growth = D0
    if len(hall_hist) >= 3 and hall_hist[0][1] > 0:
        growth = Decimal(
            str((float(hall_hist[-1][1] / hall_hist[0][1])) ** (1 / (len(hall_hist) - 1)) - 1)
        )
    # salary
    pay = (det.get("payroll") or {}).get(m) or {}
    same = [
        v
        for k, v in pay.items()
        if any(w in (k + " " + str(v[0])).lower() for w in ROLE_ALIASES.get(p.role, (p.role,)))
    ]
    if p.salary is not None:
        salary, src = p.salary, "siz aytgan"
    elif same:
        salary = sum((max(_d(v[5]) if len(v) > 5 else D0, _d(v[2])) for v in same), D0) / len(same)
        src = "shu lavozimdagi joriy oylik"
    else:
        salary, src = MARKET_SALARY.get(p.role, Decimal(2_500_000)), "bozor standarti (taxmin)"
    sales_share = (hall_rev * p.sales_pct).quantize(Decimal(1)) if p.role == "ofitsiant" else D0
    social = (salary * Decimal("0.12")) if p.official else D0
    # staff meals: 12 portions x the dish used for staff meals (Hisobdan chiqarish) or the cheapest main dish
    menu = det.get("menu") or {}
    wo = (det.get("writeoffs") or {}).get("items") or {}
    staff = [
        it[0]
        for items in wo.values()
        for it in items
        if len(it) > 4 and "xodim" in str(it[4]).lower()
    ]
    dish = staff[-1] if staff and staff[-1] in menu else None
    if dish is None and menu:
        mains = {
            n: d
            for n, d in menu.items()
            if not any(
                w in (n + str(d.get("category", ""))).lower()
                for w in ("ichimlik", "choy", "sous", "kofe", "fri", "sharbat")
            )
        }
        dish = min(mains or menu, key=lambda n: _d(menu[n].get("cost")))
    meals = (Decimal(12) * _d(menu.get(dish, {}).get("cost"))).quantize(Decimal(1)) if dish else D0
    cost = salary + sales_share + social + meals
    # load
    sd = det.get("smena_days") or []
    last_d = date.fromisoformat(sd[-1][0]) if sd else None
    since = None
    if last_d:
        m0 = last_d.month - 2
        since = date(last_d.year + (m0 - 1) // 12, (m0 - 1) % 12 + 1, 1)
    recent = [
        (date.fromisoformat(d), _d(c), n)
        for d, c, n in sd
        if since and date.fromisoformat(d) >= since
    ]
    sat = [c for d, c, _ in recent if d.weekday() == 5]
    wk = [c for d, c, _ in recent if d.weekday() < 4]
    sat_avg = sum(sat, D0) / len(sat) if sat else D0
    wk_avg = sum(wk, D0) / len(wk) if wk else D0
    lost = [
        d
        for d, n in ((date.fromisoformat(r[0]), r[2]) for r in sd)
        if "ulgurm" in n.lower() or "navbat" in n.lower()
    ]
    lost_recent = sum(1 for d in lost if last_d and (last_d - d).days < 92)
    hr = (det.get("hourly") or {}).get("cells") or {}
    peak_k, peak = max(
        ((k, _d(v[0]) / _d(v[1])) for k, v in hr.items() if _d(v[1])),
        key=lambda kv: kv[1],
        default=("", D0),
    )
    days = ["dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba"]
    peak_label = (
        f"{days[int(peak_k.split('|')[0])]} {int(peak_k.split('|')[1]):02d}:00" if peak_k else "—"
    )
    courier_orders = p.courier_orders if p.courier_orders is not None else D0
    # benefit mechanism per role
    avg_check_all = D0
    checks = _d((s.get("journals") or {}).get("checks", {}).get(m))
    if checks:
        avg_check_all = _d((s.get("months") or {}).get(m, {}).get("revenue")) / checks
    if p.role == "ofitsiant":
        gain_rev = hall_rev * p.uplift
        gain_gp = gain_rev * hall_margin
    elif p.role == "oshpaz":
        lost_checks = (
            Decimal(lost_recent) / 3 * 15
        )  # ~15 checks lost per 'ulgurmadi' day, per month
        gain_rev = lost_checks * avg_check_all
        gain_gp = gain_rev * hall_margin
    elif p.role == "kassir":
        over = max(D0, peak - p.cashier_cap * p.cashiers * Decimal("0.75"))
        gain_rev = over * 4 * 4 * avg_check_all  # peak hours/week x weeks
        gain_gp = gain_rev * hall_margin
    elif p.role == "kuryer":
        over = max(D0, courier_orders - p.courier_cap * Decimal("0.7"))
        gain_rev = over * avg_check_all
        gain_gp = gain_rev * hall_margin
    else:
        gain_rev = gain_gp = D0
    net = gain_gp - cost
    cum, acc = [], D0
    for i in range(12):
        acc += (
            (gain_gp * (p.first_month_eff if i == 0 else 1))
            - cost
            - (p.onboarding if i == 0 else D0)
        )
        cum.append(acc)
    payback = (p.onboarding / net).quantize(Decimal("0.1")) if net > 0 else None
    be_uplift = cost / (hall_rev * hall_margin) if hall_rev and hall_margin else D0
    be_hall = cost / (p.uplift * hall_margin) if hall_margin else D0
    months_be = (
        round(math.log(float(be_hall / hall_rev)) / math.log(1 + float(growth)))
        if hall_rev and growth > 0 and be_hall > hall_rev
        else None
    )
    # alternative: cashier upsell bonus on hall + takeaway
    alt_rev = (hall_rev + take_rev) * p.uplift
    alt_gp = hall_rev * p.uplift * hall_margin + take_rev * p.uplift * take_margin
    alt_cost = (alt_rev * p.bonus_pct).quantize(Decimal(1))
    alt_net = alt_gp - alt_cost
    acum, a = [], D0
    for i in range(12):
        a += alt_net * (p.first_month_eff if i == 0 else 1)
        acum.append(a)
    sat_thr = Decimal(int(p.kitchen_cap * Decimal("0.95")))
    hire_month = None
    if sat_avg and growth > 0 and last_d:
        k = math.log(float(sat_thr / sat_avg)) / math.log(1 + float(growth))
        mm = last_d.month - 1 + math.ceil(k)
        hire_month = f"{UZ_MON[mm % 12]} {last_d.year + mm // 12}"
    start = last_d.month if last_d else int(m[5:7])  # chart starts the month after the data
    labels = [UZ_MON[(start + i) % 12] for i in range(12)]
    return Hire(
        m,
        p.role,
        salary,
        src,
        sales_share,
        social,
        meals,
        dish or "",
        cost,
        gain_rev,
        gain_gp,
        net,
        payback,
        cum,
        hall_rev,
        hall_margin,
        (hall_rev / _d(hall.get("rows", 0))) if False else D0,
        be_uplift,
        be_hall,
        growth,
        months_be,
        sat_avg,
        wk_avg,
        peak,
        peak_label,
        courier_orders,
        lost_recent,
        lost[-1].isoformat() if lost else None,
        alt_cost,
        alt_rev,
        alt_gp,
        alt_net,
        acum,
        sat_thr,
        hire_month,
        labels,
        missing,
    )
