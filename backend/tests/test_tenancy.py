"""Tenant isolation (spec §5.2): one test group per app — no business ever sees another's rows."""

from datetime import date
from decimal import Decimal

import pytest
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model

from apps.tenancy.context import TenantContextMissing, tenant_context
from apps.tenancy.managers import TenantScopedModel
from apps.tenancy.models import Business, Membership

SCOPED = [m for m in django_apps.get_models() if issubclass(m, TenantScopedModel)]


def test_every_business_table_is_tenant_scoped():
    labels = {m._meta.label for m in SCOPED}
    for expected in (
        "finance.Transaction",
        "finance.Obligation",
        "finance.Counterparty",
        "finance.CashAccount",
        "integrations.DataSource",
        "integrations.GoogleCredential",
        "ingestion.SheetMapping",
        "ingestion.RawRow",
        "ingestion.DataIssue",
        "insights.ForecastSnapshot",
        "insights.Alert",
        "knowledge.BusinessRule",
        "knowledge.RuleCandidate",
        "knowledge.ForecastParams",
        "knowledge.ForecastAccuracy",
        "ai.Conversation",
        "ai.Message",
        "actions.ActionPlan",
        "actions.AuditLog",
    ):
        assert expected in labels


@pytest.mark.django_db
@pytest.mark.parametrize("model", SCOPED, ids=lambda m: m._meta.label)
def test_objects_without_tenant_context_raises(model):
    with pytest.raises(TenantContextMissing):
        list(model.objects.all())
    model.unscoped.count()  # explicit escape hatch for the scheduler / migrations


@pytest.fixture
def two(db):
    a = Business.objects.create(name="A")
    b = Business.objects.create(name="B")
    return a, b


def _make_rows(biz):
    """One row in every app's tables for `biz`."""
    from apps.actions.models import ActionPlan, AuditLog
    from apps.ai.models import Conversation, Message
    from apps.finance.models import CashAccount, Counterparty, Obligation, Transaction
    from apps.ingestion.models import DataIssue, RawRow, SheetMapping
    from apps.insights.models import Alert, ForecastSnapshot
    from apps.integrations.models import DataSource
    from apps.knowledge.models import BusinessRule, ForecastAccuracy, MemoryItem, RuleCandidate

    with tenant_context(biz):
        cp = Counterparty.objects.create(business=biz, name=f"cp-{biz.name}")
        Transaction.objects.create(
            business=biz, amount=Decimal(1), direction="in", txn_date=date.today(), counterparty=cp
        )
        Obligation.objects.create(business=biz, title="x", amount=Decimal(1), due_date=date.today())
        CashAccount.objects.create(
            business=biz, opening_balance=Decimal(1), as_of_date=date.today()
        )
        src = DataSource.objects.create(business=biz, spreadsheet_id=f"s-{biz.name}")
        SheetMapping.objects.create(
            business=biz, source=src, sheet_title="Kirim", sheet_kind="transactions_in"
        )
        raw = RawRow.objects.create(
            business=biz, source=src, sheet_title="Kirim", row_index=1, row_hash=biz.name
        )
        DataIssue.objects.create(business=biz, raw_row=raw, kind="empty_amount", message_uz="x")
        ForecastSnapshot.objects.create(
            business=biz,
            horizon_days=1,
            daily=[],
            min_balance=0,
            min_date=date.today(),
            inputs_hash="h",
            inputs={},
        )
        Alert.objects.create(
            business=biz, kind="k", severity="info", text_uz="x", dedupe_key=f"k-{biz.pk}"
        )
        BusinessRule.objects.create(business=biz, type="ignore", text_uz="x")
        RuleCandidate.objects.create(business=biz, proposed={}, text_uz="x", origin="pattern")
        ForecastAccuracy.objects.create(business=biz, week_start=date.today(), mape=Decimal("0.1"))
        conv = Conversation.objects.create(business=biz)
        Message.objects.create(business=biz, conversation=conv, role="user", content="salom")
        ActionPlan.objects.create(business=biz, kind="reminder", idempotency_key=f"k-{biz.pk}")
        AuditLog.objects.create(business=biz, actor="t", event="e")
        MemoryItem.objects.create(business=biz, kind="note", text=f"secret of {biz.name}")


APP_MODELS = {
    "finance": ["Transaction", "Obligation", "Counterparty", "CashAccount"],
    "integrations": ["DataSource"],
    "ingestion": ["SheetMapping", "RawRow", "DataIssue"],
    "insights": ["ForecastSnapshot", "Alert"],
    "knowledge": ["BusinessRule", "RuleCandidate", "ForecastAccuracy"],
    "ai": ["Conversation", "Message"],
    "actions": ["ActionPlan", "AuditLog"],
}


@pytest.mark.parametrize("app_label", list(APP_MODELS))
def test_app_cannot_see_other_business(two, app_label):
    a, b = two
    _make_rows(a)
    _make_rows(b)
    for name in APP_MODELS[app_label]:
        model = django_apps.get_model(app_label, name)
        with tenant_context(a):
            rows = list(model.objects.all())
            assert rows and all(r.business_id == a.pk for r in rows), name
            assert not model.objects.filter(business_id=b.pk).exists(), name
            assert (
                model.objects.filter(pk__in=model.unscoped.filter(business=b).values("pk")).count()
                == 0
            )


def test_memory_items_global_visible_other_business_never(two):
    from apps.knowledge.models import MemoryItem

    a, b = two
    _make_rows(a)
    _make_rows(b)
    MemoryItem.unscoped.create(business=None, kind="segment_insight", text="global")
    with tenant_context(a):
        texts = set(MemoryItem.objects.values_list("text", flat=True))
    assert texts == {"secret of A", "global"}


def test_saving_other_business_row_inside_context_is_refused(two):
    from apps.finance.models import Obligation

    a, b = two
    with tenant_context(a):
        with pytest.raises(TenantContextMissing):
            Obligation(business=b, title="x", amount=Decimal(1), due_date=date.today()).save()


@pytest.mark.django_db
def test_session_cannot_select_foreign_business(client, demo):
    """A user of business X can never act on business Y, even with a tampered session."""
    User = get_user_model()
    stranger = User.objects.create_user("eve@example.com", "eve@example.com", "pw-123456")
    own = Business.objects.create(name="Eve Shop")
    Membership.objects.create(user=stranger, business=own)
    client.force_login(stranger)
    session = client.session
    session["business_id"] = demo.pk  # tamper
    session.save()
    me = client.get("/api/me").json()
    assert me["business"]["id"] == own.pk
    assert (
        client.post(
            "/api/me/business", data={"business_id": demo.pk}, content_type="application/json"
        ).status_code
        == 403
    )
    dash = client.get("/api/dashboard").json()
    assert dash["business"]["name"] == "Eve Shop"
    assert "Navro'z" not in str(dash)


@pytest.mark.django_db
def test_api_requires_login(client):
    assert client.get("/api/dashboard").status_code in (401, 403)
    assert client.get("/api/forecast").status_code in (401, 403)
