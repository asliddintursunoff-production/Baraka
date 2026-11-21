"""Catalogue registry + routing isolation: Q1–Q4 always win; no catalogue variant overlaps a golden paraphrase."""

import re
from pathlib import Path

import pytest

from apps.ai.catalog import OVERLAP_MAX, is_bad_intent, registry, route_catalog, similarity
from apps.ai.golden_tools import match as golden_match

GOLDEN = Path(__file__).resolve().parents[2] / "golden"
EXTRA = {
    "channel_economics": [
        "Yandex komissiyasi juda katta emasmi?",
        "Uzum orqali sotish foydalimi?",
        "Agregatordan chiqib ketsam nima bo'ladi?",
        "O'z dostavkamni kuchaytirsam-chi?",
        "Kuryer yoki agregator — qaysi biri foydali?",
    ],
    "hire_payback": [
        "Yana ofitsiant olsam arziydimi?",
        "Yangi ishchi olsam o'zini oqlaydimi?",
        "Kassir qo'shsam foyda bo'ladimi?",
        "Yana bitta oshpaz kerakmi?",
        "Ishchi olish vaqti keldimi?",
    ],
    "equipment_investment": [
        "Lavash apparat olsam qoplaydimi?",
        "Yangi fritur olsam arziydimi?",
        "30 millionga apparat olsam-chi?",
        "Uskuna olsam necha oyda qoplaydi?",
        "Pech olsam zarariga ishlaydimi?",
    ],
    "revenue_growth_plan": [
        "Daromadni 10% ga oshirish rejasi",
        "Savdoni qanday ko'paytiraman?",
        "Tushumni oshirish strategiyasi tuz",
        "Mijozlarni qanday ko'paytiraman?",
        "O'rtacha chekni qanday oshiraman?",
    ],
}


def golden_paraphrases() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for f in sorted(GOLDEN.glob("Q[1-4]_*.md")):
        text = f.read_text()
        intent = re.search(r"intent:\s*`([^`]+)`", text).group(1)
        sec = text.split("## 1.", 1)[1].split("**Parametr", 1)[0].split("\n---", 1)[0]
        out[intent] = [ln.lstrip("- ").strip() for ln in sec.splitlines() if ln.startswith("- ")]
    return out


def test_registry_100_unique():
    reg = registry()
    assert len(reg) == 100
    assert len({it.intent for it in reg.values()}) == 100
    s18 = reg["S18"]
    assert s18.intent == "cash_risk_3m" and s18.variants and s18.live and len(s18.kpis) == 3


def test_no_overlap_with_golden():
    gp = golden_paraphrases()
    bad = []
    for it in registry().values():
        for ph in it.phrases:
            for intent, paras in gp.items():
                for gq in paras:
                    if similarity(ph, gq) >= OVERLAP_MAX:
                        bad.append((it.id, ph, intent, gq))
    assert not bad, bad


@pytest.mark.parametrize(
    "intent", ["channel_economics", "hire_payback", "equipment_investment", "revenue_growth_plan"]
)
def test_golden_paraphrases_route_to_golden(intent):
    for q in golden_paraphrases()[intent] + EXTRA[intent]:
        g = golden_match(q)
        assert g is not None and g[0].id == intent, (intent, q, g and g[0].id)
        assert route_catalog(q) is None, q


def test_bad_intent():
    assert is_bad_intent("Biznesimni qulatmoqchiman")
    assert is_bad_intent("biznesni uxlatmoqchiman")
    assert not is_bad_intent("Biznesimni nima qulatishi mumkin?")
