"""Advisor playbooks (apps/knowledge/playbooks/*.md): general Uzbek strategies, no numbers.

Isolation: only playbooks whose `applies_to` contains this business's kind, or `general`,
are ever returned. Retrieval is keyword scoring for now (embeddings: PLAN §8).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from apps.tenancy.models import Business

DIR = Path(__file__).resolve().parent.parent / "knowledge" / "playbooks"
TOP_K = 4


@dataclass(frozen=True)
class Playbook:
    id: str
    title: str
    applies_to: tuple[str, ...]
    tags: str
    text: str


@lru_cache(maxsize=1)
def load_all() -> tuple[Playbook, ...]:
    out = []
    for f in sorted(DIR.glob("*.md")):
        raw = f.read_text(encoding="utf-8")
        m = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
        if not m:
            continue
        meta = dict(line.split(": ", 1) for line in m.group(1).splitlines() if ": " in line)
        kinds = tuple(
            k.strip()
            for k in meta.get("applies_to", "[general]").strip("[]").split(",")
            if k.strip()
        )
        out.append(
            Playbook(
                meta.get("id", f.stem),
                meta.get("title", ""),
                kinds,
                meta.get("tags", ""),
                m.group(2).strip(),
            )
        )
    return tuple(out)


def allowed_for(kind: str) -> list[Playbook]:
    """Own-kind + general only; never another kind's playbook."""
    return [p for p in load_all() if kind in p.applies_to or "general" in p.applies_to]


def retrieve(kind: str, question: str, k: int = TOP_K) -> list[Playbook]:
    words = set(re.findall(r"[a-z'ʻ]+", question.lower()))
    scored = [
        (sum(1 for w in words if len(w) > 3 and (w in p.tags or w in p.text.lower())), p)
        for p in allowed_for(kind)
    ]
    scored.sort(key=lambda x: -x[0])
    return [p for s, p in scored[:k] if s > 0] or [p for _, p in scored[:k]]


def playbook_text(business: Business, question: str) -> str:
    return "\n".join(f"- {p.title}: {p.text}" for p in retrieve(business.kind, question)) or "—"
