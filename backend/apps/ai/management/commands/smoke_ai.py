"""`manage.py smoke_ai`: the only real-money smoke test (PLAN §0).

5 chat turns through the real chat pipeline (demo business, current AI profile) and one
Live session (~20 s, voice_spike question 3 with the tool). Every call is logged in
AiUsage; prints latency, the model that answered and the estimated cost.
"""

from __future__ import annotations

import asyncio
import json
import time
from decimal import Decimal
from typing import Any

from asgiref.sync import sync_to_async
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandParser

from apps.ai import budget
from apps.ai.chat import Turn, stream_turn
from apps.ai.models import Conversation
from apps.telemetry.models import AiUsage
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Business

QUESTIONS = [
    "25 mln jihoz olsam bo'ladimi?",
    "Eng qiyin kun qachon?",
    "Kredit to'lovi qachon va qancha?",
    "O'tgan oy qancha foyda qildim?",
    "Agro Go'shtga to'lov doim 15 kun kechikadi",
]


class Command(BaseCommand):
    help = "Real Gemini smoke test: 5 chat calls + 1 Live session (costs a few cents)"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--no-live", action="store_true")

    def handle(self, *args: Any, **opts: Any) -> None:
        b = Business.objects.filter(seed_tag="demo", name__startswith="Navro").first()
        if b is None:
            self.stderr.write("run seed_demo --reset first")
            return
        start = AiUsage.objects.order_by("-id").values_list("id", flat=True).first() or 0
        from apps.tenancy.models import Membership

        user_id = Membership.objects.filter(business=b).values_list("user_id", flat=True).first()
        self.stdout.write(f"profile={budget.profile()} chain={budget.chat_chain()}")
        for q in QUESTIONS:
            self.stdout.write(asyncio.run(self._turn(b, int(user_id or 0), q)))
        if not opts["no_live"]:
            call_command("voice_spike", only="3")
        rows = AiUsage.objects.filter(id__gt=start)
        cost = sum((r.cost_usd for r in rows), Decimal(0))
        today, total = budget.spent()
        self.stdout.write(
            self.style.SUCCESS(
                f"smoke cost ${cost:.4f} ({rows.count()} calls) · today ${today:.4f} · total ${total:.4f}"
            )
        )

    async def _turn(self, b: Business, user_id: int, text: str) -> str:
        def conv() -> Conversation:
            with tenant_context(b):
                c: Conversation = Conversation.objects.create(
                    business=b, user_id=user_id, channel="chat", title="smoke"
                )
                return c

        c = await sync_to_async(conv)()
        turn = Turn(business=b, user_id=user_id, author="smoke", conversation=c, text=text)
        t0 = time.perf_counter()
        blocks_ms = None
        answer, model = "", ""
        async for chunk in stream_turn(turn):
            for ev in chunk.decode().split("\n\n"):
                if not ev.strip():
                    continue
                name = next((ln[7:] for ln in ev.splitlines() if ln.startswith("event: ")), "")
                data = next((ln[6:] for ln in ev.splitlines() if ln.startswith("data: ")), "{}")
                if name == "blocks" and blocks_ms is None:
                    blocks_ms = (time.perf_counter() - t0) * 1000
                if name == "answer":
                    d = json.loads(data)
                    answer, model = str(d.get("headline") or ""), str(d.get("model") or "")
        total = (time.perf_counter() - t0) * 1000
        bm = f"{blocks_ms:.0f}" if blocks_ms is not None else "-"
        return f"  {text!r}: blocks {bm} ms, total {total:.0f} ms, model={model or '?'} :: {answer[:90]!r}"
