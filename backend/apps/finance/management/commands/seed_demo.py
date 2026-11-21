"""`manage.py seed_demo [--reset] [--export demo_navroz.xlsx]`

Creates the demo login (demo@demo.uz), "Navro'z Kafe" with data relative to today, and 5
synthetic Tashkent cafés for segment knowledge. Works without Google OAuth.
--reset deletes everything seed_demo created before and rebuilds it (any day).
--export also writes the same Navro'z data as a messy multi-sheet .xlsx (dev only).
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from apps.ai import uz_format
from apps.finance.demo import (
    DemoBusiness,
    build_navroz,
    build_peers,
    revenue_band,
)
from apps.finance.models import CashAccount, Counterparty, Obligation, Transaction
from apps.insights.forecasting import invalidate, refresh_forecast
from apps.knowledge.models import (
    BusinessRule,
    ForecastAccuracy,
    ForecastParams,
    MemoryItem,
    RuleCandidate,
)
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Business, Membership

SEED_TAG = "demo"
DEMO_PASSWORD = "demo12345"  # noqa: S105 - public demo login, documented in README
USERS = {
    "owner": ("demo@demo.uz", "Abdusamad", "Karimov"),
    "accountant": ("dilnoza@demo.uz", "Dilnoza", "Rahimova"),
}
SEGMENT_INSIGHTS = [
    ("Yanvarning birinchi haftasida savdo odatda pasayadi", "advice"),
    ("Oylik va kredit bir haftaga tushsa, kassa uzilishi xavfi oshadi", "alerts"),
    ("Yozda ichimlik xarajati oshadi", "later"),
]

COUNTERPARTY_KIND = {
    "NBU": Counterparty.Kind.BANK,
    "Ijara beruvchi": Counterparty.Kind.LANDLORD,
    "Soliq qo'mitasi": Counterparty.Kind.STATE,
}


class Command(BaseCommand):
    help = "Create demo users and businesses (data relative to today)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--reset", action="store_true", help="delete previous demo data first")
        parser.add_argument("--export", metavar="FILE.xlsx", help="also export Navro'z as .xlsx")
        parser.add_argument(
            "--if-empty", action="store_true", help="seed only when no demo data exists (deploys)"
        )

    def handle(self, *args: Any, **opts: Any) -> None:
        today = datetime.now(ZoneInfo("Asia/Tashkent")).date()
        if Business.objects.filter(seed_tag=SEED_TAG).exists():
            if opts.get("if_empty"):
                self.stdout.write("Demo data already exists; nothing to do.")
                return
            if not opts["reset"] and opts.get("export"):
                from apps.finance.demo_export import export_xlsx

                path = export_xlsx(build_navroz(today), opts["export"])
                self.stdout.write(self.style.SUCCESS(f"Exported {path} (demo data unchanged)"))
                return
            if not opts["reset"]:
                raise CommandError("demo data already exists; use --reset to rebuild it")
            self._reset()

        navroz = build_navroz(today)
        peers = build_peers(today)
        with transaction.atomic():
            users = self._users()
            main = self._business(navroz, users)
            for peer in peers:
                self._business(peer, None)
        for b in Business.objects.filter(seed_tag=SEED_TAG):
            invalidate(b.pk)
            refresh_forecast(b)
        from django.core.management import call_command

        from apps.insights.alerts import evaluate_alerts

        call_command("build_segment_stats", stdout=io.StringIO())
        evaluate_alerts(main)

        with tenant_context(main):
            f = refresh_forecast(main).result
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo ready for {today}: {main.name} — kassa {uz_format.format_mln(navroz.closing_cash_today)}, "
                f"eng qiyin kun {uz_format.format_date(f.min_date)} ({uz_format.format_mln(f.min_balance)}). "
                f"Login: {USERS['owner'][0]} / {DEMO_PASSWORD}"
            )
        )
        if opts.get("export"):
            from apps.finance.demo_export import export_xlsx

            path = export_xlsx(navroz, opts["export"])
            self.stdout.write(self.style.SUCCESS(f"Exported {path}"))

    # ------------------------------------------------------------------------------------
    def _reset(self) -> None:
        with transaction.atomic():
            MemoryItem.unscoped.filter(business__isnull=True, meta__seed=SEED_TAG).delete()
            for b in Business.objects.filter(seed_tag=SEED_TAG):
                invalidate(b.pk)
                b.delete()

    def _users(self) -> dict[str, Any]:
        User = get_user_model()
        out = {}
        for role, (email, first, last) in USERS.items():
            user, _ = User.objects.get_or_create(username=email, defaults={"email": email})
            user.email, user.first_name, user.last_name = email, first, last
            user.set_password(DEMO_PASSWORD)
            user.save()
            out[role] = user
        return out

    def _business(
        self,
        biz: DemoBusiness,
        users: dict[str, Any] | None,
        *,
        tag: str = SEED_TAG,
        name: str | None = None,
    ) -> Business:
        monthly = sum(biz.weekday_revenue, Decimal(0)) / 7 * 30
        business = Business.objects.create(
            name=name or biz.name,
            is_demo=True,
            kind=biz.kind,
            city=biz.city,
            safe_min_balance=biz.safe_min,
            staff_count=biz.staff_count,
            segment_key=f"{biz.kind}:toshkent:{revenue_band(monthly)}",
            seed_tag=tag,
        )
        now = datetime.now(ZoneInfo("Asia/Tashkent"))
        with tenant_context(business):
            if users:
                Membership.objects.create(user=users["owner"], business=business, role="owner")
                if users["accountant"] != users["owner"]:
                    Membership.objects.create(
                        user=users["accountant"], business=business, role="accountant"
                    )
            names = {t.counterparty for t in biz.txns if t.counterparty} | {
                o.counterparty for o in biz.obligations if o.counterparty
            }
            cps = {
                n: Counterparty.objects.create(
                    business=business,
                    name=n,
                    kind=COUNTERPARTY_KIND.get(n, Counterparty.Kind.SUPPLIER),
                )
                for n in sorted(names)
            }
            Transaction.objects.bulk_create(
                [
                    Transaction(
                        business=business,
                        amount=t.amount,
                        direction=t.direction,
                        category=t.category,
                        counterparty=cps.get(t.counterparty),
                        txn_date=t.date,
                        method=t.method,
                        note=t.note,
                    )
                    for t in biz.txns
                ],
                batch_size=2000,
            )
            Obligation.objects.bulk_create(
                [
                    Obligation(
                        business=business,
                        title=o.title,
                        amount=o.amount,
                        due_date=o.due_date,
                        priority=o.priority,
                        category=o.category,
                        counterparty=cps.get(o.counterparty),
                        status=o.status,
                        source=Obligation.Source.SHEET,
                        recurrence={"freq": "monthly", "day": o.due_date.day},
                    )
                    for o in biz.obligations
                ]
            )
            CashAccount.objects.create(
                business=business, opening_balance=biz.closing_cash_today, as_of_date=biz.today
            )
            ForecastParams.objects.create(
                business=business,
                weekday_factors=[1.0] * 7,
                variable_cost_ratio=biz.variable_cost_ratio,
            )
            for week_start, mape in biz.accuracy:
                ForecastAccuracy.objects.create(business=business, week_start=week_start, mape=mape)
            if users:
                self._knowledge(business, biz, users, now)
        return business

    def _knowledge(
        self, business: Business, biz: DemoBusiness, users: dict[str, Any], now: datetime
    ) -> None:
        for r in biz.rules:
            rule = BusinessRule.objects.create(
                business=business,
                type=r.type,
                target=r.target,
                effect=r.effect,
                text_uz=r.text_uz,
                source=r.source,
                author=users[r.author],
            )
            created = now - timedelta(days=r.days_ago)
            BusinessRule.objects.filter(pk=rule.pk).update(created_at=created)
            item = MemoryItem.objects.create(
                business=business,
                kind=MemoryItem.Kind.RULE,
                text=r.text_uz,
                meta={"rule_id": rule.pk, "source": r.source, "seed": SEED_TAG},
            )
            MemoryItem.objects.filter(pk=item.pk).update(created_at=created)
        svet = biz.svet_amount
        RuleCandidate.objects.create(
            business=business,
            proposed={
                "type": "recurring",
                "target": {"title": "Svet", "category": "kommunal"},
                "effect": {"amount": str(svet), "day_of_month": 3, "priority": "critical"},
            },
            text_uz=(
                f'Har oyning 3-sanasida "Svet" uchun taxminan {uz_format.format_mln(svet)} '
                "to'lanayotganini ko'rdim. Buni har oylik doimiy to'lov sifatida hisoblaymi?"
            ),
            origin=RuleCandidate.Origin.PATTERN,
        )
        for text, usage in SEGMENT_INSIGHTS:
            if MemoryItem.unscoped.filter(
                business__isnull=True, kind=MemoryItem.Kind.SEGMENT, text=text
            ).exists():
                continue  # global insight: once, however many demo businesses exist
            MemoryItem.unscoped.create(
                business=None,
                kind=MemoryItem.Kind.SEGMENT,
                text=text,
                meta={
                    "segment_key": business.segment_key,
                    "n_businesses": 6,
                    "usage": usage,
                    "seed": SEED_TAG,
                },
            )
