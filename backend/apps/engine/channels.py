"""Golden Q1 (channel_economics): aggregators vs own delivery, per 100 000 so'm, scenarios.

Pure Python + Decimal, input = workbook summary dict. Recipe: golden/Q1_agregator_vs_ozdostavka.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .cfo import last_month

D0 = Decimal(0)
H = Decimal(100_000)


def _d(x: Any) -> Decimal:
    try:
        return Decimal(str(x))
    except Exception:
        return D0


@dataclass
class Channel:
    name: str
    kind: str  # aggregator | own
    revenue: Decimal
    cost: Decimal  # ingredients (masalliq)
    commission: Decimal  # aggregator commission, or courier + fuel for own delivery
    packaging: Decimal
    orders: Decimal
    orders_estimated: bool

    @property
    def profit(self) -> Decimal:
        return self.revenue - self.cost - self.commission - self.packaging

    def per100k(self, part: Decimal) -> Decimal:
        return (part / self.revenue * H) if self.revenue else D0

    @property
    def keep100k(self) -> Decimal:
        return self.per100k(self.profit)

    @property
    def avg_check(self) -> Decimal:
        return self.revenue / self.orders if self.orders else D0

    @property
    def rate(self) -> Decimal:
        return self.commission / self.revenue if self.revenue else D0


@dataclass
class Params:
    shift_pct: Decimal = Decimal("0.30")
    discount_pct: Decimal = Decimal("0.05")
    fuel_per_order: Decimal = Decimal(6000)
    markup_pct: Decimal = Decimal("0.08")
    markup_drop_pct: Decimal = Decimal("0.05")
    capacity: Decimal = Decimal(450)
    packaging_rate: Decimal = Decimal(
        "0.022"
    )  # recipe default; the file's Kassa ratio is shown as a check
    couriers: int = 1
    exit_only: str | None = None  # "uzum" / "yandex": scenario of leaving one aggregator
    orders: dict[str, Decimal] = field(default_factory=dict)


@dataclass
class Scenario:
    key: str
    title: str
    what: str
    delta: Decimal
    risk: str


@dataclass
class ChannelEconomics:
    month: str
    channels: list[Channel]
    courier_cost: Decimal
    fuel: Decimal
    packaging_rate: Decimal
    packaging_check: Decimal
    scenarios: list[Scenario]
    own_plan: Channel | None
    load_now: Decimal
    load_plan: Decimal
    orders_now: Decimal
    orders_plan: Decimal
    receivables: dict[str, Decimal]
    receivables_history: list[tuple[str, Decimal]]
    net_profit: Decimal
    params: Params
    missing: list[str] = field(default_factory=list)

    @property
    def aggregators(self) -> list[Channel]:
        return [c for c in self.channels if c.kind == "aggregator"]

    @property
    def own(self) -> Channel | None:
        return next((c for c in self.channels if c.kind == "own"), None)

    @property
    def best(self) -> Scenario:
        return next(s for s in self.scenarios if s.key == "both")


def _is_own(name: str) -> bool:
    n = name.lower().replace("‘", "'").replace("ʻ", "'")
    return "dostavka" in n or "yetkaz" in n


def compute(
    s: dict[str, Any], params: Params | None = None, month: str | None = None
) -> ChannelEconomics:
    p = params or Params()
    m = month or last_month(s)
    det = s.get("details") or {}
    chm = ((det.get("channels") or {}).get("months") or {}).get(m) or {}
    j = s.get("journals") or {}
    out_items = (j.get("outflow_items") or {}).get(m) or {}
    missing: list[str] = []
    fuel = sum((_d(v) for k, v in out_items.items() if "taksi" in k.lower()), D0)
    qadoq = sum((_d(v) for k, v in out_items.items() if "qadoq" in k.lower()), D0)
    pay = (det.get("payroll") or {}).get(m) or {}
    couriers = [
        v for k, v in pay.items() if "kuryer" in (k + " " + str(v[0]) + " " + str(v[1])).lower()
    ]
    courier_cost = sum((max(_d(v[5]) if len(v) > 5 else D0, _d(v[2])) for v in couriers), D0)
    if not couriers:
        missing.append("kuryer oyligi (Ish haqi varag'ida 'Kuryer')")
    total_rev = sum((_d(v["revenue"]) for v in chm.values()), D0)
    hall_rev = sum((_d(v["revenue"]) for k, v in chm.items() if "zal" in k.lower()), D0)
    pack_check = (
        (qadoq / (total_rev - hall_rev)).quantize(Decimal("0.0001"), ROUND_HALF_UP)
        if total_rev - hall_rev > 0 and qadoq
        else D0
    )
    pack_rate = p.packaging_rate
    checks = _d((j.get("checks") or {}).get(m))
    month_rev = _d((s.get("months") or {}).get(m, {}).get("revenue")) or total_rev
    avg_check = month_rev / checks if checks else D0
    chans: list[Channel] = []
    for name, v in chm.items():
        rev, com = _d(v["revenue"]), _d(v["commission"])
        if com > 0:
            kind = "aggregator"
        elif _is_own(name):
            kind = "own"
        else:
            continue
        given = next(
            (o for k, o in p.orders.items() if name.lower().startswith(k.lower()[:3])), None
        )
        orders = (
            Decimal(given)
            if given is not None
            else ((rev / avg_check).quantize(Decimal(1)) if avg_check else D0)
        )
        c = Channel(name, kind, rev, _d(v["cost"]), com, (rev * pack_rate), orders, given is None)
        if kind == "own":
            c.commission = courier_cost + fuel
        chans.append(c)
    aggs = [c for c in chans if c.kind == "aggregator"]
    own = next((c for c in chans if c.kind == "own"), None)
    agg_profit = sum((c.profit for c in aggs), D0)

    def markup(c: Channel, k: Decimal = Decimal(1)) -> Decimal:
        """Profit of aggregator channel c with +markup price, -drop volume, scaled by k."""
        vol = (1 - p.markup_drop_pct) * k
        rev = c.revenue * (1 + p.markup_pct) * vol
        return rev - c.cost * vol - rev * c.rate - rev * pack_rate

    scen: list[Scenario] = []
    scen.append(
        Scenario(
            "exit",
            "Agregatorlardan chiqish",
            "Yandex + Uzum'ni o'chirish",
            -agg_profit,
            "Mijozlarning ko'pi qaytmaydi",
        )
    )
    own_plan = None
    orders_moved = D0
    if own is not None and aggs:
        moved_rev = sum((c.revenue for c in aggs), D0) * p.shift_pct * (1 - p.discount_pct)
        moved_cost = sum((c.cost for c in aggs), D0) * p.shift_pct
        orders_moved = (sum((c.orders for c in aggs), D0) * p.shift_pct).quantize(Decimal(1))
        extra_courier = (
            courier_cost / len(couriers) * (p.couriers - 1) if couriers and p.couriers > 1 else D0
        )
        own_plan = Channel(
            own.name + " (reja)",
            "own",
            own.revenue + moved_rev,
            own.cost + moved_cost,
            own.commission + p.fuel_per_order * orders_moved + extra_courier,
            (own.revenue + moved_rev) * pack_rate,
            own.orders + orders_moved,
            own.orders_estimated,
        )
        d_own = own_plan.profit - own.profit
        s1 = d_own - agg_profit * p.shift_pct
        s2 = sum((markup(c) - c.profit for c in aggs), D0)
        both = d_own + sum((markup(c, 1 - p.shift_pct) - c.profit for c in aggs), D0)
        scen += [
            Scenario(
                "shift",
                f"{int(p.shift_pct * 100)}% mijozni o'zimizga ({int(p.discount_pct * 100)}% chegirma)",
                f"Agregator buyurtmalarining {int(p.shift_pct * 100)}% (~{int(orders_moved)} ta) ni chegirma bilan Telegram/sayt orqali olish",
                s1,
                "Kam",
            ),
            Scenario(
                "markup",
                f"Agregatorda narx +{int(p.markup_pct * 100)}%",
                f"Yandex/Uzum menyusida narx {int(p.markup_pct * 100)}% yuqori",
                s2,
                f"Buyurtmalar ~{int(p.markup_drop_pct * 100)}% kamayishi mumkin",
            ),
            Scenario("both", "1 + 2 birga (tavsiya)", "Ikkalasi", both, "Kam"),
        ]
    else:
        if own is None:
            missing.append("o'z dostavka kanali (Sotuv 'Kanal' ustunida)")
        scen.append(Scenario("both", "Hozirgi holat", "—", D0, "—"))
    if p.exit_only:
        ex = [c for c in aggs if p.exit_only in c.name.lower()]
        if ex:
            c = ex[0]
            mig = Decimal("0.4")  # 40 % of its customers move to own delivery with the discount
            rev = c.revenue * mig * (1 - p.discount_pct)
            gain = rev - c.cost * mig - p.fuel_per_order * (c.orders * mig) - rev * pack_rate
            scen.insert(
                1,
                Scenario(
                    "exit_one",
                    f"{c.name}'dan chiqish",
                    f"{c.name}'ni o'chirish, mijozlarning 40% i o'zimizga o'tadi",
                    gain - c.profit,
                    "Shu kanal mijozlarining ko'pi ketadi",
                ),
            )
    cap = p.capacity * p.couriers
    bal = (det.get("counterparties") or []) or (s.get("balances") or [])
    aggs_cp = [
        b
        for b in bal
        if "agregator" in str(b.get("type", "")).lower()
        or any(w in b["name"].lower() for w in ("yandex", "uzum"))
    ]

    def saldo(b: dict[str, Any], month: str) -> Decimal:
        return _d((b.get("months") or {}).get(month, b.get("balance")))

    recv = {b["name"]: -saldo(b, m) for b in aggs_cp if saldo(b, m) < 0}
    months_all = sorted({k for b in aggs_cp for k in (b.get("months") or {}) if k <= m})
    hist = [(k, sum((-saldo(b, k) for b in aggs_cp if saldo(b, k) < 0), D0)) for k in months_all]
    if not hist:
        hist_row = ((s.get("reports") or {}).get("balans") or {}).get(
            "mijozlar va agregatorlar qarzi"
        ) or {}
        hist = [(k, _d(v)) for k, v in sorted(hist_row.items()) if k <= m and _d(v) > 0]
    net = _d(((s.get("reports") or {}).get("pl") or {}).get("sof foyda", {}).get(m))
    return ChannelEconomics(
        m,
        chans,
        courier_cost,
        fuel,
        pack_rate,
        pack_check,
        scen,
        own_plan,
        (own.orders / cap) if own and cap else D0,
        (own_plan.orders / cap) if own_plan and cap else D0,
        own.orders if own else D0,
        own_plan.orders if own_plan else D0,
        recv,
        hist,
        net,
        p,
        missing,
    )
