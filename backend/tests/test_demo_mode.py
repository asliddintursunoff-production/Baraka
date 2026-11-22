"""DEMO_GOLDEN_ONLY: Q1–Q4 only, frozen answers, zero LLM calls (chat + Live use demo.answer)."""

import json
from pathlib import Path

import pytest

from apps.ai import demo
from apps.ai.tools import ToolContext
from apps.tenancy.context import tenant_context
from tests.test_finmodel_golden import connect, load, no_llm  # noqa: F401

pytestmark = pytest.mark.django_db
PIN = Path(__file__).resolve().parents[1] / "apps" / "ai" / "data" / "golden"

# 10 paraphrases per golden that must give the FROZEN base answer (incl. speech-to-text typos)
BASE = {
    "channel_economics": [
        "Yandex va Uzum menga foydalimi yoki o'z dostavkamni kuchaytiraymi?",
        "Agregatorlar foydalimi?",
        "O'z dostavkam foydaliroqmi yoki Uzum Tezkor?",
        "Qaysi savdo kanali eng foydali?",
        "Dostavkadan qancha foyda qolyapti?",
        "Uzum komissiyasi meni yeb qo'yyaptimi?",
        "yandeks va uzum foydalimi",
        "agrigatorlar menga foyda beryaptimi",
        "o'z dastavkam yaxshimi yoki yandeks",
        "Yandex Eats foydalimi?",
    ],
    "hire_payback": [
        "Yana bitta ofitsiant olsam, u o'zini necha oyda oqlaydi?",
        "Yana bitta ofitsam olsam, o'zini oqlaydimi?",
        "yana bitta ofitsant olsam o'zini oqlaydimi",
        "ofitsiant olsam arziydimi",
        "Ofitsiant olishim kerakmi?",
        "yana bir ofitsiant kerakmi",
        "ofisiant olsam necha oyda oqlaydi",
        "Yangi ofitsiant olsam foyda bo'ladimi?",
        "ofitsiyant olsam o'zini oqlaydimi",
        "Zalga ofitsiant olsam-chi?",
    ],
    "equipment_investment": [
        "25 millionga lavash apparat olmoqchiman — investitsiyami yoki zarariga ishlaydimi?",
        "25 millionga yana bitta stansiya olsam foyda bo'ladimi?",
        "Yangi lavash apparati olsam arziydimi?",
        "Apparat olsam necha oyda o'zini qoplaydi?",
        "lavash aparat olsam arziydimi",
        "aparat olmoqchiman zarariga ishlaydimi",
        "Lavash apparati olsam zarar bo'ladimi?",
        "yangi apparat olsam qoplaydimi",
        "lavash apparad olsam arziydimi",
        "25 million so'mga apparat olsam investitsiyami?",
    ],
    "revenue_growth_plan": [
        "Korxona daromadini 10 foizga qisqa muddatda oshirish uchun strategiya tuzib ber.",
        "Daromadimni tezda 10% ga qanday oshiraman?",
        "Savdoni qanday ko'paytirsam bo'ladi?",
        "Keyingi oyda tushumni oshirish rejasi kerak.",
        "Mijozlarni qanday ko'paytiraman?",
        "O'rtacha chekni qanday oshiraman?",
        "Sotuvni oshirish uchun qanday aksiya qilay?",
        "daromadni o'n foizga oshirish strategiyasi",
        "savdoni oshirish strategi kerak",
        "tushumni qanday oshirsam bo'ladi",
    ],
}
PIN_BY_INTENT = {
    json.loads(f.read_text())["intent"]: json.loads(f.read_text())
    for f in PIN.glob("Q*.pinned.json")
}


@pytest.fixture(scope="module")
def lazzat(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        b, _ = connect(load("lazzat"), "Lazzat (demo)")
        yield b


def ask(b, text, prev=None):
    with tenant_context(b):
        return demo.answer(ToolContext(b, 0, "chat", last_user_text=text), text, prev)


@pytest.fixture
def llm_calls(monkeypatch):
    calls = []

    async def spy(*a, **k):
        calls.append(1)
        raise AssertionError("LLM must not be called in demo mode")

    monkeypatch.setattr("apps.ai.llm.generate", spy)
    monkeypatch.setattr("apps.ai.budget.generate_sync", lambda *a, **k: calls.append(1))
    return calls


@pytest.mark.parametrize("intent", list(BASE))
def test_golden_exact(lazzat, intent, llm_calls):
    pin = PIN_BY_INTENT[intent]
    speech = " ".join(s["text"] for s in pin["speech_segments"] if s["text"])
    for q in BASE[intent]:
        r = ask(lazzat, q)
        assert r["kind"] == "golden" and r["intent"] == intent, q
        assert r["blocks"] == [pin["report"]], q  # the frozen card, unchanged
        assert r["say"] == speech, q  # Live transcript == the md speech
    assert llm_calls == []


def test_question_cards_route_to_their_golden(lazzat):
    for c in demo.question_cards():
        r = ask(lazzat, c["text"])
        assert (r["kind"], r["intent"]) == ("golden", c["intent"]), c


@pytest.mark.parametrize(
    "text,kind",
    [
        ("salom", "greeting"),
        ("Assalomu alaykum", "greeting"),
        ("qanaysan", "greeting"),
        ("Ertaga ob-havo qanday bo'ladi?", "other"),
        ("O'tgan oy qancha foyda qildim?", "other"),
    ],
)
def test_other_gets_fixed_reply_with_4_cards(lazzat, text, kind, llm_calls):
    r = ask(lazzat, text)
    assert r["kind"] == kind and len(r["cards"]) == 4
    assert demo.OTHER_TEXT in r["markdown"]
    assert llm_calls == []


def test_charts_request_opens_active_card(lazzat, llm_calls):
    first = ask(lazzat, "Yana bitta ofitsiant olsam, u o'zini necha oyda oqlaydi?")
    r = ask(lazzat, "Qanaqadir diagrammalar bormi yo statistika?", prev=first["intent"])
    assert r["kind"] == "charts" and r["expand"] and r["blocks"] == first["blocks"]
    assert r["say"] == demo.CHARTS_SAY
    assert llm_calls == []


def test_side_and_explain_and_decline(lazzat, llm_calls):
    q1 = ask(lazzat, "Agregatorlar foydalimi?")
    side = ask(lazzat, "50% ini o'tkazsam-chi?", prev=q1["intent"])
    assert side["kind"] == "side" and "2,37" in side["markdown"]
    nega = ask(lazzat, "Nega bunday chiqdi?", prev="hire_payback")
    assert nega["kind"] == "explain" and nega["markdown"].startswith("### Qanday hisobladim")
    assert ask(lazzat, "yo'q", prev="hire_payback")["kind"] == "decline"
    assert llm_calls == []


def test_param_change_is_computed_not_fixed(lazzat):
    r = ask(lazzat, "Yana bir oshpaz kerakmi?")
    assert r["intent"] == "hire_payback" and r["kind"] in ("param", "golden")
    assert r["kind"] != "other"


def test_live_regression_transcript(lazzat, llm_calls):
    """Section 0 transcript: cards shown, frozen speech, all Q4 actions spoken."""
    a = ask(lazzat, "Hozir yangi oshpaz olmoqchiman.")
    assert a["intent"] == "hire_payback" and a["blocks"] and "hisoblayman" not in a["say"].lower()
    b = ask(lazzat, "Qanaqadir diagrammalar bormi yo statistika?", prev=a["intent"])
    assert b["kind"] == "charts" and b["blocks"]
    c = ask(
        lazzat, "Men qisqa muddatda biznesimga 10% daromadimni oshirmoqchiman", prev=a["intent"]
    )
    pin = PIN_BY_INTENT["revenue_growth_plan"]
    assert c["kind"] == "golden" and c["say"] == " ".join(
        s["text"] for s in pin["speech_segments"] if s["text"]
    )
    assert llm_calls == []
