"""M6: template alerts with dedupe, the 08:00 brief, the bell API (no LLM anywhere)."""

import pytest

from apps.insights.alerts import daily_brief, evaluate_alerts
from apps.insights.models import Alert
from apps.tenancy.context import tenant_context

pytestmark = pytest.mark.django_db


def test_alerts_dedupe_brief_and_bell(owner_client, demo, monkeypatch):
    monkeypatch.setattr(
        "apps.ai.llm.generate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no LLM"))
    )
    with tenant_context(demo):
        Alert.objects.all().delete()
    assert evaluate_alerts(demo) >= 1
    assert evaluate_alerts(demo) == 0  # same condition -> same alert, updated in place
    with tenant_context(demo):
        kinds = set(Alert.objects.values_list("kind", flat=True))
    assert "payroll_loan_week" in kinds
    brief = daily_brief(demo)
    assert brief.text_uz.startswith("Xayrli tong!") and "Eng qiyin kun" in brief.text_uz
    d = owner_client.get("/api/alerts").json()["alerts"]
    assert any(a["kind"] == "brief" for a in d) and any(a["new"] for a in d)
    assert owner_client.post("/api/alerts").json()["ok"]
    assert owner_client.get("/api/dashboard").json()["alerts"]["new"] == 0
