"""Read -> map -> ingest -> forecast, with progress events (SSE) and advisory locks.

Used by: first confirm (Connect), "Hozir yangilash" (Sources) and the scheduler (every
15 min). A source whose Drive modifiedTime did not change is skipped (no read, saves
quota). A changed header signature or a new sheet is re-mapped; it is applied
automatically only when every column is confident, otherwise a DataIssue asks the person.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from asgiref.sync import async_to_sync, sync_to_async
from django.db import connection, transaction
from django.utils import timezone

from apps.ai import uz_format as uz
from apps.insights.forecasting import invalidate, refresh_forecast
from apps.integrations import google
from apps.integrations.models import DataSource
from apps.tenancy.context import tenant_context, today_for
from apps.tenancy.models import Business

from .mapping import CONFIRM_BELOW, SheetProposal, is_report_title, propose_workbook
from .models import DataIssue, SheetMapping, SyncRun
from .pipeline import Ingestor, replace_seed_data
from .readers import WorkbookData, reader_for

log = logging.getLogger(__name__)
Progress = Callable[[str, int], None]
LOCK_BASE = 770_000_000

# proposals are kept briefly so "confirm" doesn't re-read the files
_proposals: dict[int, tuple[float, WorkbookData, list[SheetProposal]]] = {}
_plock = threading.Lock()


def propose_source(
    business: Business, source: DataSource
) -> tuple[WorkbookData, list[SheetProposal]]:
    with tenant_context(business):
        wb = reader_for(source, business).read(source)
    props = async_to_sync(propose_workbook)(wb)
    with _plock:
        _proposals[source.pk] = (time.time(), wb, props)
    return wb, props


def cached_proposals(source_id: int) -> tuple[WorkbookData, list[SheetProposal]] | None:
    with _plock:
        item = _proposals.get(source_id)
    if item and time.time() - item[0] < 900:
        return item[1], item[2]
    return None


@dataclass
class SyncSummary:
    sources: int = 0
    skipped: int = 0
    sheets: int = 0
    rows_added: int = 0
    rows_deleted: int = 0
    issues: int = 0
    errors: list[str] | None = None
    cash_found: bool = False


def _lock(source_id: int) -> bool:
    with connection.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", [LOCK_BASE + source_id])
        return bool(cur.fetchone()[0])


def _unlock(source_id: int) -> None:
    with connection.cursor() as cur:
        cur.execute("SELECT pg_advisory_unlock(%s)", [LOCK_BASE + source_id])


def save_mapping(
    business: Business,
    source: DataSource,
    p: SheetProposal,
    *,
    kind: str | None = None,
    columns: dict[str, str] | None = None,
    user_id: int | None = None,
) -> SheetMapping:
    col_map = columns if columns is not None else {str(c.index): c.field for c in p.columns}
    conf = {str(c.index): c.confidence for c in p.columns}
    m: SheetMapping
    m, _ = SheetMapping.objects.update_or_create(
        source=source,
        sheet_title=p.title,
        defaults={
            "business": business,
            "header_row": p.header_row,
            "header_signature": p.header_signature,
            "sheet_kind": kind or p.kind,
            "column_map": col_map,
            "confidence": conf,
            "confirmed_by_id": user_id,
            "confirmed_at": timezone.now() if user_id else None,
        },
    )
    return m


def purge_sheet(source: DataSource, title: str) -> None:
    """Rows once read from a tab that is now ignored are removed (no stale double counting)."""
    from apps.finance.models import Obligation, Transaction

    from .models import RawRow

    ids = list(
        RawRow.objects.filter(
            source=source, sheet_title=title, status=RawRow.Status.ACTIVE
        ).values_list("pk", flat=True)
    )
    if ids:
        Transaction.objects.filter(raw_row_id__in=ids).delete()
        Obligation.objects.filter(raw_row_id__in=ids).delete()
        RawRow.objects.filter(pk__in=ids).update(status=RawRow.Status.DELETED)


def safe_ingest(
    business: Business,
    source: DataSource,
    ing: Ingestor,
    sheet: Any,
    m: SheetMapping,
    summary: SyncSummary,
) -> None:
    """Each sheet in its own savepoint: a bad sheet becomes a DataIssue, the rest continue."""
    try:
        with transaction.atomic():
            ing.ingest(sheet, m)
    except Exception:
        log.exception("sheet %r of source %s failed; skipped", sheet.title, source.pk)
        ing.reload_counterparties()
        DataIssue.objects.get_or_create(
            kind="sheet_failed",
            status=DataIssue.Status.OPEN,
            message_uz=f"\"{sheet.title}\" varag'ini o'qib bo'lmadi, uni o'tkazib yubordim. Ustunlarini qayta ko'rib chiqing.",
            defaults={
                "business": business,
                "suggestion": {
                    "action": "remap",
                    "action_label": "Ustunlarni ko'rish",
                    "source_id": source.pk,
                    "sheet": sheet.title,
                },
            },
        )
        summary.issues += 1


def sync_source(
    business: Business,
    source: DataSource,
    *,
    trigger: str,
    force: bool,
    progress: Progress,
    summary: SyncSummary,
    first: bool = False,
) -> None:
    today = today_for(business)
    with tenant_context(business):
        if not _lock(source.pk):
            progress(f'"{source.title}" hozir boshqa jarayonda yangilanmoqda', 0)
            summary.skipped += 1
            return
        run = SyncRun.objects.create(business=business, source=source, trigger=trigger)
        try:
            reader = reader_for(source, business)
            modified = reader.modified_time(source)
            if not force and not first and modified and modified == source.modified_time:
                run.status, run.message = "skipped", "yangi qator yo'q"
                summary.skipped += 1
                return
            cached = cached_proposals(source.pk) if first else None
            wb = cached[0] if cached else reader.read(source)
            progress(f'"{wb.name or source.title}": {len(wb.sheets)} ta varaq o\'qildi…', 30)
            ing = Ingestor(business, source, today)
            ing.workbook_sheets = list(wb.sheets)
            mappings = {m.sheet_title: m for m in SheetMapping.objects.filter(source=source)}
            stale: list[str] = []
            for sheet in wb.sheets:
                m = mappings.get(sheet.title)
                from .mapping import heuristic_sheet

                hp = heuristic_sheet(sheet)
                if hp and hp.kind == "ignore" and hp.kind_confidence >= 0.95:
                    purge_sheet(source, sheet.title)  # report / accrual tab: never ingested
                    continue
                if hp and hp.kind.startswith("finmodel") and (m is None or m.sheet_kind != hp.kind):
                    m = save_mapping(business, source, hp)  # exact financial-model mapping
                if m is None or (
                    hp
                    and hp.header_signature
                    and m.header_signature
                    and hp.header_signature != m.header_signature
                ):
                    stale.append(sheet.title)
                    continue
                if m.sheet_kind == "ignore" or (
                    is_report_title(sheet.title) and not m.sheet_kind.startswith("finmodel")
                ):
                    purge_sheet(source, sheet.title)
                    continue
                safe_ingest(business, source, ing, sheet, m, summary)
            if stale:
                props = {
                    p.title: p
                    for p in async_to_sync(propose_workbook)(
                        WorkbookData(
                            wb.file_id,
                            wb.name,
                            wb.modified_time,
                            [s for s in wb.sheets if s.title in stale],
                        ),
                        use_llm=trigger != "schedule",  # the scheduler never calls an LLM
                    )
                }
                for sheet in [s for s in wb.sheets if s.title in stale]:
                    p = props.get(sheet.title)
                    if (
                        p
                        and p.kind != "ignore"
                        and all(c.confidence >= CONFIRM_BELOW for c in p.columns)
                    ):
                        safe_ingest(
                            business, source, ing, sheet, save_mapping(business, source, p), summary
                        )
                    elif p and p.kind != "ignore":
                        DataIssue.objects.get_or_create(
                            kind="remap_needed",
                            status=DataIssue.Status.OPEN,
                            message_uz=f"\"{sheet.title}\" varag'ining tuzilishi o'zgardi yoki yangi varaq qo'shildi. Ustunlarni bir marta tasdiqlang.",
                            defaults={
                                "business": business,
                                "suggestion": {
                                    "action": "remap",
                                    "action_label": "Ustunlarni ko'rish",
                                    "source_id": source.pk,
                                    "sheet": sheet.title,
                                },
                            },
                        )
            ing.finish()
            st = ing.stats
            summary.sheets += st.sheets
            summary.rows_added += st.rows_added
            summary.rows_deleted += st.rows_deleted
            summary.issues += st.issues
            summary.cash_found = summary.cash_found or st.cash_found
            progress(f"{uz.group_digits(st.data_rows)} qator o'qildi, {st.rows_added} ta yangi", 70)
            source.modified_time = modified or wb.modified_time
            source.last_synced_at = timezone.now()
            source.last_error = ""
            source.status = DataSource.Status.ACTIVE
            source.save(update_fields=["modified_time", "last_synced_at", "last_error", "status"])
            run.status = "ok"
            run.rows_added, run.rows_deleted = st.rows_added, st.rows_deleted
            run.message = (f"+{st.rows_added} qator" if st.rows_added else "yangi qator yo'q") + (
                f", {st.rows_deleted} ta o'chirildi" if st.rows_deleted else ""
            )
            summary.sources += 1
        except google.ReauthRequired:
            run.status, run.message = "error", "Google ruxsati kerak"
            summary.errors = [*(summary.errors or []), "Google hisobini qayta ulang."]
        except google.NoAccess:
            source.status, source.last_error = DataSource.Status.ERROR, "Faylga kirish yo'q"
            source.save(update_fields=["status", "last_error"])
            run.status, run.message = "error", "Faylga kirish yo'q"
            summary.errors = [*(summary.errors or []), f'"{source.title}" fayliga kirish yo\'q.']
        except Exception as exc:  # one bad source never stops the others
            log.exception("sync failed for source %s", source.pk)
            source.status, source.last_error = DataSource.Status.ERROR, str(exc)[:300]
            source.save(update_fields=["status", "last_error"])
            run.status, run.message = "error", "Xato: o'qib bo'lmadi"
            summary.errors = [
                *(summary.errors or []),
                f"\"{source.title}\" faylini o'qib bo'lmadi.",
            ]
        finally:
            run.finished_at = timezone.now()
            run.save()
            _unlock(source.pk)


def sync_business(
    business: Business,
    *,
    trigger: str,
    force: bool,
    progress: Progress,
    source_ids: list[int] | None = None,
    first: bool = False,
) -> SyncSummary:
    summary = SyncSummary()
    with tenant_context(business):
        qs = DataSource.objects.exclude(status=DataSource.Status.PAUSED).filter(confirmed=True)
        if source_ids:
            qs = qs.filter(pk__in=source_ids)
        sources = list(qs.order_by("id"))
        if first:
            replace_seed_data()
    if not sources:
        progress("Ulangan jadval yo'q", 100)
        return summary
    for i, s in enumerate(sources):
        progress(f'"{s.title}" tekshirilmoqda…', 10 + int(60 * i / len(sources)))
        sync_source(
            business,
            s,
            trigger=trigger,
            force=force,
            progress=progress,
            summary=summary,
            first=first,
        )
    if summary.rows_added or summary.rows_deleted or first or force:
        progress("Prognoz hisoblanmoqda…", 85)
        invalidate(business.pk)
        refresh_forecast(business)
        try:
            from apps.insights.alerts import evaluate_alerts

            evaluate_alerts(business)
        except ImportError:
            pass
    progress("Prognoz tayyor", 100)
    return summary


def sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()


async def stream_progress(work: Callable[[Progress], dict[str, Any]]) -> AsyncIterator[bytes]:
    """Run `work(progress)` in a thread and stream its progress as SSE."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()

    def progress(text: str, pct: int) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, ("progress", {"text": text, "pct": pct}))

    def guarded(progress: Progress) -> dict[str, Any]:
        from django.db import connections

        try:
            return work(progress)
        finally:
            connections.close_all()  # this worker thread's DB connection

    async def runner() -> None:
        try:
            result = await sync_to_async(guarded, thread_sensitive=False)(progress)
            await queue.put(("done", result))
        except Exception as exc:
            log.exception("sync stream failed")
            msg = (
                "Google hisobini qayta ulang."
                if isinstance(exc, google.ReauthRequired)
                else "Jadvalni o'qib bo'lmadi. Keyinroq qayta urinib ko'ring."
            )
            await queue.put(("error", {"message": msg}))

    task = asyncio.create_task(runner())
    while True:
        event, data = await queue.get()
        yield sse(event, data)
        if event in ("done", "error"):
            break
    await task
