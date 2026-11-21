"""The "no data, no answer" rule: backend authority, no Live token, demo never leaks."""

import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.utils import timezone

from apps.ai import live_api
from apps.finance.models import CashAccount, Transaction
from apps.integrations.models import DataSource
from apps.tenancy.context import tenant_context, today_for
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db
GATED_GET = ["/api/dashboard", "/api/forecast", "/api/calendar", "/api/chat/bootstrap"]


@pytest.fixture
def newcomer():
    c = Client()
    r = c.post(
        "/api/auth/register",
        data=json.dumps(
            {
                "first_name": "Aziz",
                "email": "aziz@example.uz",
                "password": "parol-12345",
                "accept_terms": True,
            }
        ),
        content_type="application/json",
    )
    assert r.status_code == 201, r.content
    me = r.json()
    assert (
        me["onboarding_step"] == "business"
        and me["data_status"] == "no_data"
        and not me["business"]["is_demo"]
    )
    return c, me


def test_new_user_gets_409_everywhere_and_no_live_token(newcomer, monkeypatch):
    c, _ = newcomer
    minted = []
    monkeypatch.setattr(live_api, "mint_token", lambda conf: minted.append(conf))
    for url in GATED_GET:
        r = c.get(url)
        assert r.status_code == 409 and r.json()["code"] == "no_data", url
    for url, body in [
        ("/api/chat/messages", {"text": "25 mln jihoz olsam bo'ladimi?"}),
        ("/api/tools/evaluate_purchase", {"amount": "25000000"}),
        ("/api/simulate", {"preset": "buy"}),
        ("/api/live/session", {}),
    ]:
        r = c.post(url, data=json.dumps(body), content_type="application/json")
        assert r.status_code == 409 and r.json()["code"] == "no_data", url
    assert c.get("/api/live/session/prefetch").status_code == 409
    assert minted == []  # no Live token for a business without data


def test_onboarding_steps_follow_real_state(newcomer):
    c, me = newcomer
    r = c.post(
        "/api/onboarding/business",
        data=json.dumps(
            {
                "name": "Aziz Kafe",
                "kind": "cafe",
                "city": "Toshkent",
                "staff_count": 6,
                "salary_day": 5,
                "safe_min": "5 000 000",
            }
        ),
        content_type="application/json",
    )
    assert r.status_code == 200 and r.json()["onboarding_step"] == "connect"
    b = Business.objects.get(pk=me["business"]["id"])
    assert b.safe_min_balance == Decimal("5000000.00") and b.salary_day == 5
    with tenant_context(b):
        src = DataSource.objects.create(business=b, spreadsheet_id="f1", title="x")
    assert c.get("/api/me").json()["onboarding_step"] == "review"
    src.confirmed = True
    src.save()
    assert c.get("/api/me").json()["onboarding_step"] == "analyzing"
    src.last_synced_at = timezone.now()
    src.save()
    today = today_for(b)
    with tenant_context(b):
        CashAccount.objects.create(
            business=b, opening_balance=Decimal("1000000"), as_of_date=today - timedelta(days=1)
        )
        Transaction.objects.create(
            business=b, amount=Decimal("500000"), direction="in", txn_date=today - timedelta(days=5)
        )
    me2 = c.get("/api/me").json()
    assert (
        me2["onboarding_step"] == "done"
        and me2["data_status"] == "short_history"
        and me2["history_days"] == 6
    )
    assert c.get("/api/dashboard").status_code == 200  # gated only on no_data
    d = c.post(
        "/api/tools/evaluate_purchase",
        data=json.dumps({"amount": "25000000"}),
        content_type="application/json",
    ).json()
    assert d["insufficient_data"] is True and not d.get("verdict")  # no decision on short history
    cash = c.post("/api/tools/get_cash_status", data="{}", content_type="application/json").json()
    assert cash["facts"]["cash"] and "2 haftalik" in cash["answer"]["reason"]  # cash still answered


def test_demo_business_is_separate_and_never_leaks(newcomer):
    c, me = newcomer
    real_id = me["business"]["id"]
    d = c.post("/api/demo/start").json()
    assert d["business"]["is_demo"] and d["business"]["id"] != real_id
    assert d["onboarding_step"] == "done" and d["data_status"] == "ok"
    assert c.get("/api/dashboard").status_code == 200
    assert {b["is_demo"] for b in d["businesses"]} == {True, False}
    again = c.post("/api/demo/start").json()
    assert again["business"]["id"] == d["business"]["id"]  # reused, not re-seeded
    c.post(
        "/api/me/business",
        data=json.dumps({"business_id": real_id}),
        content_type="application/json",
    )
    real = Business.objects.get(pk=real_id)
    with tenant_context(real):
        assert not Transaction.objects.exists() and not CashAccount.objects.exists()
    assert c.get("/api/dashboard").status_code == 409
    assert c.get("/api/me").json()["data_status"] == "no_data"
