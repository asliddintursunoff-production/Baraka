"""Sources API (docs/API_SOURCES.md): pick -> proposals -> confirm (SSE) -> sync (SSE)."""

from __future__ import annotations

import json
import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponseBase, JsonResponse, StreamingHttpResponse
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.response import Response

from apps.actions.audit import audit
from apps.ai import uz_format as uz
from apps.finance.models import CashAccount
from apps.insights.forecasting import invalidate, refresh_forecast
from apps.integrations import google
from apps.integrations.models import DataSource, GoogleCredential
from apps.tenancy.api import BusinessAPIView
from apps.tenancy.context import tenant_context, today_for
from config import app_settings as cfg

from .mapping import FIELD_LABELS, FIELDS, KIND_LABELS, KINDS, SheetProposal
from .models import DataIssue, RawRow, SheetMapping, SyncRun
from .pipeline import Ingestor
from .sync import cached_proposals, propose_source, save_mapping, stream_progress, sync_business

log = logging.getLogger(__name__)


def _log_tone(run: SyncRun) -> str:
    if run.status == "error":
        return "error"
    return "success" if run.rows_added or run.rows_deleted else "muted"


def _when(dt: Any, today: date) -> str:
    local = timezone.localtime(dt)
    d = local.date()
    day = "Bugun" if d == today else "Kecha" if (today - d).days == 1 else uz.format_date(d)
    return f"{day} {local:%H:%M}"


def proposals_payload(
    items: list[tuple[DataSource, list[SheetProposal]]], *, needs_cash: bool
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    return {
        "sources": [
            {
                "id": s.pk,
                "title": s.title,
                "kind": s.kind,
                "summary": f"{len(props)} varaq: "
                + " · ".join(p.title for p in props[:5])
                + (" …" if len(props) > 5 else ""),
                "sheets": [p.payload() for p in props],
            }
            for s, props in items
        ],
        "field_options": [{"value": f, "label": FIELD_LABELS[f]} for f in FIELDS],
        "kind_options": [{"value": k, "label": KIND_LABELS[k]} for k in KINDS],
        "issues_preview": issues,
        "needs_opening_balance": needs_cash,
        "opening_balance_hint": None,
    }


def _needs_cash(items: list[tuple[DataSource, list[SheetProposal]]]) -> bool:
    has_sheet = any(p.kind == "cash_balance" for _, props in items for p in props)
    return not has_sheet and not CashAccount.objects.exists()


class SourcesView(BusinessAPIView):
    def post(self, request: Request) -> Response:
        data = request.data if isinstance(request.data, dict) else {}
        ids = [str(x)[:128] for x in (data.get("file_ids") or []) if x][:20]
        if not ids:
            return Response(
                {"error": "no_files", "message": "Kamida bitta jadval tanlang."}, status=400
            )
        b = self.business
        items: list[tuple[DataSource, list[SheetProposal]]] = []
        for fid in ids:
            try:
                meta = google.file_meta(b, fid)
            except google.ReauthRequired:
                return Response(
                    {"error": "reauth_required", "message": "Google hisobini qayta ulang."},
                    status=409,
                )
            except google.NoAccess:
                return Response(
                    {
                        "error": "no_access",
                        "message": "Bu faylni ochib bo'lmadi. Uni Picker orqali qayta tanlang.",
                    },
                    status=400,
                )
            mime = str(meta.get("mimeType", ""))
            if mime not in (cfg.SHEETS_MIME, cfg.XLSX_MIME):
                return Response(
                    {
                        "error": "bad_type",
                        "message": f'"{meta.get("name")}" jadval emas. Google Sheets yoki .xlsx tanlang.',
                    },
                    status=400,
                )
            src, _ = DataSource.objects.update_or_create(
                spreadsheet_id=fid,
                defaults={
                    "business": b,
                    "title": str(meta.get("name", ""))[:200],
                    "kind": DataSource.Kind.XLSX
                    if mime == cfg.XLSX_MIME
                    else DataSource.Kind.GOOGLE_SHEET,
                    "status": DataSource.Status.ACTIVE,
                },
            )
            try:
                _, props = propose_source(b, src)
            except google.NoAccess:
                return Response(
                    {"error": "no_access", "message": "Faylni o'qib bo'lmadi."}, status=400
                )
            items.append((src, props))
        audit(f"user:{request.user.pk}", "sources_added", args={"file_ids": ids})
        return Response(proposals_payload(items, needs_cash=_needs_cash(items)))

    def get(self, request: Request) -> Response:
        b = self.business
        today = today_for(b)
        cred = GoogleCredential.objects.first()
        sources = list(DataSource.objects.filter(confirmed=True).order_by("id"))
        mappings = (
            SheetMapping.objects.filter(source__in=sources)
            .exclude(sheet_kind="ignore")
            .order_by("source_id", "id")
        )
        counts = {
            (r["source_id"], r["sheet_title"]): r["n"]
            for r in RawRow.objects.filter(status="active")
            .values("source_id", "sheet_title")
            .annotate(n=Count("id"))
        }
        last_runs: dict[int, SyncRun] = {}
        for run in SyncRun.objects.filter(status__in=["ok", "error"]).order_by("-started_at")[:50]:
            last_runs.setdefault(run.source_id, run)
        files = []
        for m in mappings:
            src = next(s for s in sources if s.pk == m.source_id)
            run = last_runs.get(src.pk)
            added = 0
            if (
                run
                and run.status == "ok"
                and run.rows_added
                and (timezone.now() - run.started_at).days < 1
            ):
                added = run.rows_added
            err = src.status in (DataSource.Status.ERROR, DataSource.Status.REAUTH)
            files.append(
                {
                    "source_id": src.pk,
                    "label": f"{src.title} › {m.sheet_title}",
                    "kind_label": KIND_LABELS.get(m.sheet_kind, m.sheet_kind),
                    "rows": uz.group_digits(counts.get((src.pk, m.sheet_title), 0)),
                    "state": "Xato"
                    if err
                    else (f"Yangi · +{added}" if added else "O'zgarish yo'q"),
                    "state_tone": "error" if err else ("new" if added else "same"),
                }
            )
        last_sync = max((s.last_synced_at for s in sources if s.last_synced_at), default=None)
        errors = [s for s in sources if s.status != DataSource.Status.ACTIVE]
        needs_reauth = any(s.status == DataSource.Status.REAUTH for s in sources)
        sub = [
            f"Oxirgi tekshiruv: {_when(last_sync, today).lower() if last_sync else 'hali yo‘q'}",
            f"har {cfg.SYNC_INTERVAL_MIN} daqiqada tekshiriladi",
        ]
        if cred and cred.email:
            sub.append(cred.email)
        issues = DataIssue.objects.filter(status=DataIssue.Status.OPEN).order_by("-created_at")[:30]
        runs = SyncRun.objects.exclude(status="running").order_by("-started_at")[:12]
        return Response(
            {
                "connected": cred is not None,
                "email": cred.email if cred else None,
                "needs_reauth": needs_reauth,
                "status": {
                    "ok": not errors,
                    "title": "Hammasi ishlayapti"
                    if not errors
                    else (
                        "Google hisobini qayta ulang"
                        if needs_reauth
                        else "Ba'zi fayllarda xato bor"
                    ),
                    "subtitle": " · ".join(sub),
                },
                "files": files,
                "issues": [
                    {
                        "id": i.pk,
                        "message": i.message_uz,
                        "action": (i.suggestion or {}).get("action", "ignore"),
                        "action_label": (i.suggestion or {}).get(
                            "action_label", "E'tiborsiz qoldirish"
                        ),
                    }
                    for i in issues
                ],
                "log": [
                    {
                        "when": _when(r.started_at, today),
                        "text": r.message
                        + (" · prognoz yangilandi" if r.rows_added or r.rows_deleted else ""),
                        "tone": _log_tone(r),
                    }
                    for r in runs
                ],
            }
        )


class RemapView(BusinessAPIView):
    def post(self, request: Request, source_id: int) -> Response:
        src = DataSource.objects.filter(pk=source_id).first()
        if src is None:
            return Response({"error": "not_found"}, status=404)
        try:
            _, props = propose_source(self.business, src)
        except google.ReauthRequired:
            return Response(
                {"error": "reauth_required", "message": "Google hisobini qayta ulang."}, status=409
            )
        existing = {m.sheet_title: m for m in SheetMapping.objects.filter(source=src)}
        for p in props:  # show what is confirmed now
            m = existing.get(p.title)
            if m:
                p.kind = m.sheet_kind
                for c in p.columns:
                    if str(c.index) in m.column_map:
                        c.field, c.confidence = m.column_map[str(c.index)], max(c.confidence, 0.95)
        return Response(proposals_payload([(src, props)], needs_cash=False))


def _business_or_401(request: HttpRequest) -> Any:
    if not request.user.is_authenticated or getattr(request, "business", None) is None:
        return None
    return getattr(request, "business", None)


def confirm(request: HttpRequest) -> HttpResponseBase:
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    business = _business_or_401(request)
    if business is None:
        return JsonResponse({"error": "auth_required"}, status=401)
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"error": "bad_json"}, status=400)
    mappings = body.get("mappings") or []
    opening = body.get("opening_balance") or None
    auto_sync = bool(body.get("auto_sync", True))
    user_id = request.user.pk

    def work(progress: Any) -> dict[str, Any]:
        with tenant_context(business):
            source_ids: list[int] = []
            first = not DataSource.objects.filter(confirmed=True).exists()
            for m in mappings:
                src = DataSource.objects.filter(pk=int(m.get("source_id", 0))).first()
                if src is None:
                    continue
                cached = cached_proposals(src.pk)
                props = {
                    p.title: p for p in (cached[1] if cached else propose_source(business, src)[1])
                }
                p = props.get(str(m.get("sheet")))
                if p is None:
                    continue
                kind = m.get("kind") if m.get("kind") in KINDS else p.kind
                cols = {str(k): v for k, v in (m.get("columns") or {}).items() if v in FIELDS}
                save_mapping(business, src, p, kind=kind, columns=cols or None, user_id=user_id)
                if src.pk not in source_ids:
                    source_ids.append(src.pk)
            DataSource.objects.filter(pk__in=source_ids).update(confirmed=True, auto_sync=auto_sync)
            progress("Ustunlar saqlandi", 10)
        summary = sync_business(
            business,
            trigger="confirm",
            force=True,
            progress=progress,
            source_ids=source_ids,
            first=first,
        )
        with tenant_context(business):
            if opening and not summary.cash_found:
                try:
                    amount = Decimal(str(opening.get("amount", "")).replace(" ", ""))
                    as_of = date.fromisoformat(str(opening.get("date")))
                except (InvalidOperation, ValueError):
                    amount, as_of = None, None
                if amount is not None and as_of is not None:
                    CashAccount.objects.all().delete()
                    CashAccount.objects.create(
                        business=business, opening_balance=amount, as_of_date=as_of
                    )
                    invalidate(business.pk)
                    refresh_forecast(business)
            audit(f"user:{user_id}", "sources_confirmed", args={"source_ids": source_ids})
        return {
            "text": "Prognoz tayyor",
            "redirect": "/",
            "rows_added": summary.rows_added,
            "issues": summary.issues,
        }

    resp = StreamingHttpResponse(
        stream_progress(work), content_type="text/event-stream; charset=utf-8"
    )
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp


def sync_now(request: HttpRequest) -> HttpResponseBase:
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    business = _business_or_401(request)
    if business is None:
        return JsonResponse({"error": "auth_required"}, status=401)
    user_id = request.user.pk

    def work(progress: Any) -> dict[str, Any]:
        summary = sync_business(business, trigger="manual", force=True, progress=progress)
        with tenant_context(business):
            audit(f"user:{user_id}", "sync_now", args={"rows_added": summary.rows_added})
        text = (
            f"+{summary.rows_added} qator · prognoz yangilandi"
            if summary.rows_added
            else "Yangi qator yo'q"
        )
        if summary.errors:
            text = summary.errors[0]
        return {"text": text, "rows_added": summary.rows_added, "issues": summary.issues}

    resp = StreamingHttpResponse(
        stream_progress(work), content_type="text/event-stream; charset=utf-8"
    )
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp


class IssueResolveView(BusinessAPIView):
    def post(self, request: Request, issue_id: int) -> Response:
        issue = (
            DataIssue.objects.filter(pk=issue_id, status=DataIssue.Status.OPEN)
            .select_related("raw_row")
            .first()
        )
        if issue is None:
            return Response({"error": "not_found"}, status=404)
        data = request.data if isinstance(request.data, dict) else {}
        action = data.get("action", "ignore")
        sug = issue.suggestion or {}
        if action in ("use_suggestion", "set_amount") and issue.raw_row is not None:
            overrides: dict[str, Any] = {}
            if action == "use_suggestion" and sug.get("value"):
                overrides["date"] = date.fromisoformat(sug["value"])
            if action == "set_amount":
                try:
                    overrides["amount"] = Decimal(str(data.get("value", "")).replace(" ", ""))
                except InvalidOperation:
                    return Response(
                        {"error": "bad_amount", "message": "Summani raqam bilan yozing."},
                        status=400,
                    )
            m = SheetMapping.objects.filter(
                source_id=issue.raw_row.source_id, sheet_title=issue.raw_row.sheet_title
            ).first()
            if m is None:
                return Response({"error": "no_mapping"}, status=400)
            ing = Ingestor(self.business, issue.raw_row.source, today_for(self.business))
            try:
                facts = ing.build(
                    m.sheet_kind,
                    m.sheet_title,
                    issue.raw_row.row_index,
                    list(issue.raw_row.values),
                    Ingestor.cols(m),
                    overrides,
                )
            except Exception as exc:
                return Response({"error": "still_invalid", "message": str(exc)[:200]}, status=400)
            for f in facts:
                f.raw_row = issue.raw_row
                f.save()
            invalidate(self.business.pk)
            refresh_forecast(self.business)
        issue.status = DataIssue.Status.RESOLVED if action != "ignore" else DataIssue.Status.IGNORED
        issue.save(update_fields=["status"])
        audit(
            f"user:{request.user.pk}",
            "issue_resolved",
            args={"issue_id": issue.pk, "action": action},
        )
        return Response({"ok": True})


__all__ = ["Q"]
