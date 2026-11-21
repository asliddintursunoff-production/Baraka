"""Fayl tahlili storage: uploaded file -> per-file DuckDB (one table per detected table,
wide tables also in long form, raw non-empty cells in _cells) + a compact catalog.

Files live under var/files/<business_id>/<file_id>/ and are deleted after 30 days.
"""

from __future__ import annotations

import json
import re
import shutil
import threading
import time
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from django.conf import settings

from .reader import ROLE_LABELS, Column, DetectedTable, WorkbookModel, col_letter, read_any

ROOT = Path(settings.BASE_DIR) / "var" / "files"
KEEP_DAYS = 30
MAX_BYTES = 20 * 1024 * 1024
MAX_RESULT_ROWS = 500
SQL_TIMEOUT_S = 3.0


def _ident(s: str) -> str:
    t = re.sub(r"[‘’ʻʼ`']", "", s.lower())
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t or "t"


def biz_dir(business_id: int) -> Path:
    return ROOT / str(int(business_id))


def file_dir(business_id: int, file_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", file_id):
        raise FileNotFoundError(file_id)
    return biz_dir(business_id) / file_id


def split_multi(t: DetectedTable) -> list[DetectedTable]:
    """Side-by-side tables (blank header columns between them) -> separate tables."""
    groups: list[list[int]] = [[]]
    for k, c in enumerate(t.columns):
        if c.name.startswith("col_"):
            if groups[-1]:
                groups.append([])
            continue
        groups[-1].append(k)
    groups = [g for g in groups if g]
    if len(groups) < 2 or t.layout not in ("multi_table", "key_value + multi_table"):
        return [t]
    out = []
    for gi, g in enumerate(groups):
        cols = [Column(t.columns[k].name, t.columns[k].index, t.columns[k].type) for k in g]
        rows = [[r[k] for k in g] for r in t.rows if r[g[0]] not in (None, "")]
        out.append(
            DetectedTable(
                t.sheet,
                f"{t.sheet} {gi + 1}",
                "row_table",
                t.role,
                t.header_row,
                t.columns[g[0]].index,
                cols,
                rows,
                t.hidden,
            )
        )
    return out


def _sqltype(c: Column) -> str:
    return {"number": "DOUBLE", "date": "DATE"}.get(c.type, "VARCHAR")


def _val(v: Any, typ: str) -> Any:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if typ == "DOUBLE":
        if isinstance(v, bool):
            return float(v)
        if isinstance(v, (int, float)):
            return float(v)
        try:
            return float(str(v).replace(" ", "").replace("\xa0", "").replace(",", "."))
        except ValueError:
            return None
    if typ == "DATE":
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, date):
            return v
        return None
    if isinstance(v, datetime):
        return v.date().isoformat() if v.time() == datetime.min.time() else v.isoformat()
    return str(v)


def build(business_id: int, blob: bytes, filename: str) -> dict[str, Any]:
    import duckdb

    model = read_any(blob, filename)
    fid = uuid.uuid4().hex
    d = file_dir(business_id, fid)
    d.mkdir(parents=True, exist_ok=True)
    (d / ("original" + Path(filename).suffix.lower()[:6])).write_bytes(blob)
    con = duckdb.connect(str(d / "db.duckdb"))
    tables_meta: list[dict[str, Any]] = []
    used: set[str] = set()
    try:
        con.execute("CREATE TABLE _cells(sheet VARCHAR, r INTEGER, c VARCHAR, v VARCHAR)")
        _load_cells(con, blob, filename, model)
        for t0 in model.tables:
            for t in split_multi(t0):
                tables_meta.append(_load_table(con, t, used))
    finally:
        con.close()
    catalog = _catalog(fid, filename, model, tables_meta, len(blob))
    (d / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, default=str))
    return catalog


def _load_cells(con: Any, blob: bytes, filename: str, model: WorkbookModel) -> None:
    if not filename.lower().endswith((".xlsx", ".xlsm")):
        return
    import io

    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
    try:
        batch: list[tuple[str, int, str, str]] = []
        for ws in wb.worksheets:
            for i, row in enumerate(ws.iter_rows(values_only=True), 1):
                for j, v in enumerate(row):
                    if v is not None and v != "":
                        batch.append((ws.title, i, col_letter(j), str(v)[:500]))
        if batch:
            import csv as _csv
            import tempfile

            with tempfile.NamedTemporaryFile(
                "w", suffix=".csv", delete=False, newline="", encoding="utf-8"
            ) as fh:
                _csv.writer(fh).writerows(batch)
                tmp = fh.name
            try:
                con.execute(
                    "INSERT INTO _cells SELECT * FROM read_csv(?, header=false, columns={'sheet':'VARCHAR','r':'INTEGER','c':'VARCHAR','v':'VARCHAR'})",
                    [tmp],
                )
            finally:
                Path(tmp).unlink(missing_ok=True)
    finally:
        wb.close()


def _bulk(con: Any, name: str, types_: dict[str, str], rows: list[Any]) -> None:
    import csv as _csv
    import tempfile

    with tempfile.NamedTemporaryFile(
        "w", suffix=".csv", delete=False, newline="", encoding="utf-8"
    ) as fh:
        w = _csv.writer(fh)
        for r in rows:
            w.writerow(
                ["" if v is None else (v.isoformat() if isinstance(v, date) else v) for v in r]
            )
        tmp = fh.name
    try:
        spec = "{" + ", ".join(f"'c{i}': '{t}'" for i, t in enumerate(types_.values())) + "}"
        con.execute(
            f"INSERT INTO \"{name}\" SELECT * FROM read_csv(?, header=false, columns={spec}, nullstr='')",
            [tmp],
        )
    finally:
        Path(tmp).unlink(missing_ok=True)


def _load_table(con: Any, t: DetectedTable, used: set[str]) -> dict[str, Any]:
    base = _ident(t.name)
    name, k = base, 2
    while name in used:
        name, k = f"{base}_{k}", k + 1
    used.add(name)
    cols, seen = [], set()
    for c in t.columns:
        cn = _ident(c.name)
        if cn[0].isdigit():
            cn = "c_" + cn
        while cn in seen:
            cn += "_"
        seen.add(cn)
        cols.append((cn, c, _sqltype(c)))
    meta: dict[str, Any] = {
        "table": name,
        "sheet": t.sheet,
        "role": t.role,
        "role_label": ROLE_LABELS.get(t.role, t.role),
        "layout": t.layout,
        "header_row": t.header_row,
        "first_col": col_letter(t.first_col),
        "hidden": t.hidden,
        "ignored": t.role == "ignore",
        "rows": len(t.rows),
        "columns": [{"name": cn, "orig": c.name, "type": typ} for cn, c, typ in cols],
    }
    if not cols:
        con.execute(f'CREATE TABLE "{name}"(text VARCHAR)')
        rows_txt = [" | ".join(str(x) for x in r if x not in (None, "")) for r in t.rows]
        if rows_txt:
            con.executemany(f'INSERT INTO "{name}" VALUES (?)', [[x] for x in rows_txt])
        meta["columns"] = [{"name": "text", "orig": "matn", "type": "VARCHAR"}]
        meta["sample"] = rows_txt[:5]
        return meta
    data = {
        cn: [_val(r[i] if i < len(r) else None, typ) for r in t.rows]
        for i, (cn, _c, typ) in enumerate(cols)
    }
    ddl = ", ".join(f'"{cn}" {typ}' for cn, _c, typ in cols)
    con.execute(f'CREATE TABLE "{name}"({ddl})')
    if t.rows:
        _bulk(con, name, {cn: typ for cn, _c, typ in cols}, list(zip(*data.values(), strict=True)))
    # stats
    for cm in meta["columns"]:
        cn, typ = cm["name"], cm["type"]
        if typ == "DATE":
            lo, hi = con.execute(f'SELECT min("{cn}"), max("{cn}") FROM "{name}"').fetchone()
            cm["from"], cm["to"] = (str(lo) if lo else None), (str(hi) if hi else None)
        elif typ == "DOUBLE":
            s, n = con.execute(f'SELECT sum("{cn}"), count("{cn}") FROM "{name}"').fetchone()
            cm["sum"], cm["count"] = (round(s, 2) if s is not None else None), n
    meta["sample"] = [
        [str(x)[:40] if x is not None else None for x in r]
        for r in con.execute(f'SELECT * FROM "{name}" LIMIT 3').fetchall()
    ]
    # wide period -> long form
    if t.period_axis:
        label_cols = [cm["name"] for cm in meta["columns"] if cm["type"] == "VARCHAR"][:2]
        per = [
            (cn, t.period_axis[c.index])
            for cn, c, typ in cols
            if c.index in t.period_axis and typ == "DOUBLE"
        ]
        if label_cols and per:
            lname = f"{name}_long"
            sel = " UNION ALL ".join(
                f'SELECT {", ".join(chr(34) + lc + chr(34) for lc in label_cols)}, DATE \'{p}\' AS period, "{cn}" AS value FROM "{name}" WHERE "{cn}" IS NOT NULL'
                for cn, p in per
            )
            con.execute(f'CREATE TABLE "{lname}" AS {sel}')
            meta["long_table"] = lname
            meta["long_columns"] = label_cols + ["period", "value"]
            meta["periods"] = [per[0][1], per[-1][1]]
    return meta


def _catalog(
    fid: str, filename: str, model: WorkbookModel, tables: list[dict[str, Any]], size: int
) -> dict[str, Any]:
    dates = [
        (c.get("from"), c.get("to"))
        for t in tables
        if t["role"].startswith("journal")
        for c in t["columns"]
        if c.get("from")
    ]
    lo = min((a for a, _ in dates), default=None)
    hi = max((b for _, b in dates), default=None)
    return {
        "id": fid,
        "filename": filename,
        "size": size,
        "uploaded_at": int(time.time()),
        "sheets": len(model.sheet_names),
        "template": model.template,
        "period": {"from": lo, "to": hi},
        "tables": tables,
        "notes": model.notes,
    }


def load_catalog(business_id: int, file_id: str) -> dict[str, Any]:
    return json.loads((file_dir(business_id, file_id) / "catalog.json").read_text())


def list_files(business_id: int) -> list[dict[str, Any]]:
    out = []
    root = biz_dir(business_id)
    if not root.exists():
        return out
    now = time.time()
    for d in root.iterdir():
        cat = d / "catalog.json"
        if not cat.exists():
            continue
        if now - cat.stat().st_mtime > KEEP_DAYS * 86400:
            shutil.rmtree(d, ignore_errors=True)
            continue
        c = json.loads(cat.read_text())
        out.append(
            {k: c[k] for k in ("id", "filename", "sheets", "period", "uploaded_at", "template")}
        )
    return sorted(out, key=lambda x: -x["uploaded_at"])


def delete_file(business_id: int, file_id: str) -> None:
    shutil.rmtree(file_dir(business_id, file_id), ignore_errors=True)


# --- safe read-only SQL ----------------------------------------------------------------------
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|copy|attach|detach|install|load|pragma|create|drop|alter|export|"
    r"import|call|set|reset|checkpoint|vacuum|read_csv\w*|read_parquet|read_json\w*|read_text|"
    r"read_blob|parquet_scan|csv_scan|httpfs|glob|getenv|sniff_csv|query_table|query)\b",
    re.I,
)


class SqlRejected(ValueError):
    pass


def check_sql(q: str) -> str:
    s = q.strip().rstrip(";").strip()
    if ";" in s:
        raise SqlRejected("faqat bitta so'rov")
    if not re.match(r"(?is)^\s*(select|with)\b", s):
        raise SqlRejected("faqat SELECT / WITH")
    no_str = re.sub(r"'(?:[^']|'')*'", "''", s)
    if _FORBIDDEN.search(no_str):
        raise SqlRejected("taqiqlangan funksiya yoki buyruq")
    if (
        re.search(r"(https?:|s3:|gs:|/|\\)", re.sub(r"'(?:[^'/]|'')*'", "''", s).replace("/ ", ""))
        and "'" in s
        and re.search(r"'[^']*(https?:|/|\\)[^']*'", s)
    ):
        raise SqlRejected("fayl yoki URL yo'li taqiqlangan")
    return s


_lock = threading.Lock()


def run_sql(business_id: int, file_id: str, q: str) -> dict[str, Any]:
    import duckdb

    s = check_sql(q)
    con = duckdb.connect(
        str(file_dir(business_id, file_id) / "db.duckdb"),
        read_only=True,
        config={
            "enable_external_access": False,
            "autoload_known_extensions": False,
            "autoinstall_known_extensions": False,
        },
    )
    timer = threading.Timer(SQL_TIMEOUT_S, con.interrupt)
    timer.start()
    try:
        cur = con.execute(s)
        cols = [d[0] for d in cur.description or []]
        rows = cur.fetchmany(MAX_RESULT_ROWS + 1)
    except duckdb.InterruptException as exc:
        raise SqlRejected("3 soniyadan oshdi; agregatsiya (SUM/GROUP BY) ishlating") from exc
    finally:
        timer.cancel()
        con.close()
    truncated = len(rows) > MAX_RESULT_ROWS
    rows = rows[:MAX_RESULT_ROWS]
    out_rows = [
        [
            (
                round(v, 4)
                if isinstance(v, float)
                else (str(v) if v is not None and not isinstance(v, (int, float, str)) else v)
            )
            for v in r
        ]
        for r in rows
    ]
    res: dict[str, Any] = {"columns": cols, "rows": out_rows, "row_count": len(out_rows)}
    if truncated:
        res["note"] = "500 qatordan ko'p: GROUP BY / SUM bilan agregatsiya qiling"
    return res


def cells(business_id: int, file_id: str, sheet: str, a1: str) -> dict[str, Any]:
    m = re.fullmatch(r"([A-Z]{1,3})(\d+):([A-Z]{1,3})(\d+)", a1.strip().upper())
    if not m:
        raise SqlRejected("diapazon A1:D20 ko'rinishida bo'lsin")
    c1, r1, c2, r2 = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
    if r2 - r1 > 200:
        r2 = r1 + 200
    import duckdb

    con = duckdb.connect(
        str(file_dir(business_id, file_id) / "db.duckdb"),
        read_only=True,
        config={"enable_external_access": False},
    )
    try:
        rows = con.execute(
            "SELECT r, c, v FROM _cells WHERE sheet = ? AND r BETWEEN ? AND ? AND length(c) BETWEEN ? AND ? ORDER BY r, length(c), c",
            [sheet, r1, r2, min(len(c1), len(c2)), max(len(c1), len(c2))],
        ).fetchall()
    finally:
        con.close()

    def key(c: str) -> tuple[int, str]:
        return (len(c), c)

    rows = [r for r in rows if key(c1) <= key(r[1]) <= key(c2)]
    return {"sheet": sheet, "range": a1, "cells": [f"{c}{r}={v}" for r, c, v in rows][:1500]}
