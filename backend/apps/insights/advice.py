"""Deterministic Uzbek texts built from engine results (no LLM, no arithmetic here).

Style (spec §1.7): decision first, one reason, at most 3 steps; no jargon. Every number
comes from the ForecastResult/ScenarioResult and is formatted by `uz_format`.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from apps.ai import uz_format as uz
from apps.engine import (
    Deferral,
    ForecastResult,
    PreparedObligation,
    ScenarioResult,
    compute_verdict,
    spend_limit_until,
)
from apps.engine.money import from_tiyin, to_tiyin

CATEGORY_WORD = {
    "payroll": "oylik",
    "loan": "kredit",
    "rent": "ijara",
    "tax": "soliq",
    "kommunal": "kommunal to'lov",
    "utility": "kommunal to'lov",
}
CATEGORY_LABEL = {
    "payroll": "Oylik",
    "loan": "Kredit",
    "rent": "Ijara",
    "tax": "Soliq",
    "kommunal": "Svet",
    "utility": "Svet",
}
PRIORITY_LABEL = {
    "critical": "Muhim",
    "deferrable": "Kechiktirsa bo'ladi",
    "discretionary": "Ixtiyoriy",
}
VERDICT_CHIP = {"yes": "Pul yetadi", "risky": "Ehtiyot", "no": "Pul yetmaydi"}
STATUS_WORD = {"ok": "yaxshi", "warn": "ehtiyot", "danger": "xavfli"}


def join_uz(words: list[str]) -> str:
    words = list(OrderedDict.fromkeys(w for w in words if w))
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " va " + words[-1]


def payment_word(p: PreparedObligation) -> str:
    if p.category in CATEGORY_WORD:
        return CATEGORY_WORD[p.category]
    if p.category == "supplier" and p.counterparty:
        return p.counterparty
    return p.title


def payment_label(p: PreparedObligation) -> str:
    if p.category in CATEGORY_LABEL:
        return CATEGORY_LABEL[p.category]
    if p.counterparty:
        return p.counterparty
    return p.title


def labels_joined(pays: list[PreparedObligation]) -> str:
    """'Oylik + kredit', "Agro Go'sht" (names keep their case; category words follow)."""
    labels = list(dict.fromkeys(payment_label(p) for p in pays))
    if not labels:
        return ""
    return " + ".join(
        [labels[0]] + [lab.lower() if lab in CATEGORY_LABEL.values() else lab for lab in labels[1:]]
    )


def mln_number_short(amount: Decimal) -> str:
    """'45', '18,5' (calendar chips)."""
    return uz.format_mln(amount, short=True).removesuffix(" mln")


def payments_on(base: ForecastResult, d: date) -> list[PreparedObligation]:
    if d == base.today:
        return [p for p in base.obligations if p.date <= d]
    return [p for p in base.obligations if p.date == d]


def day_status(base: ForecastResult, close: Decimal) -> str:
    return "danger" if close < 0 else "warn" if close < base.safe_min else "ok"


@dataclass(frozen=True)
class HorizonSummary:
    days: int
    verdict: str | None
    chip: str
    lowest_date: date
    lowest: Decimal
    text: str  # "Eng qiyin kun — 10-dekabr: kassada 18,8 mln qoladi."
    callout_title: str  # "10-dek · eng qiyin kun"
    callout_text: str  # "Oylik + kredit · 18,8 mln qoladi"


def horizon_summary(base: ForecastResult, days: int) -> HorizonSummary:
    close = base.close[: days + 1]
    i = int(close.argmin())
    lowest = from_tiyin(int(close[i]))
    d = base.date_at(i)
    verdict = (
        None
        if base.insufficient_data
        else compute_verdict(close, base.critical_mask[: days + 1], to_tiyin(base.safe_min))
    )
    pays = payments_on(base, d)
    what = labels_joined(pays)
    if verdict == "no":
        text = f"Eng qiyin kun — **{uz.format_date(d)}**: kassada {uz.format_mln(lowest)} bo'ladi."
    else:
        text = f"Eng qiyin kun — **{uz.format_date(d)}**: kassada {uz.format_mln(lowest)} qoladi."
    return HorizonSummary(
        days=days,
        verdict=verdict,
        chip=VERDICT_CHIP.get(verdict or "", "Ma'lumot yetarli emas"),
        lowest_date=d,
        lowest=lowest,
        text=text,
        callout_title=f"{uz.format_date_short(d)} · eng qiyin kun",
        callout_text=(f"{what} · " if what else "") + f"{uz.format_mln(lowest)} qoladi",
    )


def deferral_text(d: Deferral) -> str:
    who = d.obligation.counterparty or d.obligation.title
    return f"{uz.add_case(who, 'ga')} to'lovni {d.days} kunga suring."


def banner(base: ForecastResult) -> dict[str, str]:
    """The dark "Bugungi maslahat" card: headline, reason, one strong instruction."""
    if base.insufficient_data:
        return {
            "headline": "Ishonchli prognoz uchun kamida 2 haftalik ma'lumot kerak.",
            "reason": "Jadvalingizga savdo va xarajatlarni yozib boring —",
            "instruction": "prognoz o'zi paydo bo'ladi.",
        }
    d = base.min_date
    pays = payments_on(base, d)
    words = join_uz([payment_word(p) for p in pays])
    if base.verdict == "yes":
        limit = spend_limit_until(base, d) if d > base.today else Decimal(0)
        reason = (
            f"O'sha kuni {words} bir kunga tushgan. Shuning uchun"
            if len(pays) > 1
            else f"O'sha kuni {words} to'lanadi. Shuning uchun"
            if pays
            else "Shuning uchun"
        )
        if limit > 0:
            instruction = (
                f"{uz.format_date(d, 'gacha')} {uz.format_mln(limit, short=True).removesuffix(' mln')} "
                f"million so'mdan katta xarid qilmang."
            )
        else:
            instruction = f"{uz.format_date(d, 'gacha')} katta xarid qilmang."
        return {
            "headline": f"Pulingiz yetadi. Faqat {uz.format_date(d, 'ga')} ehtiyot bo'ling.",
            "reason": reason,
            "instruction": instruction,
        }
    if base.verdict == "risky":
        shortage = base.first_shortage_date
        if shortage and base.deferrals:
            return {
                "headline": f"Ehtiyot bo'ling: {uz.format_date(shortage, 'da')} kassa minusga tushadi.",
                "reason": "Bu kuni muhim to'lov yo'q, shuning uchun bitta to'lovni surish yetadi:",
                "instruction": deferral_text(base.deferrals[0]),
            }
        return {
            "headline": f"Ehtiyot bo'ling: {uz.format_date(d, 'da')} kassa xavfsiz chegaradan pastga tushadi.",
            "reason": f"O'sha kuni kassada {uz.format_mln(base.min_balance)} qoladi. Shuning uchun",
            "instruction": f"{uz.format_date(d, 'gacha')} yangi xarid qilmang.",
        }
    shortage = base.first_shortage_date or d
    return {
        "headline": f"Diqqat: {uz.format_date(shortage, 'da')} majburiy to'lovlarga pul yetmaydi.",
        "reason": f"Eng past qoldiq {uz.format_mln(base.min_balance)}. Shuning uchun",
        "instruction": "hozirdan ixtiyoriy xarajatlarni to'xtating va AI bilan reja tuzing.",
    }


def steps(base: ForecastResult) -> list[dict[str, str]]:
    """'Nima qilish kerak': up to 3 dated steps, coloured by severity."""
    if base.insufficient_data:
        return []
    out: list[dict[str, str]] = []
    hard = base.min_date
    upcoming = [p for p in base.obligations if base.today < p.date < hard]
    if upcoming:
        p = upcoming[0]
        close = base.close_on(p.date)
        st = day_status(base, close)
        out.append(
            {
                "severity": "success" if st == "ok" else "warning",
                "label": f"{uz.format_date(p.date)} · {'bemalol' if st == 'ok' else 'ehtiyot'}",
                "text": f"{uz.add_case(payment_word(p).capitalize() if p.category in CATEGORY_WORD else payment_word(p), 'ga')} "
                f"{uz.format_mln(p.amount, short=True)} to'lang."
                + (" Pul yetadi." if st == "ok" else ""),
            }
        )
    if base.deferrals:
        d = base.deferrals[0]
        out.append(
            {
                "severity": "warning",
                "label": f"{uz.format_date(d.obligation.date, 'gacha')} · ehtiyot",
                "text": deferral_text(d),
            }
        )
    elif hard > base.today:
        limit = spend_limit_until(base, hard)
        out.append(
            {
                "severity": "warning",
                "label": f"{uz.format_date(hard, 'gacha')} · ehtiyot",
                "text": f"{uz.format_mln(limit, short=True)} so'mdan katta xarid qilmang."
                if limit > 0
                else "Yangi xarid qilmang.",
            }
        )
    pays = [p for p in payments_on(base, hard) if p.priority == "critical"]
    if pays:
        words = join_uz([payment_word(p) for p in pays])
        out.append(
            {
                "severity": "danger",
                "label": f"{uz.format_date(hard)} · muhim kun",
                "text": f"Avval {words}ni to'lang, keyin boshqasini."
                if len(pays) > 1 or base.obligations
                else f"Avval {words}ni to'lang.",
            }
        )
    return out[:3]


def day_text(base: ForecastResult, d: date, close: Decimal) -> str:
    pays = payments_on(base, d)
    if not pays:
        return "Bu kuni to'lov yo'q. Faqat savdodan pul kiradi."
    st = day_status(base, close)
    parts = []
    for p in pays:
        kind = "Majburiy to'lov" if p.priority == "critical" else "Kechiktirsa bo'ladigan to'lov"
        if st == "ok":
            ease = "pul bemalol yetadi" if close >= base.safe_min * 3 else "pul yetadi"
        elif st == "warn":
            ease = "pul yetadi, lekin kassa xavfsiz chegaradan pastga tushadi"
        else:
            ease = "pul yetmaydi"
        parts.append(f"{payment_label(p)} · {uz.format_mln(p.amount, short=True)}. {kind}, {ease}.")
    return " ".join(parts)


def day_advice(base: ForecastResult, d: date) -> str:
    pays = payments_on(base, d)
    critical = [p for p in pays if p.priority == "critical"]
    if critical:
        words = join_uz([payment_word(p) for p in critical])
        return f"Avval {words}ni to'lang. Shu kuni boshqa to'lov qo'ymang."
    if pays:
        return "Bu to'lovni kerak bo'lsa bir necha kunga surish mumkin."
    return "Bu kuni katta xarajat rejalashtirmang."


SCENARIO_TITLES = {
    "purchase": {"yes": "Bo'ladi", "risky": "Bo'ladi, lekin tor", "no": "Yo'q, hozir emas"},
    "other": {"yes": "Bo'ladi", "risky": "Bo'ladi, lekin tor", "no": "Xavfli"},
}


def scenario_card(
    base: ForecastResult,
    s: ScenarioResult,
    *,
    kind: str,
    recommended_date: date | None = None,
    tip: str | None = None,
    days: int = 90,
) -> dict[str, Any]:
    """Verdict card for a "what if", judged on the visible window (default 90 days)."""
    close = s.close[: days + 1]
    mask = s.critical_mask[: days + 1]
    safe_t = to_tiyin(base.safe_min)
    verdict = s.verdict if s.verdict is None else compute_verdict(close, mask, safe_t)
    verdict = verdict or "risky"
    titles = SCENARIO_TITLES["purchase" if kind == "purchase" else "other"]
    title = titles[verdict]
    low_i = int(close.argmin())
    low = from_tiyin(int(close[low_i]))
    if verdict == "yes" and low < base.safe_min * Decimal("1.5"):
        title = "Bo'ladi, lekin tor"
        tone = "warning"
    else:
        tone = {"yes": "success", "risky": "warning", "no": "danger"}[verdict]
    crit_neg = [i for i in range(len(close)) if mask[i] and close[i] < 0]
    i = crit_neg[0] if verdict == "no" and crit_neg else low_i
    d = base.date_at(i)
    value = from_tiyin(int(close[i]))
    pays = sorted(
        payments_on(base, d), key=lambda p: (p.category != "payroll", p.priority != "critical")
    )
    word = payment_word(pays[0]) if pays else "to'lovlar"
    if value < 0:
        body = {
            "before": f"{uz.format_date(d, 'da')} {uz.add_case(word, 'ga')} ",
            "strong": f"{uz.format_mln(-value)} yetmaydi",
            "after": ".",
        }
    else:
        near = " — xavfsiz chegaradan sal yuqori" if value < base.safe_min * Decimal("1.5") else ""
        below = " — xavfsiz chegaradan past" if value < base.safe_min else ""
        body = {
            "before": f"{uz.format_date(d, 'da')} ",
            "strong": f"{uz.format_mln(value)} qoladi",
            "after": (below or near) + ".",
        }
    if tip is None:
        month = uz.MONTHS[d.month - 1]
        if kind == "purchase" and recommended_date:
            tip = f"Maslahat: {uz.format_date(recommended_date, 'da')} oling — o'shanda hammasiga yetadi."
        elif s.deferrals:
            tip = "Maslahat: " + deferral_text(s.deferrals[0])
        elif verdict == "yes":
            tip = f"Maslahat: olsangiz, {month}da boshqa katta xarajat qilmang."
        else:
            down = uz.MONTHS[(d - timedelta(days=15)).month - 1]  # the month cash goes down
            tip = (
                f"Maslahat: savdo tushsa, {down}da katta xaridlarni to'xtating va "
                "ta'minotchi bilan muddatni kelishing."
            )
    return {
        "verdict": verdict,
        "tone": tone,
        "title": title,
        "body": body,
        "tip": tip,
        "marker_index": i,
    }
