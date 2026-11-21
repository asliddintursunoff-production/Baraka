import json

import pytest
from django.core.management import call_command

from apps.insights.forecasting import _cache
from apps.tenancy.models import Business


@pytest.fixture(scope="session")
def django_db_modify_db_settings():
    """No psycopg pool in tests: pooled connections in worker threads block DB teardown."""
    from django.conf import settings
    from django.db import connections

    settings.DATABASES["default"]["OPTIONS"].pop("pool", None)
    connections["default"].settings_dict["OPTIONS"].pop("pool", None)


@pytest.fixture
def debug_on(settings):
    settings.DEBUG = True
    return settings


@pytest.fixture(scope="module")
def demo(django_db_setup, django_db_blocker):
    """seed_demo once per module (data relative to the real today); removed afterwards."""
    with django_db_blocker.unblock():
        call_command("seed_demo", "--reset", verbosity=0)
        navroz = Business.objects.get(seed_tag="demo", name="Navro'z Kafe")
        yield navroz
        from django.contrib.auth import get_user_model

        from apps.knowledge.models import MemoryItem

        MemoryItem.unscoped.filter(meta__seed="demo").delete()
        Business.objects.filter(seed_tag="demo").delete()
        get_user_model().objects.filter(username__endswith="@demo.uz").delete()
        _cache.clear()


@pytest.fixture
def owner_client(client, demo):
    r = client.post(
        "/api/auth/login",
        data=json.dumps({"email": "demo@demo.uz", "password": "demo12345"}),
        content_type="application/json",
    )
    assert r.status_code == 200
    return client
