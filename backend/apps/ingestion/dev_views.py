"""DEBUG-only: connect the demo export through a FakeReader, so the Connect -> confirm ->
dashboard flow and "Hozir yangilash" can be tested end to end without Google.

POST /api/dev/sources/demo              -> {"source_id"}; then open
                                           /onboarding/connect?step=map&source=<id>
POST /api/dev/sources/demo/add-expense  -> appends a "remont" expense row dated today
                                           (like the owner typing it into the sheet)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.finance.demo import build_navroz
from apps.finance.demo_export import export_xlsx
from apps.integrations.models import DataSource
from apps.tenancy.context import tenant_context, today_for
from apps.tenancy.models import Business

from .readers import FakeReader, WorkbookData, set_reader_override, xlsx_sheets

FILE_ID = "dev-demo-navroz"
_book: dict[str, WorkbookData] = {}


def _business(request: HttpRequest) -> Business:
    if not settings.DEBUG:
        raise Http404
    b = getattr(request, "business", None)
    if not request.user.is_authenticated or not isinstance(b, Business):
        raise Http404
    return b


@require_POST
def connect_demo(request: HttpRequest) -> JsonResponse:
    b = _business(request)
    with tempfile.TemporaryDirectory() as tmp:
        path = export_xlsx(build_navroz(today_for(b)), Path(tmp) / "demo_navroz.xlsx")
        sheets = xlsx_sheets(path.read_bytes())
    _book[FILE_ID] = WorkbookData(FILE_ID, "demo_navroz", timezone.now().isoformat(), sheets)
    set_reader_override(FakeReader(_book))
    with tenant_context(b):
        src, _ = DataSource.objects.update_or_create(
            spreadsheet_id=FILE_ID,
            defaults={
                "business": b,
                "title": "demo_navroz",
                "kind": DataSource.Kind.XLSX,
                "status": DataSource.Status.ACTIVE,
            },
        )
    return JsonResponse({"source_id": src.pk})


@require_POST
def add_expense(request: HttpRequest) -> JsonResponse:
    b = _business(request)
    wb = _book.get(FILE_ID)
    if wb is None:
        return JsonResponse({"error": "connect first"}, status=400)
    body = json.loads(request.body or b"{}")
    amount = str(body.get("amount") or "3 000 000")
    chiqim = next(s for s in wb.sheets if s.title == "Chiqim")
    chiqim.rows.append(
        [
            today_for(b).strftime("%d.%m.%Y"),
            amount,
            "remont",
            "Usta Akmal",
            None,
            "Naqd",
            "to'landi",
        ]
    )
    wb.modified_time = timezone.now().isoformat()
    return JsonResponse({"ok": True, "rows": len(chiqim.rows)})
