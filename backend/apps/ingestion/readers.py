"""SourceReader: one interface for Google Sheets and .xlsx on Drive (and a fake for tests).

Google Sheets: spreadsheets.get (sheet titles) + ONE values.batchGet for all sheets with
UNFORMATTED_VALUE / SERIAL_NUMBER (numbers stay numbers, dates are serials).
.xlsx: Drive files.get?alt=media, then openpyxl(read_only, data_only). Both produce the
same WorkbookData, so the rest of ingestion is identical.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any, Protocol

from apps.integrations import google
from apps.integrations.models import DataSource
from apps.tenancy.models import Business

MAX_ROWS = 20_000


@dataclass
class SheetData:
    title: str
    rows: list[list[Any]]


@dataclass
class WorkbookData:
    file_id: str
    name: str
    modified_time: str
    sheets: list[SheetData] = field(default_factory=list)


class SourceReader(Protocol):
    def modified_time(self, source: DataSource) -> str: ...

    def read(self, source: DataSource) -> WorkbookData: ...


def _trim(rows: list[list[Any]]) -> list[list[Any]]:
    out = [list(r) for r in rows[:MAX_ROWS]]
    while out and all(c in (None, "") for c in out[-1]):
        out.pop()
    return out


class GoogleSheetsReader:
    def __init__(self, business: Business) -> None:
        self.business = business

    def modified_time(self, source: DataSource) -> str:
        return str(google.file_meta(self.business, source.spreadsheet_id).get("modifiedTime", ""))

    def read(self, source: DataSource) -> WorkbookData:
        meta = google.file_meta(self.business, source.spreadsheet_id)
        svc = google.sheets_service(self.business)
        info = google.call(
            lambda: (
                svc.spreadsheets()
                .get(
                    spreadsheetId=source.spreadsheet_id,
                    fields="properties.title,sheets.properties.title",
                )
                .execute()
            )
        )
        titles = [s["properties"]["title"] for s in info.get("sheets", [])]
        ranges = ["'" + t.replace("'", "''") + "'" for t in titles]
        data = google.call(
            lambda: (
                svc.spreadsheets()
                .values()
                .batchGet(
                    spreadsheetId=source.spreadsheet_id,
                    ranges=ranges,
                    valueRenderOption="UNFORMATTED_VALUE",
                    dateTimeRenderOption="SERIAL_NUMBER",
                )
                .execute()
            )
        )
        sheets = [
            SheetData(title=t, rows=_trim(vr.get("values", [])))
            for t, vr in zip(titles, data.get("valueRanges", []), strict=False)
        ]
        return WorkbookData(
            source.spreadsheet_id,
            str(meta.get("name", "")),
            str(meta.get("modifiedTime", "")),
            sheets,
        )


def xlsx_sheets(blob: bytes) -> list[SheetData]:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
    try:
        return [
            SheetData(title=ws.title, rows=_trim([list(r) for r in ws.iter_rows(values_only=True)]))
            for ws in wb.worksheets
        ]
    finally:
        wb.close()


class DriveXlsxReader:
    def __init__(self, business: Business) -> None:
        self.business = business

    def modified_time(self, source: DataSource) -> str:
        return str(google.file_meta(self.business, source.spreadsheet_id).get("modifiedTime", ""))

    def read(self, source: DataSource) -> WorkbookData:
        meta = google.file_meta(self.business, source.spreadsheet_id)
        svc = google.drive_service(self.business)
        blob: bytes = google.call(
            lambda: (
                svc.files()
                .get_media(fileId=source.spreadsheet_id, supportsAllDrives=True)
                .execute()
            )
        )
        return WorkbookData(
            source.spreadsheet_id,
            str(meta.get("name", "")),
            str(meta.get("modifiedTime", "")),
            xlsx_sheets(blob),
        )


class FakeReader:
    """Tests: workbooks by file id; bump `modified` to simulate an edit."""

    def __init__(self, books: dict[str, WorkbookData]) -> None:
        self.books = books
        self.reads = 0

    def modified_time(self, source: DataSource) -> str:
        return self.books[source.spreadsheet_id].modified_time

    def read(self, source: DataSource) -> WorkbookData:
        self.reads += 1
        return self.books[source.spreadsheet_id]


_override: SourceReader | None = None


def set_reader_override(reader: SourceReader | None) -> None:
    """Tests inject a FakeReader for every source."""
    global _override
    _override = reader


def reader_for(source: DataSource, business: Business) -> SourceReader:
    if _override is not None:
        return _override
    if source.kind == DataSource.Kind.XLSX:
        return DriveXlsxReader(business)
    return GoogleSheetsReader(business)
