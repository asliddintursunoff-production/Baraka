"""Data quality gate (P0): freshness, reconciliation with the file's own reports, plausibility.

`assess(business)` runs after every sync and stores `Business.data_quality`:
  status       ok | needs_review | no_data
  as_of        last actual date in the data; missing_from..missing_to = days not entered yet
  recon        per month: computed vs the workbook's report (1 % tolerance), from DataSource.summary
  flags        plausibility checks that failed, each with a plain Uzbek explanation
While `needs_review`, forecasts, verdicts and advice are blocked (apps.tenancy.gate).
"""

from __future__ import annotations

import itertools
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Max, Min

from apps.ai import uz_format as uz
from apps.finance.models import CashAccount, Obligation, Transaction
from apps.integrations.models import DataSource
from apps.tenancy.context import tenant_context, today_for
from apps.tenancy.models import Business

NON_OPERATING = ("financing", "capex", "dividend", "avans")
METRIC_UZ = {
    "cash_end": "Oy oxiridagi pul",
    "revenue": "Sof tushum",
    "payroll_accrued": "Ish haqi (hisoblangan)",
}
FRESH_DAYS = 1


def freshness(last: date, today: date) -> dict[str, Any]:
    gap = (today - last).days
    if gap <= FRESH_DAYS:
        return {"as_of": last.isoformat(), "stale": False, "missing_days": 0, "text": ""}
    a, b = last + timedelta(days=1), today
    span = (
        f"{a.day}–{uz.format_date(b)}"
        if a.month == b.month
        else f"{uz.format_date(a)} – {uz.format_date(b)}"
    )
    return {
        "as_of": last.isoformat(),
        "stale": True,
        "missing_from": a.isoformat(),
        "missing_to": b.isoformat(),
        "missing_days": gap,
        "text": f"{uz.format_date(last)} holati; {span} kunlik hisobotlari hali kiritilmagan",
    }


def _monthly(rows: list[dict[str, Any]]) -> dict[date, dict[str, Decimal]]:
    out: dict[date, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for r in rows:
        m = r["txn_date"].replace(day=1)
        if r["direction"] == "in" and r["category"] not in NON_OPERATING:
            out[m]["revenue"] += r["amount"]
        elif r["direction"] == "out" and r["category"] not in NON_OPERATING:
            out[m]["expenses"] += r["amount"]
            if r["category"] == "payroll":
                out[m]["payroll"] += r["amount"]
    return out


def checks(business: Business, today: date) -> dict[str, Any]:
    """Pure assessment from the DB (inside the tenant context)."""
    agg = Transaction.objects.filter(is_actual=True).aggregate(
        first=Min("txn_date"), last=Max("txn_date")
    )
    if agg["last"] is None:
        return {"status": "no_data"}
    first, last = agg["first"], min(agg["last"], today)
    fresh = freshness(last, today)
    rows = list(
        Transaction.objects.filter(is_actual=True).values(
            "txn_date", "direction", "category", "amount"
        )
    )
    monthly = _monthly(rows)
    summaries = [
        s.summary for s in DataSource.objects.exclude(summary={}) if s.summary.get("months")
    ]
    # accrual figures from financial-model workbooks override the cash proxies
    for summ in summaries:
        for ms, f in summ["months"].items():
            m = date.fromisoformat(ms)
            if Decimal(f.get("revenue", "0")):
                monthly[m]["revenue"] = Decimal(f["revenue"])
            if Decimal(f.get("payroll_accrued", "0")):
                monthly[m]["payroll"] = Decimal(f["payroll_accrued"])
    full = sorted(m for m in monthly if m < last.replace(day=1) or last.day >= 25)
    ref = monthly[full[-1]] if full else None
    rev = ref["revenue"] if ref else Decimal(0)
    flags: list[dict[str, str]] = []

    def flag(code: str, text: str) -> None:
        flags.append({"code": code, "text": text})

    cash = CashAccount.objects.order_by("-as_of_date").first()
    if rev > 0 and cash is None:
        flag(
            "cash_missing",
            "Savdo bor, lekin kassadagi pul (boshlang'ich qoldiq) jadvalda topilmadi.",
        )
    if ref and rev > 0 and ref["payroll"] > rev * Decimal("0.6"):
        flag(
            "payroll_share",
            f"Ish haqi ({uz.format_mln(ref['payroll'])}) oylik savdoning ({uz.format_mln(rev)}) 60% idan ko'p — ehtimol ish haqi ikki marta yoki noto'g'ri varaqdan o'qilgan.",
        )
    big = (
        Obligation.objects.filter(status="planned", due_date__gte=last).order_by("-amount").first()
    )
    if big and rev > 0 and big.amount > rev * 2:
        flag(
            "big_obligation",
            f'"{big.title}" ({uz.format_mln(big.amount)}) oylik savdodan 2 barobardan katta — summani tekshirish kerak.',
        )
    for a, b in itertools.pairwise(full):
        for key, word in (("revenue", "Savdo"), ("expenses", "Xarajatlar")):
            x, y = monthly[a][key], monthly[b][key]
            if x > 0 and y > 0 and (y > x * 3 or x > y * 3):
                flag(
                    f"jump_{key}",
                    f"{word} {uz.MONTHS[a.month - 1]}dan {uz.MONTHS[b.month - 1]}ga 3 barobardan ko'p o'zgargan ({uz.format_mln(x)} → {uz.format_mln(y)}).",
                )
    dup = (
        Transaction.objects.filter(is_actual=True, amount__gte=1_000_000, raw_row__isnull=False)
        .values("txn_date", "amount", "direction")
        .annotate(n=Count("id"), sheets=Count("raw_row__sheet_title", distinct=True))
        .filter(sheets__gt=1)
        .count()
    )
    if dup >= 3:
        flag(
            "duplicates",
            f"{dup} ta to'lov bir xil sana va summa bilan ikki xil varaqda bor — ikki marta hisoblanayotgan bo'lishi mumkin.",
        )
    recon = [
        r | {"label": METRIC_UZ.get(r["metric"], r["metric"])}
        for s in summaries
        for r in s.get("recon", [])
    ]
    mismatch = [r for r in recon if not r["ok"]]
    status = "needs_review" if (mismatch or flags) else "ok"
    return {
        "status": status,
        "first_date": first.isoformat(),
        "last_date": last.isoformat(),
        **fresh,
        "monthly_revenue": str(rev),
        "recon": recon,
        "recon_ok": not mismatch,
        "flags": flags,
    }


def forecast_check(business: Business, q: dict[str, Any]) -> None:
    """Check 4 (needs the forecast): cash falling below -3x monthly revenue."""
    from apps.insights.forecasting import get_forecast

    rev = Decimal(q.get("monthly_revenue") or 0)
    if rev <= 0 or q.get("status") == "no_data":
        return
    low = get_forecast(business).result.min_balance
    if low < -rev * 3:
        q["flags"].append(
            {
                "code": "forecast_low",
                "text": f"Prognozda kassa {uz.format_mln(low)} gacha tushadi — bu oylik savdodan 3 barobar ko'p minus, ma'lumotda xato bo'lishi mumkin.",
            }
        )
        q["status"] = "needs_review"


def assess(business: Business) -> dict[str, Any]:
    today = today_for(business)
    with tenant_context(business):
        q = checks(business, today)
    if q["status"] != "no_data" and q["status"] == "ok":
        forecast_check(business, q)
    Business.objects.filter(pk=business.pk).update(data_quality=q)
    business.data_quality = q
    return q


def summary_line(q: dict[str, Any]) -> str:
    """One Uzbek sentence for chat / the gate."""
    if q.get("status") != "needs_review":
        return ""
    bad = [r for r in q.get("recon", []) if not r["ok"]]
    parts = []
    if bad:
        parts.append("jadvaldan o'qigan raqamlarim faylning o'z hisobotlari bilan mos kelmayapti")
    if q.get("flags"):
        parts.append(q["flags"][0]["text"].rstrip("."))
    return (
        "Ma'lumotda muammo bor: "
        + "; ".join(parts)
        + ". Shuning uchun hozircha prognoz va maslahat bermayman."
    )
