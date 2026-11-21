"""AI spend guard: every billed call is logged in AiUsage; daily/total limits -> templates.

`check()` raises BudgetExceeded (a subclass of AllModelsFailed, so chat falls back to its
template answer). Live is refused with "Bugungi ovoz limiti tugadi".
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from apps.telemetry.models import AiUsage
from config import app_settings as cfg

from .llm import AllModelsFailed

log = logging.getLogger(__name__)
M = Decimal(1_000_000)


class BudgetExceeded(AllModelsFailed):
    pass


def profile() -> str:
    return "dev" if settings.DEBUG else "demo"


def chat_chain() -> tuple[str, ...]:
    return cfg.AI_PROFILES[profile()]


def token_cost(model: str, inp: int, out: int) -> Decimal:
    pin, pout = cfg.AI_PRICES_PER_M_TOKENS.get(model, cfg.AI_DEFAULT_PRICE_PER_M)
    return (pin * inp + pout * out) / M


def _usage_tokens(usage: Any) -> tuple[int, int]:
    if usage is None:
        return 0, 0
    inp = int(getattr(usage, "prompt_token_count", 0) or 0)
    out = int(getattr(usage, "candidates_token_count", 0) or 0) + int(
        getattr(usage, "thoughts_token_count", 0) or 0
    )
    return inp, out


def record(
    kind: str, model: str, *, usage: Any = None, seconds: int = 0, business_id: int | None = None
) -> AiUsage:
    inp, out = _usage_tokens(usage)
    cost = token_cost(model, inp, out) if not seconds else cfg.AI_LIVE_USD_PER_MIN * seconds / 60
    return AiUsage.objects.create(
        business_id=business_id,
        kind=kind,
        model=model,
        input_tokens=inp,
        output_tokens=out,
        seconds=seconds,
        cost_usd=cost.quantize(Decimal("0.000001")),
    )


def spent() -> tuple[Decimal, Decimal]:
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    total = AiUsage.objects.aggregate(s=Sum("cost_usd"))["s"] or Decimal(0)
    today = AiUsage.objects.filter(created_at__gte=start).aggregate(s=Sum("cost_usd"))[
        "s"
    ] or Decimal(0)
    return today, total


def over_limit() -> str | None:
    if not cfg.AI_BUDGET_ENFORCED:  # owner turned the limits off (2026-11-22); usage still logged
        return None
    today, total = spent()
    if total >= cfg.AI_TOTAL_BUDGET_USD:
        return "total"
    if today >= cfg.AI_DAILY_BUDGET_USD:
        return "daily"
    return None


def check(kind: str) -> None:
    reason = over_limit()
    if reason:
        log.warning("AI budget %s limit reached; %s call refused", reason, kind)
        raise BudgetExceeded(f"budget:{reason}")


def generate_sync(
    kind: str, *, model: str, contents: Any, config: Any = None, business_id: int | None = None
) -> Any:
    """Budget-checked, usage-logged `client().models.generate_content` (TTS, STT, light)."""
    from .gemini import client

    check(kind)
    r = client().models.generate_content(model=model, contents=contents, config=config)
    record(kind, model, usage=getattr(r, "usage_metadata", None), business_id=business_id)
    return r
