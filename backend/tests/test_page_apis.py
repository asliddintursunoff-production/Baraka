"""M2 page APIs on the seeded demo: one request per page, query budgets, real numbers."""

import json
from datetime import timedelta

import pytest

from apps.ai.uz_format import format_date
from apps.insights.forecasting import _cache, get_forecast
from apps.tenancy.context import today_for

pytestmark = pytest.mark.django_db


def test_login_and_me(owner_client):
    me = owner_client.get("/api/me").json()
    assert me["user"]["first_name"] == "Abdusamad"
    assert me["business"]["name"] == "Navro'z Kafe"


def test_bad_login(client, demo):
    r = client.post(
        "/api/auth/login",
        data=json.dumps({"email": "demo@demo.uz", "password": "x"}),
        content_type="application/json",
    )
    assert r.status_code == 400 and r.json()["message"] == "Email yoki parol noto'g'ri."


def test_dashboard(owner_client, demo, django_assert_max_num_queries):
    owner_client.get("/api/dashboard")
    with django_assert_max_num_queries(18):  # +4: two-panel chart history, +growth steps
        r = owner_client.get("/api/dashboard")
    d = r.json()
    base = get_forecast(demo).result
    assert d["forecast"]["summaries"]["60"]["lowest_display"] == "18,8 mln"
    assert d["banner"]["headline"].startswith("Pulingiz yetadi.")
    assert format_date(base.min_date, "ga") in d["banner"]["headline"]
    assert len(d["kpis"]) == 4 and len(d["steps"]) == 3
    assert len(d["forecast"]["series"]) == 91
    assert d["upcoming"]["rows"] and d["monthly"]
    assert {n["kind"] for n in d["news"]} == {"learned", "segment"}
    assert "Server-Timing" in r


def test_forecast_page(owner_client, django_assert_max_num_queries):
    owner_client.get("/api/forecast")
    with django_assert_max_num_queries(8):  # +4: two-panel chart history
        f = owner_client.get("/api/forecast").json()
    ids = [p["id"] for p in f["presets"]]
    assert ids == ["buy", "rev", "staff"]
    buy = f["presets"][0]["card"]
    assert buy["verdict"] == "no" and buy["title"] == "Yo'q, hozir emas"
    assert "6,2 mln yetmaydi" == buy["body"]["strong"]
    assert len(f["presets"][0]["overlay"]) == 91
    assert any(k["hardest"] for k in f["key_days"])


def test_simulate_presets_and_free_text(owner_client):
    r = owner_client.post(
        "/api/simulate", data=json.dumps({"preset": "staff"}), content_type="application/json"
    )
    assert r.json()["card"]["body"]["strong"] == "12,8 mln qoladi"
    r = owner_client.post(
        "/api/simulate",
        data=json.dumps({"text": "Savdo 20% kamaysa"}),
        content_type="application/json",
    )
    assert r.json()["card"]["verdict"] in {"no", "risky"}
    r = owner_client.post(
        "/api/simulate", data=json.dumps({"text": "hmm"}), content_type="application/json"
    )
    assert r.status_code == 422


def test_calendar(owner_client, demo, django_assert_max_num_queries):
    owner_client.get("/api/calendar")
    with django_assert_max_num_queries(4):
        c = owner_client.get("/api/calendar").json()
    hot = [d for d in c["days"] if d["kind"] == "hot"]
    assert len(hot) <= 1
    if hot:
        detail = hot[0]["detail"]
        assert detail["full"] and detail["rows"][0]["label"] == "Kun boshida kassada"
    assert c["lead"] in range(7) and len(c["weekdays"]) == 7
    nxt = owner_client.get(f"/api/calendar?month={c['next']}").json()
    assert nxt["month"] == c["next"]
    assert owner_client.get("/api/calendar?month=bad").status_code == 400


def test_add_manual_payment_updates_forecast(owner_client, demo):
    before = get_forecast(demo).result.min_balance
    when = today_for(demo) + timedelta(days=3)
    r = owner_client.post(
        "/api/obligations",
        data=json.dumps(
            {
                "title": "Yangi muzlatgich",
                "amount": "5000000",
                "due_date": when.isoformat(),
                "priority": "discretionary",
            }
        ),
        content_type="application/json",
    )
    assert r.status_code == 201
    assert get_forecast(demo).result.min_balance == before - 5_000_000


def test_snapshot_cache_paths(demo, django_assert_max_num_queries):
    get_forecast(demo)
    with django_assert_max_num_queries(1):
        get_forecast(demo)  # hit: 1 SELECT
    _cache.clear()
    with django_assert_max_num_queries(2):
        get_forecast(demo)  # rebuilt from the snapshot's stored inputs
