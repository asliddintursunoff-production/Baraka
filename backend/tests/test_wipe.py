import json

import pytest

from apps.finance.models import Transaction
from apps.tenancy.context import tenant_context

pytestmark = pytest.mark.django_db


def test_wipe_all_data(owner_client, demo):
    r = owner_client.post(
        "/api/business/wipe", data=json.dumps({"confirm": "x"}), content_type="application/json"
    )
    assert r.status_code == 400
    with tenant_context(demo):
        assert Transaction.objects.exists()
    r = owner_client.post(
        "/api/business/wipe",
        data=json.dumps({"confirm": "O'CHIRISH"}),
        content_type="application/json",
    )
    assert r.status_code == 200 and r.json()["deleted"] > 0
    with tenant_context(demo):
        assert not Transaction.objects.exists()
