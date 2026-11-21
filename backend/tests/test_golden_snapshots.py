"""Q1–Q4 are frozen: their full payloads on the Lazzat fixture must equal the saved snapshots."""

import json
import os

import pytest

from tests.golden_snapshot_util import CASES, SNAP, payload
from tests.test_finmodel_golden import connect, load, no_llm  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture(scope="module")
def lazzat(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        b, _ = connect(load("lazzat"), "Lazzat Lavash (snap)")
        yield b


@pytest.mark.parametrize("q", sorted(CASES))
def test_golden_frozen(lazzat, q):
    got = payload(lazzat, q)
    path = SNAP / f"{q}.json"
    if os.environ.get("WRITE_GOLDEN_SNAPSHOTS"):
        path.write_text(json.dumps(got, ensure_ascii=False, indent=1))
    assert got == json.loads(path.read_text()), f"{q} changed — Q1–Q4 are frozen"
