"""DEMO_GOLDEN_ONLY: the app answers only Q1–Q4 (+ their side questions) — zero LLM calls.

One deterministic entry point for chat and Live: `answer(ctx, text, prev)` returns the full answer
(markdown, report blocks, chips/cards, speech text + its clip key). Golden base answers come from
the pinned (frozen) bundles; side answers from the pinned side list; parameter changes from the
golden tool (deterministic template with an "Oldin → Yangi" table); everything else gets the fixed
reply with the 4 golden question cards.
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .golden_tools import INTENTS, match
from .tools import ToolContext, run_tool

ROOT = Path(__file__).resolve().parents[3]

# The 4 cards (exact texts; each routes to its frozen base answer — tested).
QUESTIONS = {
    "channel_economics": "Yandex va Uzum menga foydalimi yoki o'z dostavkamni kuchaytiraymi?",
    "hire_payback": "Yana bitta ofitsiant olsam, u o'zini necha oyda oqlaydi?",
    "equipment_investment": (
        "25 millionga lavash apparat olmoqchiman — investitsiyami yoki zarariga ishlaydimi?"
    ),
    "revenue_growth_plan": (
        "Korxona daromadini 10 foizga qisqa muddatda oshirish uchun strategiya tuzib ber."
    ),
}
MD_FILE = {i.id: ROOT / i.spec for i in INTENTS}

OTHER_TEXT = "Hozir men 4 ta asosiy tahlil bo'yicha javob beraman:"
OTHER_SAY = (
    "Hozir men to'rtta asosiy tahlil bo'yicha javob beraman: agregatorlar yoki o'z dostavka, "
    "yangi ofitsiant olish, lavash apparati olish va daromadni o'n foizga oshirish. "
    "Ekrandan birini tanlang yoki savolingizni ayting."
)
GREET_TEXT = "Assalomu alaykum!"
GREET_SAY = "Assalomu alaykum! " + OTHER_SAY
CHARTS_SAY = "Mana, grafik va jadvallar ekranda."
EXPLAIN_SAY = "Hisoblash usuli ekranda."
DECLINE_TEXT = "Mayli, rejani tasdiqlamadim. Boshqa savolingiz bo'lsa, bemalol so'rang."
AMBIG_TEXT = "Qaysi birini nazarda tutdingiz?"

# speech-to-text typos and spoken forms -> the words the golden patterns know
_FIX = [
    (r"\bofitsant", "ofitsiant"),
    (r"\bofitsiyant", "ofitsiant"),
    (r"\bofisiant", "ofitsiant"),
    (r"\baparat", "apparat"),
    (r"\bapparad", "apparat"),
    (r"\byandeks", "yandex"),
    (r"\bdastavka", "dostavka"),
    (r"\bdostafka", "dostavka"),
    (r"\bagrigator", "agregator"),
    (r"\bagregattor", "agregator"),
    (r"\bstrategi\b", "strategiya"),
    (r"\bfoiz(ga)?\b", r"foiz\1"),
]
_GREET = re.compile(
    r"^\W*(salom|assalomu?\s*alaykum|assalom|qalaysiz|qanaysan|qalaysan|yaxshimisiz|hello|hi|privet|"
    r"rahmat|katta\s+rahmat|xayr|ishlar\s+qalay)\W*(\w+\W*){0,2}$",
    re.I,
)
_CHARTS = re.compile(
    r"diagramm|grafik|statistik|jadval|ko'rsat|batafsil|chart|vizual|rasm\w*\s+bormi", re.I
)
_EXPLAIN = re.compile(
    r"\bnega\b|nima\s+uchun|qanday\s+(hisob|chiqdi|chiqar)|qayerdan|formula|tushuntir", re.I
)
_DECLINE = re.compile(
    r"^\W*(yo'q|yoq|kerak\s+emas|kerakmas|shart\s+emas|hozircha\s+yo'q)\W*$", re.I
)


def normalize(text: str) -> str:
    t = re.sub(r"[‘’ʻʼ`´]", "'", text or "").lower().strip()
    for a, b in _FIX:
        t = re.sub(a, b, t)
    return t


def speech_key(text: str) -> str:
    return hashlib.sha256(text.strip().encode()).hexdigest()[:16]


@lru_cache(maxsize=1)
def clip_manifest() -> dict[str, str]:
    """key -> text of every pre-recorded clip (frontend/public/golden/<key>.wav)."""
    f = Path(__file__).parent / "data" / "golden" / "clips.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _recipe(intent: str) -> str:
    """md section 2 (the calculation recipe), verbatim."""
    md = MD_FILE[intent].read_text()
    m = re.search(r"^## 2\..*?$(.*?)^---\s*$", md, re.S | re.M)
    body = (m.group(1) if m else "").strip()
    return "### Qanday hisobladim\n\n" + body


# extra spoken forms (routing only; the frozen golden tools are unchanged)
_EXTRA = {
    "hire_payback": re.compile(
        r"(ishchi|xodim|ofitsiant|oshpaz|lavash\s+usta|kassir|kuryer|odam)\w*\s+"
        r"(ol(moqchi|ay|ib|ish|sak|amiz)|kerak|qo'sh|yolla)",
        re.I,
    ),
    "equipment_investment": re.compile(
        r"(apparat|stansiya|jihoz|uskuna)\w*\s+(ol(moqchi|ay|ib|ish|sak)|sotib|kerak)", re.I
    ),
    "revenue_growth_plan": re.compile(
        r"(daromad|tushum|savdo|sotuv|foyda)\w*\s+(\w+\s+){0,3}(oshir|ko'paytir|o'stir)", re.I
    ),
}


def _matches(t: str) -> list[str]:
    hits = [i.id for i in INTENTS if i.pattern.search(t)]
    return hits or [k for k, rx in _EXTRA.items() if rx.search(t)]


def _run(ctx: ToolContext, intent: str, params: dict[str, Any]) -> dict[str, Any]:
    return run_tool(ctx, intent, params)


def _speech(result: dict[str, Any]) -> str:
    segs = result.get("speech_segments") or []
    if segs:
        return " ".join(str(s["text"]).strip() for s in segs if s.get("text"))
    return str(result.get("say") or re.sub(r"\*\*", "", str(result.get("md") or ""))).strip()


def _out(
    kind: str,
    *,
    intent: str | None = None,
    markdown: str = "",
    blocks: list[dict[str, Any]] | None = None,
    say: str = "",
    segments: list[dict[str, Any]] | None = None,
    cards: list[dict[str, str]] | None = None,
    chips: list[str] | None = None,
    result: dict[str, Any] | None = None,
    expand: bool = False,
) -> dict[str, Any]:
    key = speech_key(say) if say else ""
    return {
        "kind": kind,
        "intent": intent,
        "markdown": markdown,
        "blocks": blocks or [],
        "say": say,
        "segments": segments or [],
        "cards": cards or [],
        "chips": chips or [],
        "clip": key if key in clip_manifest() else "",
        "speech_key": key,
        "expand": expand,
        "result": result,
    }


def question_cards(ids: list[str] | None = None) -> list[dict[str, str]]:
    return [{"intent": k, "text": v} for k, v in QUESTIONS.items() if ids is None or k in ids]


def fixed_reply(greeting: bool = False) -> dict[str, Any]:
    text = f"{GREET_TEXT} {OTHER_TEXT}" if greeting else OTHER_TEXT
    return _out(
        "greeting" if greeting else "other",
        markdown=text,
        say=GREET_SAY if greeting else OTHER_SAY,
        cards=question_cards(),
    )


def answer(ctx: ToolContext, text: str, prev: str | None = None) -> dict[str, Any]:
    """The whole demo router. `prev` = the active golden intent of this conversation."""
    t = normalize(text)
    hits = _matches(t)
    # 1. an explicit golden question (any paraphrase)
    if len(hits) > 1 and prev not in hits:
        # two goldens fit equally: ask, with both cards (never the fixed "other" reply)
        return _out(
            "ambiguous", markdown=AMBIG_TEXT, say=AMBIG_TEXT, cards=question_cards(hits[:2])
        )
    m = match(t, prev)
    if m is None and len(hits) == 1:  # an extra spoken form: same golden, its own params
        it = next(i for i in INTENTS if i.id == hits[0])
        m = (it, it.params(t))
    if m is not None and (hits or not prev or m[0].id == prev):
        intent, params = m[0].id, m[1]
        ctx.last_user_text = t
        r = _run(ctx, intent, params)
        blocks = list(r.get("ui_blocks") or [])
        pinned = bool(r.get("pinned"))
        side = bool(r.get("pinned_side"))
        md = "" if (pinned and blocks) else str(r.get("md") or "")
        md = re.sub(r"(?im)^\W*chips\W*:.*$\n?", "", md).strip()
        return _out(
            "golden" if pinned else ("side" if side else "param"),
            intent=intent,
            markdown=md,
            blocks=blocks,
            say=_speech(r),
            segments=list(r.get("speech_segments") or []),
            result=r,
        )
    # 2. follow-ups about the active golden
    if prev:
        ctx.last_user_text = t
        base = _run(ctx, prev, {})
        from .golden_tools import _pinned

        # a pinned side answer (md section 7.1) for this text?
        d = _pinned().get(prev) or {}
        for sd in d.get("side") or []:
            if re.search(sd["match"], t):
                md = str(sd["answer"])
                return _out(
                    "side",
                    intent=prev,
                    markdown=md,
                    say=str(sd.get("say") or re.sub(r"\*\*", "", md)),
                )
        if _CHARTS.search(t):
            return _out(
                "charts",
                intent=prev,
                markdown=CHARTS_SAY,
                blocks=list(base.get("ui_blocks") or []),
                say=CHARTS_SAY,
                expand=True,
            )
        if _EXPLAIN.search(t):
            return _out(
                "explain",
                intent=prev,
                markdown=_recipe(prev),
                blocks=list(base.get("ui_blocks") or []),
                say=EXPLAIN_SAY,
            )
        if _DECLINE.search(t):
            return _out("decline", intent=prev, markdown=DECLINE_TEXT, say=DECLINE_TEXT)
    # 3. greetings / anything else: the fixed reply with the 4 question cards (no LLM)
    return fixed_reply(greeting=bool(_GREET.match(t)))


# --- spoken form for the clips (screen text stays verbatim) -----------------------------------
def _w(n: int) -> str:
    from .uz_format import uz_number_words

    return uz_number_words(n)


def _num_words(s: str) -> str:
    """ "4,32" -> "to'rt butun o'ttiz ikki"; "430 000" -> "to'rt yuz o'ttiz ming"."""
    s = s.replace("\xa0", " ").replace(" ", "")
    if "," in s:
        a, b = s.split(",", 1)
        return f"{_w(int(a or 0))} butun {_w(int(b))}" if b.strip("0") else _w(int(a or 0))
    return _w(int(s))


def _mln(m: re.Match[str]) -> str:
    v = float(m.group(2).replace(",", "."))
    return _w(int(round(v * 1_000_000, -3)))


def _ord(n: int) -> str:
    from .uz_format import uz_ordinal_words

    return uz_ordinal_words(n)


def _sign(s: str) -> str:
    return "minus " if s in ("−", "-") else ("qo'shimcha " if s == "+" else "")


def speakable(text: str) -> str:
    """Markdown/digit answer -> Uzbek words a TTS voice reads cleanly (no symbols, no digits)."""
    t = re.sub(r"\*\*|__|`|#", "", text)
    t = re.sub(r"\s*\(Q\d+\)", "", t)
    t = re.sub(r"so'm/kVt·soat", "so'm har kilovatt soatiga", t)
    t = t.replace("kVt·soat", "kilovatt soat")
    t = re.sub(r"(?i)\bdu\s*[–-]\s*pa\b", "dushanbadan payshanbagacha", t)
    t = re.sub(
        r"(\d{1,2}):00\s*[–-]\s*(\d{1,2}):00",
        lambda m: f"soat {_w(int(m.group(1)))}dan {_w(int(m.group(2)))}gacha",
        t,
    )
    t = re.sub(
        r"(\d+)-(?=[a-zA-Z'])", lambda m: f"{_ord(int(m.group(1)))} ", t
    )  # 2-kuryer, 31-oktyabr
    t = re.sub(r"\b(20\d\d)\b", lambda m: f"{_ord(int(m.group(1)))} yil", t)
    t = re.sub(r"([+−-]?)(\d+(?:,\d+)?)\s*mln", lambda m: _sign(m.group(1)) + _mln(m), t)
    t = re.sub(
        r"([+−-]?)(\d+(?:,\d+)?)\s*%",
        lambda m: _sign(m.group(1)) + _num_words(m.group(2)) + " foiz",
        t,
    )
    t = re.sub(
        r"([+−-]?)(\d{1,3}(?:[ \xa0]\d{3})+|\d+(?:,\d+)?)",
        lambda m: _sign(m.group(1)) + _num_words(m.group(2)),
        t,
    )
    t = t.replace("/oy", " oyiga").replace("/kun", " kuniga").replace("/yil", " yiliga")
    t = re.sub(r"\s[+]\s", " va ", t)
    t = re.sub(r"\s[−-]\s", " minus ", t)
    t = re.sub(r"\bvs\b", "va", t)
    t = re.sub(r"(?<=\w)/(?=\w)", " va ", t)
    t = (
        t.replace(" = ", " — ")
        .replace("→", ", ")
        .replace("~", "taxminan ")
        .replace("×", " ko'paytirilgan ")
    )
    t = (
        t.replace("·", ", ")
        .replace("≥", "kamida ")
        .replace("≤", "ko'pi bilan ")
        .replace("–", " — ")
    )
    t = re.sub(r"(\S) (da|ga|dan|gacha|ni|ning)\b", r"\1\2", t)
    t = re.sub(r"\s+([,.;:])", r"\1", t)
    return re.sub(r"\s{2,}", " ", t).strip()
