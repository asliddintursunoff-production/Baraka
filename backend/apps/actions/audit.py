"""AuditLog helper: who, when, which tool, which args (spec §5.10)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from apps.tenancy.context import require_business_id

from .models import AuditLog


def result_hash(result: Any) -> str:
    raw = json.dumps(result, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def audit(
    actor: str,
    event: str,
    *,
    tool: str = "",
    args: dict[str, Any] | None = None,
    result: Any = None,
) -> None:
    AuditLog.objects.create(
        business_id=require_business_id(),
        actor=actor,
        event=event,
        tool=tool,
        args=args or {},
        result_hash=result_hash(result) if result is not None else "",
    )
