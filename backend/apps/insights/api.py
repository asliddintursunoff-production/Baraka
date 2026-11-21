"""Page APIs: one request per page (spec §6). All numbers/dates come formatted from here."""

from __future__ import annotations

import calendar as pycal
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.response import Response

from apps.ai import uz_format as uz
from apps.ai.uz_parse import parse_amounts, parse_count, parse_percent
from apps.engine import (
    Change,
    EngineError,
    ForecastResult,
    StaffCountUnknown,
    evaluate_purchase,
    explain_day,
    simulate,
)
from apps.finance.models import Transaction
from apps.integrations.models import DataSource
from apps.knowledge.models import MemoryItem
from apps.telemetry import timing
from apps.tenancy.api import BusinessAPIView
from apps.tenancy.context import today_for
from apps.tenancy.models import Business

from . import advice
from .forecasting import CachedForecast, get_forecast
from .models import Alert

HORIZONS = (7, 30, 60, 90)
PRESETS = (
    {
        "id": "buy",
        "label": "25 mln ga jihoz olsam",
        "kind": "purchase",
        "amount": Decimal(25_000_000),
    },
    {"id": "rev", "label": "Savdo 20% kamaysa", "kind": "revenue_pct", "value": Decimal(-20)},
    {"id": "staff", "label": "Yana 2 ta xodim olsam", "kind": "new_staff", "value": Decimal(2)},
)
MONTH_CHART = ("Yan", "Fev", "Mar", "Apr", "May", "Iyun", "Iyul", "Avg", "Sen", "Okt", "Noy", "Dek")
USAGE_SUFFIX = {
    "advice": "Maslahatlarda hisobga olinadi.",
    "alerts": "Ogohlantirishlarda ishlatiladi.",
    "forecast": "Prognozga hisobga olindi.",
    "later": "",
}


def _money(v: Decimal) -> str:
    return f"{v:.2f}"


def series(base: ForecastResult, days: int = 90) -> list[dict[str, Any]]:
    rows = base.daily()[: days + 1]
    return [
        {
            "i": i,
            "date": r.date.isoformat(),
            "label": uz.format_date_short(r.date),
            "close": _money(r.close),
            "p10": _money(r.p10),
            "p90": _money(r.p90),
            "display": uz.format_mln(r.close),
        }
        for i, r in enumerate(rows)
    ]


def summaries(base: ForecastResult) -> dict[str, Any]:
    out = {}
    for h in HORIZONS:
        s = advice.horizon_summary(base, h)
        out[str(h)] = {
            "days": h,
            "verdict": s.verdict,
            "chip": s.chip,
            "lowest_index": (s.lowest_date - base.today).days,
            "lowest_date": s.lowest_date.isoformat(),
            "lowest_display": uz.format_mln(s.lowest),
            "lowest_date_label": uz.format_date(s.lowest_date),
            "text": s.text,
            "callout_title": s.callout_title,
            "callout_text": s.callout_text,
            "title": f"Keyingi {h} kun",
        }
    return out


def forecast_block(base: ForecastResult) -> dict[str, Any]:
    return {
        "series": series(base),
        "safe_min": _money(base.safe_min),
        "safe_label": f"Xavfsiz chegara · {uz.format_mln(base.safe_min, short=True)}",
        "summaries": summaries(base),
        "default_horizon": 60,
        "insufficient_data": base.insufficient_data,
    }


def _sync_status(business_id: int) -> dict[str, Any]:
    src = DataSource.objects.order_by("-last_synced_at").values("last_synced_at", "status").first()
    if not src:
        return {"connected": False, "ok": False, "label": "Jadval ulanmagan"}
    at = src["last_synced_at"]
    if not at:
        return {"connected": True, "ok": False, "label": "Google Sheets · hali sinxronlanmagan"}
    minutes = max(0, int((timezone.now() - at).total_seconds() // 60))
    ago = (
        "hozirgina"
        if minutes < 1
        else f"{minutes} daqiqa oldin"
        if minutes < 60
        else f"{minutes // 60} soat oldin"
    )
    return {
        "connected": True,
        "ok": src["status"] == "active",
        "label": f"Google Sheets · {ago} sinxronlandi",
    }


USAGE_ORDER = ("forecast", "advice", "alerts", "later")


def _news() -> list[dict[str, str]]:
    out = []
    learned = (
        MemoryItem.objects.filter(business__isnull=False, kind__in=["rule", "correction"])
        .order_by("-created_at")
        .values("text", "created_at", "meta")
        .first()
    )
    if learned:
        days = (timezone.localdate() - timezone.localtime(learned["created_at"]).date()).days
        when = "bugun" if days <= 0 else "kecha" if days == 1 else f"{days} kun oldin"
        by_ai = (learned["meta"] or {}).get("source") == "ai_confirmed"
        text = (
            f'"{learned["text"]}" — AI sezdi, siz tasdiqladingiz. Prognozga qo\'shildi.'
            if by_ai
            else f'Xodim izohi: "{learned["text"]}". Prognozga qo\'shildi.'
        )
        out.append({"kind": "learned", "label": f"AI o'rgandi · {when}", "text": text})
    segs = list(
        MemoryItem.objects.filter(business__isnull=True, kind="segment_insight").values(
            "text", "meta"
        )
    )
    if segs:
        segs.sort(key=lambda r: USAGE_ORDER.index((r["meta"] or {}).get("usage", "later")))
        seg = segs[0]
        suffix = USAGE_SUFFIX.get((seg["meta"] or {}).get("usage", ""), "")
        out.append(
            {
                "kind": "segment",
                "label": "Shu turdagi bizneslardan",
                "text": f"Toshkent kafelarida {seg['text'][0].lower()}{seg['text'][1:]}. {suffix}".strip(),
            }
        )
    return out


def _kpis(
    base: ForecastResult, today: date, real_today: date | None = None
) -> list[dict[str, str]]:
    d30, d60 = today - timedelta(days=29), today - timedelta(days=59)
    agg = Transaction.objects.filter(
        txn_date__gte=d60, txn_date__lte=today, is_actual=True
    ).aggregate(
        in30=Sum("amount", filter=Q(direction="in", txn_date__gte=d30)),
        out30=Sum("amount", filter=Q(direction="out", txn_date__gte=d30)),
        in_prev=Sum("amount", filter=Q(direction="in", txn_date__lt=d30)),
    )
    in30 = agg["in30"] or Decimal(0)
    out30 = agg["out30"] or Decimal(0)
    in_prev = agg["in_prev"] or Decimal(0)
    prev_month = uz.MONTHS[(d30 - timedelta(days=15)).month - 1]
    if in_prev > 0:
        pct = ((in30 - in_prev) / in_prev * 100).quantize(Decimal("0.1"))
        arrow = "▲" if pct > 0 else "▼" if pct < 0 else "•"
        change = f"{arrow} {str(abs(pct)).replace('.', ',')}% {prev_month}ga nisbatan"
        change_tone = "success" if pct > 0 else "warning" if pct < 0 else "muted"
    else:
        change, change_tone = "Oldingi davr ma'lumoti yo'q", "muted"
    net = in30 - out30
    due = [p for p in base.obligations if base.today < p.date <= base.today + timedelta(days=30)]
    due_total = sum((p.amount for p in due), Decimal(0))
    return [
        {
            "id": "cash",
            "label": "Hozir qo'lingizdagi pul",
            "value": uz.format_mln_number(base.close_on(base.today)),
            "unit": "mln so'm",
            "note": "Naqd + bank hisobi"
            if not real_today or real_today <= base.today + timedelta(days=1)
            else f"{uz.format_date(base.today)} holati",
            "tone": "muted",
        },
        {
            "id": "in30",
            "label": "30 kunda kirgan pul",
            "value": uz.format_mln_number(in30),
            "unit": "mln",
            "note": change,
            "tone": change_tone,
        },
        {
            "id": "out30",
            "label": "30 kunda chiqqan pul",
            "value": uz.format_mln_number(out30),
            "unit": "mln",
            "note": f"{uz.format_mln(abs(net))} ortib qoldi"
            if net >= 0
            else f"{uz.format_mln(-net)} ko'p chiqdi",
            "tone": "success" if net >= 0 else "danger",
        },
        {
            "id": "due30",
            "label": "30 kunda to'lashingiz shart",
            "value": uz.format_mln_number(due_total),
            "unit": "mln",
            "note": f"{len(due)} ta to'lov"
            + (f" · eng yaqini {uz.format_date(due[0].date)}" if due else ""),
            "tone": "muted",
        },
    ]


def _upcoming(base: ForecastResult) -> dict[str, Any]:
    due = [p for p in base.obligations if base.today < p.date <= base.today + timedelta(days=30)]
    return {
        "rows": [
            {
                "date_label": uz.format_date_short(p.date),
                "title": p.title,
                "priority": p.priority,
                "priority_label": advice.PRIORITY_LABEL[p.priority],
                "amount_display": uz.format_mln(p.amount),
            }
            for p in due
        ],
        "total_display": uz.format_mln(sum((p.amount for p in due), Decimal(0))),
    }


def _monthly(today: date) -> list[dict[str, str]]:
    first_this = today.replace(day=1)
    start = (first_this - timedelta(days=1)).replace(day=1)
    for _ in range(4):
        start = (start - timedelta(days=1)).replace(day=1)
    rows = (
        Transaction.objects.filter(txn_date__gte=start, txn_date__lt=first_this, is_actual=True)
        .annotate(m=TruncMonth("txn_date"))
        .values("m")
        .annotate(
            inflow=Sum("amount", filter=Q(direction="in")),
            outflow=Sum("amount", filter=Q(direction="out")),
        )
        .order_by("m")
    )
    out = []
    for r in rows:
        inflow, outflow = r["inflow"] or Decimal(0), r["outflow"] or Decimal(0)
        profit = ((inflow - outflow) / uz.MLN).quantize(Decimal(1))
        out.append(
            {
                "label": MONTH_CHART[r["m"].month - 1],
                "inflow": _money(inflow),
                "outflow": _money(outflow),
                "inflow_display": uz.format_mln(inflow),
                "outflow_display": uz.format_mln(outflow),
                "profit_label": f"{'+' if profit >= 0 else uz.MINUS}{abs(profit)}",
            }
        )
    return out


def _freshness(b: Business) -> dict[str, Any] | None:
    q = b.data_quality or {}
    if b.is_demo or not q.get("stale"):
        return None
    return {
        "as_of": q.get("as_of"),
        "missing_from": q.get("missing_from"),
        "missing_to": q.get("missing_to"),
        "text": q.get("text", "")[:1].upper() + q.get("text", "")[1:],
    }


class DashboardView(BusinessAPIView):
    requires_data = True  # 409 no_data until a source is synced

    def get(self, request: Request) -> Response:
        b = self.business
        cached = get_forecast(b)
        base = cached.result
        today = today_for(b)
        snap_time = timezone.localtime(timezone.now(), ZoneInfo(b.timezone)).strftime("%H:%M")
        return Response(
            {
                "user": {"first_name": getattr(request.user, "first_name", "")},
                "business": {"id": b.pk, "name": b.name, "city": b.city},
                "today": {"iso": today.isoformat(), "label": uz.format_date_long(today)},
                "sync": _sync_status(b.pk),
                "alerts": {"new": Alert.objects.filter(status="new").count()},
                "banner": {
                    "label": f"Bugungi maslahat · keyingi 60 kun · {snap_time}",
                    **advice.banner(base),
                    "beyond": (
                        f"60 kundan keyin: {uz.format_date(base.beyond[0])} {base.beyond[0].year} kuni kassa "
                        f"{uz.format_mln(base.beyond[1])} gacha tushadi."
                        if base.beyond
                        else ""
                    ),
                },
                "kpis": _kpis(
                    base, base.today, today
                ),  # as of the last actual day when data is stale
                "freshness": _freshness(b),
                "forecast": forecast_block(base),
                "steps": advice.steps(base),
                "news": _news(),
                "upcoming": _upcoming(base),
                "monthly": _monthly(today),
                "has_cash": cached.has_cash,
            }
        )


# --- Forecast page --------------------------------------------------------------------
def _key_days(base: ForecastResult, days: int = 90) -> list[dict[str, Any]]:
    by_day: dict[date, list[Any]] = {}
    for p in base.obligations:
        if base.today < p.date <= base.today + timedelta(days=days):
            by_day.setdefault(p.date, []).append(p)
    out = []
    for d, pays in sorted(by_day.items()):
        close = base.close_on(d)
        st = advice.day_status(base, close)
        hardest = d == base.min_date
        total = sum((p.amount for p in pays), Decimal(0))
        names = advice.labels_joined(pays)
        out.append(
            {
                "i": (d - base.today).days,
                "date": d.isoformat(),
                "label": uz.format_date(d) + (" · eng qiyin kun" if hardest else ""),
                "title": f"{names} · {uz.format_mln(total, short=True)}",
                "balance": f"{uz.format_mln(close)} qoladi · {advice.STATUS_WORD['warn' if hardest and st == 'ok' else st]}",
                "status": "warn" if hardest and st == "ok" else st,
                "hardest": hardest,
            }
        )
    return out


def run_preset(cached: CachedForecast, preset: dict[str, Any]) -> dict[str, Any]:
    base, inp = cached.result, cached.inp
    with timing.measure("engine"):
        if preset["kind"] == "purchase":
            decision = evaluate_purchase(inp, preset["amount"], base=base)
            s = simulate(base, inp, Change(kind="extra_expense", value=preset["amount"]))
            rec = decision.recommended.schedule[0][0] if decision.recommended else None
            card = advice.scenario_card(base, s, kind="purchase", recommended_date=rec)
        else:
            s = simulate(base, inp, Change(kind=preset["kind"], value=preset["value"]))
            card = advice.scenario_card(base, s, kind="other")
    return {
        "card": card,
        "overlay": [_money(Decimal(int(v)) / 100) for v in s.close[:91]],
        "marker_index": card["marker_index"],
    }


class ForecastView(BusinessAPIView):
    requires_data = True  # 409 no_data until a source is synced

    def get(self, request: Request) -> Response:
        cached = get_forecast(self.business)
        base = cached.result
        presets = []
        for p in PRESETS:
            try:
                result = run_preset(cached, p)
            except StaffCountUnknown:
                result = {"card": None, "needs": "staff_count"}
            except EngineError:
                result = {"card": None, "error": "not_applicable"}
            presets.append({"id": p["id"], "label": p["label"], **result})
        return Response(
            {
                "forecast": forecast_block(base),
                "key_days": _key_days(base),
                "presets": presets,
                "free_text_placeholder": "Masalan: 10 mln ga reklama qilsam",
            }
        )


class SimulateView(BusinessAPIView):
    """POST {preset} | {text}. Free text: deterministic parse here; the LLM path is M3."""

    requires_data = True  # 409 no_data until a source is synced

    def post(self, request: Request) -> Response:
        cached = get_forecast(self.business)
        data = request.data if isinstance(request.data, dict) else {}
        preset_id = data.get("preset")
        if preset_id:
            preset = next((p for p in PRESETS if p["id"] == preset_id), None)
            if preset is None:
                return Response({"error": "unknown_preset"}, status=400)
            return Response(run_preset(cached, preset))
        text = str(data.get("text", ""))[:300]
        pct = parse_percent(text)
        if pct is not None and any(w in text.lower() for w in ("kamay", "tush", "pasay")):
            preset = {"kind": "revenue_pct", "value": -abs(pct)}
        elif pct is not None:
            preset = {"kind": "revenue_pct", "value": abs(pct)}
        elif "xodim" in text.lower() and parse_count(text):
            preset = {"kind": "new_staff", "value": Decimal(parse_count(text) or 0)}
        elif amounts := parse_amounts(text):
            preset = {"kind": "purchase", "amount": amounts[0]}
        else:
            return Response(
                {
                    "error": "not_understood",
                    "message": "Tushunmadim. Summani yoki foizni yozing, masalan: 10 mln ga reklama qilsam.",
                },
                status=422,
            )
        try:
            return Response(run_preset(cached, preset))
        except StaffCountUnknown:
            return Response(
                {"error": "staff_count_unknown", "message": "Hozir nechta xodimingiz bor?"},
                status=409,
            )
        except EngineError as exc:
            return Response({"error": "engine", "message": str(exc)}, status=400)


# --- Calendar ---------------------------------------------------------------------------
class CalendarView(BusinessAPIView):
    requires_data = True  # 409 no_data until a source is synced

    def get(self, request: Request) -> Response:
        b = self.business
        base = get_forecast(b).result
        today = today_for(b)
        raw = request.query_params.get("month") or ""
        try:
            first = datetime.strptime(raw, "%Y-%m").date() if raw else today.replace(day=1)
        except ValueError:
            return Response({"error": "bad_month", "message": "month=YYYY-MM"}, status=400)
        if not raw and today.day > 20:
            first = (today.replace(day=28) + timedelta(days=5)).replace(day=1)  # show next month
        days_in = pycal.monthrange(first.year, first.month)[1]
        month_days = [first.replace(day=n) for n in range(1, days_in + 1)]
        visible = [d for d in month_days if base.today <= d <= base.end]
        hardest = min(visible, key=lambda d: base.close_on(d)) if visible else None
        days = []
        for d in month_days:
            in_window = base.today <= d <= base.end
            pays = advice.payments_on(base, d) if in_window else []
            close = base.close_on(d) if in_window else None
            hot = d == hardest and bool(pays)
            kind = "out" if not in_window else "hot" if hot else "pay" if pays else "plain"
            entry: dict[str, Any] = {
                "n": d.day,
                "date": d.isoformat(),
                "kind": kind,
                "items": [
                    {
                        "label": f"{advice.payment_label(p)} {advice.mln_number_short(p.amount)}",
                        "critical": p.priority == "critical",
                    }
                    for p in pays
                ],
                "bal": uz.format_mln(close) if close is not None else None,
                "title": uz.format_date(d),
            }
            if close is not None:
                status = advice.day_status(base, close)
                if hot or status != "ok":
                    bd = explain_day(base, d)
                    entry["detail"] = {
                        "full": True,
                        "chip": "Qiyin kun, lekin pul yetadi"
                        if status == "ok"
                        else "Ehtiyot: xavfsiz chegaradan past"
                        if status == "warn"
                        else "Pul yetmaydi",
                        "status": status,
                        "rows": [
                            {
                                "label": "Kun boshida kassada",
                                "value": uz.format_mln(bd.opening),
                                "tone": "plain",
                            },
                            {
                                "label": "Savdodan kiradi",
                                "value": uz.format_mln(bd.net_trading, signed=True),
                                "tone": "success",
                            },
                            *[
                                {
                                    "label": advice.payment_label(p)
                                    + (
                                        f" · {b.staff_count} xodim"
                                        if p.category == "payroll" and b.staff_count
                                        else ""
                                    ),
                                    "badge": "majburiy" if p.priority == "critical" else "",
                                    "value": uz.format_mln(-p.amount),
                                    "tone": "danger",
                                }
                                for p in bd.payments
                            ],
                        ],
                        "closing": uz.format_mln(bd.closing),
                        "advice": advice.day_advice(base, d),
                        "reminder": {
                            "date": (d - timedelta(days=1)).isoformat(),
                            "label": f"{uz.format_date(d - timedelta(days=1), 'ga')} eslatma qo'yish",
                        }
                        if d - timedelta(days=1) >= today
                        else None,
                    }
                else:
                    entry["detail"] = {
                        "full": False,
                        "text": advice.day_text(base, d, close),
                        "closing": uz.format_mln(close),
                    }
            days.append(entry)
        prev_m = (first - timedelta(days=1)).replace(day=1)
        next_m = (first + timedelta(days=days_in)).replace(day=1)
        selected = hardest or (today if first <= today < next_m else first)
        return Response(
            {
                "month": first.strftime("%Y-%m"),
                "title": f"{uz.MONTHS[first.month - 1].capitalize()} {first.year}",
                "prev": prev_m.strftime("%Y-%m"),
                "next": next_m.strftime("%Y-%m"),
                "lead": first.weekday(),
                "weekdays": list(uz.WEEKDAYS_SHORT),
                "days": days,
                "selected": selected.isoformat(),
            }
        )


class AlertsView(BusinessAPIView):
    """GET: open alerts + today's brief for the bell; POST: mark them seen."""

    def get(self, request: Request) -> Response:
        rows = Alert.objects.exclude(status=Alert.Status.DISMISSED).order_by("-created_at")[:20]
        return Response(
            {
                "alerts": [
                    {
                        "id": a.pk,
                        "kind": a.kind,
                        "severity": a.severity,
                        "text": a.text_uz,
                        "date": uz.format_date(a.date) if a.date else "",
                        "new": a.status == Alert.Status.NEW,
                    }
                    for a in rows
                ]
            }
        )

    def post(self, request: Request) -> Response:
        n = Alert.objects.filter(status=Alert.Status.NEW).update(status=Alert.Status.SEEN)
        return Response({"ok": True, "seen": n})
