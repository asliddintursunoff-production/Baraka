"""M5: OAuth (Google mocked), readers, ingestion of the real demo export, sync behaviour."""

import io
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.ai.llm import AllModelsFailed
from apps.finance.demo import build_navroz
from apps.finance.demo_export import closing_cash_yesterday, export_xlsx
from apps.finance.models import CashAccount, Obligation, Transaction
from apps.ingestion.mapping import heuristic_sheet
from apps.ingestion.models import DataIssue, SheetMapping
from apps.ingestion.readers import FakeReader, WorkbookData, set_reader_override, xlsx_sheets
from apps.ingestion.sync import save_mapping, sync_business
from apps.insights.forecasting import get_forecast
from apps.integrations import api as gapi
from apps.integrations import google
from apps.integrations.crypto import decrypt, encrypt
from apps.integrations.models import DataSource, GoogleCredential
from apps.tenancy.context import tenant_context, today_for
from apps.tenancy.models import Business, Membership

pytestmark = pytest.mark.django_db
M = Decimal(1_000_000)


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    async def busy(*a, **k):
        raise AllModelsFailed("tests never call Gemini")

    monkeypatch.setattr("apps.ai.llm.generate", busy)
    yield
    set_reader_override(None)


# --- OAuth -------------------------------------------------------------------------------
@pytest.fixture
def google_configured(settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = "123456789012-abc.apps.googleusercontent.com"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "secret"
    settings.GOOGLE_PICKER_API_KEY = "picker-key"


def test_oauth_start_and_callback_store_encrypted_token(
    owner_client, demo, google_configured, monkeypatch
):
    monkeypatch.setattr(
        google,
        "start_auth",
        lambda **k: google.StartedAuth(
            "https://accounts.google.com/o/oauth2/auth?x=1", "STATE1", "VERIFIER"
        ),
    )
    r = owner_client.get("/api/integrations/google/start?next=/onboarding/connect?step=pick")
    assert r.status_code == 302 and r["Location"].startswith("https://accounts.google.com/")
    seen = {}

    def fake_exchange(code, *, state, code_verifier):
        seen.update(code=code, state=state, verifier=code_verifier)
        return google.ExchangedTokens(
            "REFRESH-XYZ", "ACCESS", None, "asliddin@example.com", "openid email drive.file"
        )

    monkeypatch.setattr(google, "exchange_code", fake_exchange)
    r = owner_client.get("/api/integrations/google/callback?state=STATE1&code=CODE")
    assert r.status_code == 302 and r["Location"] == "/onboarding/connect?step=pick"
    assert seen == {"code": "CODE", "state": "STATE1", "verifier": "VERIFIER"}
    with tenant_context(demo):
        cred = GoogleCredential.objects.get()
    assert (
        cred.encrypted_refresh_token != "REFRESH-XYZ"
        and decrypt(cred.encrypted_refresh_token) == "REFRESH-XYZ"
    )
    assert cred.email == "asliddin@example.com"
    # state is single-use
    r = owner_client.get("/api/integrations/google/callback?state=STATE1&code=CODE")
    assert "error=invalid_state" in r["Location"]
    with tenant_context(demo):
        GoogleCredential.objects.all().delete()


def test_oauth_errors_and_open_redirect(owner_client, demo, google_configured, monkeypatch):
    monkeypatch.setattr(
        google,
        "start_auth",
        lambda **k: google.StartedAuth("https://accounts.google.com/x", "S2", None),
    )
    owner_client.get("/api/integrations/google/start?next=//evil.example.com")
    assert owner_client.session[gapi.SESSION_KEY]["next"] == "/onboarding/connect?step=pick"
    r = owner_client.get("/api/integrations/google/callback?error=access_denied&state=S2")
    assert "error=access_denied" in r["Location"] and "message=" in r["Location"]
    owner_client.get("/api/integrations/google/start")
    r = owner_client.get("/api/integrations/google/callback?state=WRONG&code=x")
    assert "error=invalid_state" in r["Location"]


def test_picker_config_never_exposes_refresh_token(
    owner_client, demo, google_configured, monkeypatch
):
    from datetime import UTC, datetime

    monkeypatch.setattr(
        google, "access_token", lambda b: ("ya29.short", datetime(2030, 1, 1, tzinfo=UTC))
    )
    d = owner_client.get("/api/integrations/google/picker-config").json()
    assert d == {
        "access_token": "ya29.short",
        "developer_key": "picker-key",
        "app_id": "123456789012",
        "expires_at": "2030-01-01T00:00:00+00:00",
    }


def test_invalid_grant_marks_reauth(demo, monkeypatch, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID, settings.GOOGLE_OAUTH_CLIENT_SECRET = "1-x", "s"
    from google.auth.exceptions import RefreshError

    with tenant_context(demo):
        src = DataSource.objects.create(
            business=demo, spreadsheet_id="f1", title="x", confirmed=True
        )
        GoogleCredential.objects.create(business=demo, encrypted_refresh_token=encrypt("R"))
    monkeypatch.setattr(
        "google.oauth2.credentials.Credentials.refresh",
        lambda self, req: (_ for _ in ()).throw(
            RefreshError("invalid_grant: Token has been expired or revoked.")
        ),
    )
    google._token_cache.clear()
    with pytest.raises(google.ReauthRequired):
        google.credentials(demo)
    with tenant_context(demo):
        src.refresh_from_db()
        assert src.status == DataSource.Status.REAUTH
        src.delete()
        GoogleCredential.objects.all().delete()


# --- ingestion of the real demo export ----------------------------------------------
@pytest.fixture
def demo_book(demo, tmp_path):
    biz = build_navroz(today_for(demo))
    path = export_xlsx(biz, tmp_path / "demo.xlsx")
    sheets = xlsx_sheets(path.read_bytes())
    wb = WorkbookData("file-demo", "demo_navroz", "2026-11-21T10:00:00Z", sheets)
    reader = FakeReader({"file-demo": wb})
    set_reader_override(reader)
    return biz, wb, reader


def test_heuristic_proposals_for_demo_sheets(demo_book):
    _, wb, _ = demo_book
    kinds = {s.title: heuristic_sheet(s).kind for s in wb.sheets}
    assert kinds["Kirim"] == "transactions_in"
    assert kinds["Chiqim"] == "transactions_out"
    assert kinds["Oylik"] == "payroll"
    assert kinds["NBU kredit"] == "loan_schedule"
    assert kinds["Kassa"] == "cash_balance"
    assert kinds["Izohlar"] == "ignore"
    kirim = heuristic_sheet(next(s for s in wb.sheets if s.title == "Kirim"))
    assert kirim.header_row == 3


def _connect(demo, wb):
    with tenant_context(demo):
        src = DataSource.objects.create(
            business=demo,
            spreadsheet_id="file-demo",
            title="demo_navroz",
            kind="xlsx",
            confirmed=True,
        )
        for s in wb.sheets:
            save_mapping(demo, src, heuristic_sheet(s))
    return src


def test_demo_sheet_reproduces_the_seed_forecast(demo, demo_book):
    biz, wb, reader = demo_book
    seed_min = get_forecast(demo).result.min_balance
    _connect(demo, wb)
    s = sync_business(demo, trigger="confirm", force=True, progress=lambda t, p: None, first=True)
    assert s.rows_added > 400 and s.cash_found
    with tenant_context(demo):
        cash = CashAccount.objects.get()
        assert cash.opening_balance == closing_cash_yesterday(
            biz
        ) and cash.as_of_date == biz.today - timedelta(days=1)
        assert not Transaction.objects.filter(raw_row__isnull=True).exists()  # seed rows replaced
        kinds = set(DataIssue.objects.filter(status="open").values_list("kind", flat=True))
        assert {"duplicate", "empty_amount", "invalid_date"} <= kinds
        demo.refresh_from_db()
        assert demo.staff_count == 15
    sheet_min = get_forecast(demo).result.min_balance
    assert abs(sheet_min - seed_min) <= Decimal("100000"), (sheet_min, seed_min)

    # unchanged modifiedTime -> nothing is read
    reads = reader.reads
    s2 = sync_business(demo, trigger="schedule", force=False, progress=lambda t, p: None)
    assert reader.reads == reads and s2.skipped == 1

    # a new expense row today -> read, +1 row, cash lower
    chiqim = next(sh for sh in wb.sheets if sh.title == "Chiqim")
    today = today_for(demo)
    chiqim.rows.append(
        [today.strftime("%d.%m.%Y"), "3 000 000", "remont", "Usta Akmal", None, "Naqd", "to'landi"]
    )
    wb.modified_time = "2026-11-21T11:00:00Z"
    before = get_forecast(demo).result.close_on(today)
    s3 = sync_business(demo, trigger="manual", force=False, progress=lambda t, p: None)
    assert s3.rows_added == 1
    assert get_forecast(demo).result.close_on(today) == before - 3 * M

    # the row is deleted again -> its transaction disappears
    chiqim.rows.pop()
    wb.modified_time = "2026-11-21T12:00:00Z"
    s4 = sync_business(demo, trigger="manual", force=False, progress=lambda t, p: None)
    assert s4.rows_deleted == 1
    assert get_forecast(demo).result.close_on(today) == before
    with tenant_context(demo):
        assert (
            Obligation.objects.filter(category="loan").count()
            == Obligation.objects.filter(category="loan").values("due_date").distinct().count()
        )


def test_sources_page_and_issue_resolution(owner_client, demo, demo_book):
    _, wb, _ = demo_book
    _connect(demo, wb)
    sync_business(demo, trigger="confirm", force=True, progress=lambda t, p: None, first=True)
    d = owner_client.get("/api/sources").json()
    assert d["files"] and d["issues"] and d["log"]
    bad_date = next(i for i in d["issues"] if i["action"] == "use_suggestion")
    r = owner_client.post(
        f"/api/sources/issues/{bad_date['id']}/resolve",
        data=json.dumps({"action": "use_suggestion"}),
        content_type="application/json",
    )
    assert r.json() == {"ok": True}
    empty = next(i for i in d["issues"] if i["action"] == "set_amount")
    r = owner_client.post(
        f"/api/sources/issues/{empty['id']}/resolve",
        data=json.dumps({"action": "set_amount", "value": "120 000"}),
        content_type="application/json",
    )
    assert r.json() == {"ok": True}


def test_sources_are_tenant_isolated(client, demo, demo_book):
    _, wb, _ = demo_book
    src = _connect(demo, wb)
    User = get_user_model()
    eve = User.objects.create_user("eve2@example.com", "eve2@example.com", "pw-123456")
    other = Business.objects.create(name="Other")
    Membership.objects.create(user=eve, business=other)
    client.force_login(eve)
    assert client.post(f"/api/sources/{src.pk}/remap").status_code == 404
    assert client.get("/api/sources").json()["files"] == []
    with tenant_context(other):
        assert not DataSource.objects.exists() and not SheetMapping.objects.exists()


def test_xlsx_reader_reads_dates_and_numbers(demo):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "T"
    ws.append(["Sana", "Summa"])
    ws.append([today_for(demo) - timedelta(days=1), 1500000])
    out = io.BytesIO()
    wb.save(out)
    sheets = xlsx_sheets(out.getvalue())
    assert sheets[0].title == "T" and sheets[0].rows[1][1] == 1500000


def test_loan_sheet_uses_total_payment_not_remaining_debt(demo, demo_book):
    """The UI may confirm every money column as `amount`: the payment is "Jami to'lov"."""
    _, wb, _ = demo_book
    _connect(demo, wb)
    with tenant_context(demo):
        m = SheetMapping.objects.get(sheet_title="NBU kredit")
        m.column_map = {"0": "due_date", "1": "amount", "2": "amount", "3": "amount", "4": "amount"}
        m.save()
    sync_business(demo, trigger="confirm", force=True, progress=lambda t, p: None, first=True)
    with tenant_context(demo):
        loans = set(
            Obligation.objects.filter(category="loan", status="planned").values_list(
                "amount", flat=True
            )
        )
    assert loans and max(loans) < 20 * M, loans
