"""Tier 2: the 100-question catalogue (golden/catalog/AI_CFO_100_savol_shablonlar.md).

Routing order (cfo_router.route): Tier 1 golden Q1–Q4 (always first) → lexical guard (golden markers
never go to the catalogue) → Tier 2 catalogue (only implemented intents, score ≥ CATALOG_MIN) →
Tier 3 full-context chat. Similarity is a deterministic bag-of-stems + char-trigram cosine (no
embedding calls); the same metric drives the build-time overlap test against Q1–Q4 paraphrases.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG_MD = Path(__file__).parent / "data" / "catalog" / "AI_CFO_100_savol_shablonlar.md"
CATALOG_MIN = 0.55  # route to the catalogue only above this score
OVERLAP_MAX = 0.80  # build fails if a catalogue variant is this close to a Q1–Q4 paraphrase


@dataclass
class CatalogItem:
    id: str
    title: str
    intent: str
    domain: str = ""
    variants: list[str] = field(default_factory=list)
    params: str = ""
    sources: str = ""
    calc: str = ""
    verdict: str = ""
    kpis: list[str] = field(default_factory=list)
    chart: str = ""
    table: str = ""
    actions: list[str] = field(default_factory=list)
    live: str = ""
    side: list[str] = field(default_factory=list)

    @property
    def phrases(self) -> list[str]:
        return [self.title, *self.variants]


def _field(block: str, name: str) -> str:
    m = re.search(rf"\*\*{name}:\*\*\s*(.+)", block)
    return m.group(1).strip() if m else ""


# Catalogue wordings changed because they collided with a golden (Q1–Q4) pattern — Q1–Q4 never change.
REWORDED = {
    "N17": (
        "Zal ta'miriga (remont) X mln sarflasam o'zini oqlaydimi?",
        "Zal ta'miriga (remont) X mln sarflasam qoplaydimi?",
    ),
    "N25": (
        "Chegirma aksiyasi (masalan, −20% hafta oxiri) o'zini oqlaydimi?",
        "Chegirma aksiyasi (masalan, −20% hafta oxiri) foyda beradimi?",
    ),
    "N45": (
        "Bayramlar (Yangi yil, Navro'z) uchun qancha ko'proq zaxira va xodim kerak?",
        "Bayramlar (Yangi yil, Navro'z) uchun qancha ko'proq zaxira va kunbay kerak?",
    ),
}


@lru_cache(maxsize=1)
def registry() -> dict[str, CatalogItem]:
    text = CATALOG_MD.read_text()
    out: dict[str, CatalogItem] = {}
    for m in re.finditer(r"^#### ([SN]\d{2}) · (.+?)\n(.*?)(?=^#### |^### |\Z)", text, re.M | re.S):
        cid, title, block = m.group(1), m.group(2).strip(), m.group(3)
        if cid in REWORDED and title == REWORDED[cid][0]:
            title = REWORDED[cid][1]
        im = re.search(r"\*\*Intent:\*\*\s*`([^`]+)`(?:\s*·\s*\*\*Soha:\*\*\s*(.+))?", block)
        variants = re.findall(r"«([^»]+)»", _field(block, "Variantlar"))
        rep = block.split("**Hisobot:**", 1)[1] if "**Hisobot:**" in block else ""
        acts = (
            re.findall(r"\d\)\s*([^→\n]+)", re.search(r"Nima qilish kerak:\s*(.+)", rep).group(1))
            if re.search(r"Nima qilish kerak:\s*(.+)", rep)
            else []
        )
        live = re.findall(r"«([^»]+)»", _field(block, "Live"))
        side = re.findall(r"«([^»]+)»", _field(block, "Side"))
        out[cid] = CatalogItem(
            cid,
            title,
            im.group(1) if im else cid.lower(),
            (im.group(2) or "").strip() if im else "",
            variants,
            _field(block, "Parametrlar"),
            _field(block, "Manba"),
            _field(block, "Hisoblash"),
            re.sub(
                r"^«|»$",
                "",
                (
                    re.search(r"Xulosa:\s*(.+)", rep).group(1).strip()
                    if re.search(r"Xulosa:\s*(.+)", rep)
                    else ""
                ),
            ),
            [
                k.strip()
                for k in (
                    re.search(r"KPI:\s*(.+)", rep).group(1).split("|")
                    if re.search(r"KPI:\s*(.+)", rep)
                    else []
                )
            ],
            (
                re.search(r"Grafik:\s*(.+)", rep).group(1).strip()
                if re.search(r"Grafik:\s*(.+)", rep)
                else ""
            ),
            (
                re.search(r"Jadval:\s*(.+)", rep).group(1).strip()
                if re.search(r"Jadval:\s*(.+)", rep)
                else ""
            ),
            [a.strip() for a in acts],
            live[0] if live else "",
            side,
        )
    return out


# --- similarity ----------------------------------------------------------------------------------
STOP = {
    "men",
    "menga",
    "bu",
    "va",
    "yoki",
    "qanday",
    "qancha",
    "nima",
    "bo'ladi",
    "bo'ladimi",
    "kerak",
    "mi",
    "bilan",
    "uchun",
    "biz",
    "bizda",
    "ham",
    "qaysi",
    "shu",
    "o'zi",
}


def _norm(t: str) -> str:
    return re.sub(r"[‘’ʻʼ`]", "'", t).lower()


def _stems(t: str) -> Counter[str]:
    words = [w for w in re.findall(r"[a-z'0-9]+", _norm(t)) if w not in STOP and len(w) > 1]
    return Counter(w[:5] for w in words)


def _tri(t: str) -> Counter[str]:
    s = f"  {re.sub(r'[^a-z0-9 ]', '', _norm(t))}  "
    return Counter(s[i : i + 3] for i in range(len(s) - 2))


def _cos(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    return dot / (
        math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    )


def similarity(a: str, b: str) -> float:
    return 0.6 * _cos(_stems(a), _stems(b)) + 0.4 * _cos(_tri(a), _tri(b))


# --- guards ---------------------------------------------------------------------------------------
GOLDEN_MARKERS = re.compile(
    r"yandex|uzum|agregator|o'z\s+dostavka|kuryer\s+.*agregator|ofitsi?ant\w*\s+olsam|yangi\s+ishchi\s+olsam|xodim\s+yollasam"
    r"|ap+arat|uskuna\w*\s+olsam|jihoz\w*\s+olsam|lavash\s+apparat|fritur|pech\s+olsam|daromad\w*\s+\d+\s*%|savdoni\s+oshirish\s+strategiya|revenue",
    re.I,
)
BAD_INTENT = re.compile(
    r"(biznes\w*|korxona\w*)\s+(ni\s+)?(qulat|uxlat|sindir)\w*(moqchi|aman|ib\s+qo'y)|sabotaj|sherik\w*\s+.*(yashir|aldab)|soliq\w*\s+.*(yashir|aldab|qochir)|pul\w*\s+yashir",
    re.I,
)


def is_bad_intent(text: str) -> bool:
    t = _norm(text)
    if re.search(
        r"\bnima\b.*qulat", t
    ):  # "biznesimni NIMA qulatishi mumkin?" — legitimate risk question (N60)
        return False
    return bool(BAD_INTENT.search(t))


# --- routing --------------------------------------------------------------------------------------
IMPLEMENTED: dict[str, Any] = {}  # intent -> compute function (filled by catalog_tools)


def best_match(text: str, only_implemented: bool = True) -> tuple[CatalogItem, float] | None:
    best: tuple[CatalogItem, float] | None = None
    for it in registry().values():
        if only_implemented and it.intent not in IMPLEMENTED:
            continue
        sc = max(similarity(text, p) for p in it.phrases)
        if best is None or sc > best[1]:
            best = (it, sc)
    return best


def route_catalog(text: str) -> tuple[CatalogItem, float] | None:
    """Tier 2. Never answers golden-marked questions (lexical guard)."""
    if GOLDEN_MARKERS.search(_norm(text)):
        return None
    b = best_match(text)
    return b if b and b[1] >= CATALOG_MIN else None
