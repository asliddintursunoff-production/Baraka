"""/api/files: Fayl tahlili (upload, list, catalog, ask). Separate from the business ledger."""

from __future__ import annotations

from typing import Any

from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.actions.audit import audit
from apps.tenancy.api import BusinessAPIView

from . import analyst, store

OK_EXT = (".xlsx", ".xlsm", ".xls", ".csv")


def chip(c: dict[str, Any]) -> str:
    from apps.ai import uz_format as uz

    def d(s: str | None) -> str:
        if not s:
            return ""
        m, dd = int(s[5:7]), int(s[8:10])
        return f"{dd}-{uz.MONTHS[m - 1][:3].lower()}"

    p = c.get("period") or {}
    span = (
        f" · {d(p.get('from'))} – {d(p.get('to'))} {str(p.get('to'))[:4]}" if p.get("from") else ""
    )
    return f"{c['filename']} · {c['sheets']} varaq{span}"


class FilesView(BusinessAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request: Request) -> Response:
        files = store.list_files(self.business.pk)
        for f in files:
            f["chip"] = chip(f)
        return Response({"files": files})

    def post(self, request: Request) -> Response:
        up = request.FILES.get("file")
        if up is None:
            return Response({"error": "no_file", "message": "Fayl tanlanmagan."}, status=400)
        name = str(up.name or "fayl.xlsx")[:200]
        if not name.lower().endswith(OK_EXT):
            return Response(
                {"error": "bad_type", "message": "Faqat .xlsx, .xls yoki .csv fayl."}, status=400
            )
        if up.size and up.size > store.MAX_BYTES:
            return Response({"error": "too_big", "message": "Fayl 20 MB dan katta."}, status=400)
        blob = up.read()
        try:
            cat = store.build(self.business.pk, blob, name)
        except Exception as exc:
            from apps.ai.gemini import scrub

            return Response(
                {
                    "error": "parse_failed",
                    "message": "Faylni o'qib bo'lmadi: " + scrub(str(exc))[:120],
                },
                status=400,
            )
        audit(
            f"user:{request.user.pk}", "file_upload", args={"file": name, "sheets": cat["sheets"]}
        )
        return Response({"file": _public(cat)})


def _public(cat: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": cat["id"],
        "filename": cat["filename"],
        "sheets": cat["sheets"],
        "period": cat["period"],
        "template": cat.get("template", ""),
        "chip": chip(cat),
        "notes": cat.get("notes", []),
        "tables": [
            {
                "table": t["table"],
                "sheet": t["sheet"],
                "role_label": t["role_label"],
                "layout": t["layout"],
                "header": f"{t['header_row']} / {t['first_col']}" if t["header_row"] else "—",
                "rows": t["rows"],
                "ignored": t.get("ignored", False),
                "hidden": t.get("hidden", False),
                "from": next((c.get("from") for c in t["columns"] if c.get("from")), None),
                "to": next((c.get("to") for c in t["columns"] if c.get("to")), None),
                "columns": [c["orig"] for c in t["columns"]][:30],
            }
            for t in cat["tables"]
        ],
    }


class FileDetailView(BusinessAPIView):
    def get(self, request: Request, file_id: str) -> Response:
        try:
            return Response({"file": _public(store.load_catalog(self.business.pk, file_id))})
        except FileNotFoundError:
            return Response({"error": "not_found"}, status=404)

    def delete(self, request: Request, file_id: str) -> Response:
        store.delete_file(self.business.pk, file_id)
        return Response({"ok": True})


class FileAskView(BusinessAPIView):
    def post(self, request: Request, file_id: str) -> Response:
        data = request.data if isinstance(request.data, dict) else {}
        q = str(data.get("question") or "").strip()[:2000]
        history = data.get("history") if isinstance(data.get("history"), list) else []
        try:
            store.load_catalog(self.business.pk, file_id)
        except FileNotFoundError:
            return Response({"error": "not_found"}, status=404)
        summary = not q or q == "__summary__"
        try:
            res = analyst.ask(
                self.business.pk, file_id, analyst.SUMMARY_Q if summary else q, history
            )
        except Exception as exc:
            from apps.ai.gemini import scrub

            return Response(
                {"markdown": "**Hozir tahlil qila olmadim.** " + scrub(str(exc))[:80], "chips": []}
            )
        md = res.get("markdown", "")
        chips: list[str] = []
        lines = md.rstrip().splitlines()
        if lines and lines[-1].strip().upper().startswith("CHIPS:"):
            chips = [c.strip() for c in lines[-1].split(":", 1)[1].split("|") if c.strip()][:3]
            md = "\n".join(lines[:-1]).rstrip()
        audit(
            f"user:{request.user.pk}",
            "file_ask",
            args={"file": file_id, "q": q[:200]},
            result={"model": res.get("model"), "steps": res.get("steps")},
        )
        return Response(
            {
                "markdown": md,
                "chips": chips,
                "model": res.get("model"),
                "ms": res.get("ms"),
                "summary": summary,
            }
        )
