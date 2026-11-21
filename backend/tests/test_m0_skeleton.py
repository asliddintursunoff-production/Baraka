"""M0 acceptance: health, APP_NAME injection, env contract, pgvector, Server-Timing."""

import json
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.db import connection

from config import views

REPO = Path(settings.BASE_DIR).parent


@pytest.mark.django_db
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "app": settings.APP_NAME}


@pytest.mark.django_db
def test_health_deep_checks_db(client):
    r = client.get("/api/health?deep=1")
    assert r.json()["db"] is True


@pytest.mark.django_db
def test_pgvector_extension_enabled():
    with connection.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        assert cur.fetchone() == (1,)


def test_env_example_has_exactly_the_allowed_keys():
    keys = [
        line.split("=", 1)[0]
        for line in (REPO / ".env.example").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert keys == list(settings_module().ENV_KEYS)
    assert len(keys) == 9  # spec's 8 + GOOGLE_PICKER_API_KEY (user decision, M5)


def settings_module():
    import config.settings as s

    return s


def test_settings_reads_env_only_through_allowlist():
    src = (Path(settings.BASE_DIR) / "config" / "settings.py").read_text()
    # every _env("X") is one of the 8 keys; no other os.environ / getenv access
    for key in re.findall(r'_env\("([A-Z_]+)"', src):
        assert key in settings_module().ENV_KEYS
    assert "os.getenv" not in src
    assert src.count("os.environ.get(") == 1  # inside _env only
    for other in Path(settings.BASE_DIR).joinpath("apps").rglob("*.py"):
        text = other.read_text()
        assert "os.environ" not in text and "os.getenv" not in text, other


def test_app_config_js_sets_name_and_csrf_cookie(client):
    r = client.get("/app-config.js")
    assert r.status_code == 200
    body = r.content.decode()
    assert body.startswith("window.__APP_CONFIG__ = ")
    assert json.loads(body.split("=", 1)[1].rstrip(";"))["appName"] == settings.APP_NAME
    assert "csrftoken" in r.cookies


def test_index_injection(tmp_path, settings):
    settings.FRONTEND_DIST = tmp_path
    (tmp_path / "index.html").write_text(
        f"<html><head><title>…</title>{views.APP_CONFIG_TAG}</head><body></body></html>"
    )
    settings.APP_NAME = "Test <Pilot>"
    page = views._read_index()
    assert page is not None
    assert "<title>Test &lt;Pilot&gt;</title>" in page
    assert '"appName": "Test \\u003cPilot>"' in page
    assert views.APP_CONFIG_TAG not in page


@pytest.mark.django_db
def test_spa_route_without_build_explains(client, settings, tmp_path):
    settings.FRONTEND_DIST = tmp_path  # empty: no build
    r = client.get("/forecast")
    assert r.status_code == 503
    assert settings.APP_NAME.encode() in r.content


@pytest.mark.django_db
def test_server_timing_header_has_db_and_total(client):
    r = client.get("/api/health?deep=1")
    header = r["Server-Timing"]
    assert "total;dur=" in header
    assert "db;dur=" in header


def test_frontend_bundle_has_no_secrets():
    dist = REPO / "frontend" / "dist"
    if not dist.is_dir():
        pytest.skip("frontend not built")
    secrets = [s for s in (settings.GEMINI_API_KEY, settings.GOOGLE_OAUTH_CLIENT_SECRET) if s]
    for f in dist.rglob("*"):
        if f.is_file() and f.suffix in {".js", ".html", ".css", ".map", ".json"}:
            text = f.read_text(errors="ignore")
            assert "GEMINI_API_KEY" not in text
            for s in secrets:
                assert s not in text, f
