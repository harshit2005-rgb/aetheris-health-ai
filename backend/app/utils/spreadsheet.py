"""Reading and writing the spreadsheets of data import and export.

``docs/modules/17-data-import-export.md`` §4 rules 2 and 6, §11. Files are read
in memory and never stored. A file is accepted only if its name, its declared
type and its first bytes all agree on ``.xlsx`` or ``.csv``.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Final

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils.exceptions import InvalidFileException

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "MAX_BYTES",
    "MAX_ROWS",
    "XLSX_TYPE",
    "CellError",
    "SheetData",
    "SpreadsheetError",
    "header_key",
    "parse_bool",
    "parse_date",
    "parse_decimal",
    "parse_int",
    "parse_phone",
    "read_spreadsheet",
    "workbook_bytes",
]

MAX_BYTES: Final = 5 * 1024 * 1024
MAX_ROWS: Final = 2000
XLSX_TYPE: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_CSV_TYPES: Final = frozenset(
    {"text/csv", "application/csv", "text/plain", "application/vnd.ms-excel"}
)
_XLSX_TYPES: Final = frozenset({XLSX_TYPE, "application/octet-stream"})
_ZIP_MAGIC: Final = b"PK\x03\x04"


class SpreadsheetError(ValueError):
    """The file as a whole cannot be read (wrong type, too big, no header)."""


class CellError(ValueError):
    """One cell's value is not what its column expects."""


@dataclass(frozen=True, slots=True)
class SheetData:
    """A file read into rows keyed by normalised header."""

    headers: tuple[str, ...]
    #: ``(row number as the user sees it, values by header key)``.
    rows: tuple[tuple[int, dict[str, Any]], ...]


def header_key(text: object) -> str:
    """A header as a lookup key: lower case, punctuation and spaces folded.

    ``"Date of birth (YYYY-MM-DD)"`` → ``"date_of_birth"``: anything in
    brackets is a hint for the person filling the sheet, not part of the name.
    """
    cleaned = re.sub(r"\(.*?\)", "", str(text or "")).strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", cleaned).strip("_")


def _blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _kind(filename: str, content_type: str, data: bytes) -> str:
    name = filename.lower()
    declared = content_type.split(";")[0].strip().lower()
    if name.endswith(".xlsx"):
        if declared not in _XLSX_TYPES or not data.startswith(_ZIP_MAGIC):
            msg = "This doesn't look like an Excel (.xlsx) file."
            raise SpreadsheetError(msg)
        return "xlsx"
    if name.endswith(".csv"):
        if declared not in _CSV_TYPES or data.startswith(_ZIP_MAGIC) or b"\x00" in data[:4096]:
            msg = "This doesn't look like a CSV file."
            raise SpreadsheetError(msg)
        return "csv"
    msg = "Upload an Excel (.xlsx) or CSV (.csv) file."
    raise SpreadsheetError(msg)


def _xlsx_rows(data: bytes) -> list[list[Any]]:
    try:
        book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except (InvalidFileException, zipfile.BadZipFile, KeyError, OSError) as exc:
        msg = "The Excel file could not be opened. Save it again as .xlsx and retry."
        raise SpreadsheetError(msg) from exc
    try:
        sheet = book.worksheets[0]
        rows: list[list[Any]] = []
        for values in sheet.iter_rows(values_only=True):
            rows.append(list(values))
            if len(rows) > MAX_ROWS + 1:
                break
        return rows
    finally:
        book.close()


def _csv_rows(data: bytes) -> list[list[Any]]:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover — cp1252 decodes almost anything
        msg = "The CSV file's text encoding could not be read. Save it as UTF-8."
        raise SpreadsheetError(msg)
    rows: list[list[Any]] = []
    for values in csv.reader(io.StringIO(text)):
        rows.append(list(values))
        if len(rows) > MAX_ROWS + 1:
            break
    return rows


def read_spreadsheet(data: bytes, *, filename: str, content_type: str) -> SheetData:
    """Read an uploaded file into rows (§4 rules 2 and 6).

    :param data: The file's bytes.
    :param filename: The name it was uploaded with.
    :param content_type: The declared media type.
    :returns: The header keys and the non-empty data rows.
    :raises SpreadsheetError: If the file is the wrong type, too large, has no
        header row, no data, or more than :data:`MAX_ROWS` rows.
    """
    if len(data) > MAX_BYTES:
        msg = "The file is larger than 5 MB. Split it into smaller files."
        raise SpreadsheetError(msg)
    raw = _xlsx_rows(data) if _kind(filename, content_type, data) == "xlsx" else _csv_rows(data)
    raw = [row for row in raw if not all(_blank(v) for v in row)]
    if not raw:
        msg = "The file is empty."
        raise SpreadsheetError(msg)
    headers = tuple(header_key(h) for h in raw[0])
    body = raw[1:]
    if not body:
        msg = "The file has a header row but nothing to import."
        raise SpreadsheetError(msg)
    if len(body) > MAX_ROWS:
        msg = f"The file has more than {MAX_ROWS:,} rows. Split it into smaller files."
        raise SpreadsheetError(msg)
    rows = tuple(
        (
            number,
            {
                key: (value.strip() if isinstance(value, str) else value)
                for key, value in zip(headers, values, strict=False)
                if key and not _blank(value)
            },
        )
        for number, values in enumerate(body, start=2)
    )
    return SheetData(headers=headers, rows=rows)


# ── Cell values ──────────────────────────────────────────────────────────────

_DATE_FORMATS: Final = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y")


def parse_date(value: object) -> date:
    """An Excel date cell, ``YYYY-MM-DD`` or ``DD/MM/YYYY``."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()  # noqa: DTZ007 — a calendar date, no time
        except ValueError:
            continue
    msg = "Use a date like 1990-01-31 or 31/01/1990."
    raise CellError(msg)


def parse_phone(value: object) -> str:
    """A phone number in E.164; a bare Indian 10-digit mobile gets ``+91``."""
    text = str(value).strip()
    if isinstance(value, float) and value.is_integer():
        text = str(int(value))
    digits = re.sub(r"[\s\-().]", "", text)
    if re.fullmatch(r"[6-9]\d{9}", digits):
        return f"+91{digits}"
    if re.fullmatch(r"0[6-9]\d{9}", digits):
        return f"+91{digits[1:]}"
    if re.fullmatch(r"91[6-9]\d{9}", digits):
        return f"+{digits}"
    return digits


_TRUE: Final = frozenset({"yes", "y", "true", "1", "t"})
_FALSE: Final = frozenset({"no", "n", "false", "0", "f"})


def parse_bool(value: object) -> bool:
    """yes/no, y/n, true/false, 1/0."""
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        text = str(int(value))
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    msg = "Use yes or no."
    raise CellError(msg)


def parse_decimal(value: object) -> Decimal:
    """A number such as a price: ``1,250.50`` or ``₹1250.5``."""
    text = str(value).strip().replace(",", "").replace("₹", "").replace("Rs.", "").strip()
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        msg = "Use a number, e.g. 250 or 99.50."
        raise CellError(msg) from exc
    if not number.is_finite():
        msg = "Use a number, e.g. 250 or 99.50."
        raise CellError(msg)
    return number


def parse_int(value: object) -> int:
    """A whole number."""
    number = parse_decimal(value)
    if number != number.to_integral_value():
        msg = "Use a whole number."
        raise CellError(msg)
    return int(number)


# ── Writing ──────────────────────────────────────────────────────────────────

_HEADER_FILL: Final = PatternFill("solid", fgColor="0F1B2D")
_HEADER_FONT: Final = Font(bold=True, color="FFFFFF")


def workbook_bytes(sheets: Sequence[tuple[str, Sequence[str], Sequence[Sequence[Any]]]]) -> bytes:
    """Write ``(title, headers, rows)`` sheets to an ``.xlsx`` file.

    :param sheets: One entry per sheet, in order.
    :returns: The workbook's bytes.
    """
    book = Workbook(write_only=True)
    for title, headers, rows in sheets:
        sheet = book.create_sheet(title=title[:31])
        header_cells = []
        for text in headers:
            cell = _styled_cell(sheet, text)
            header_cells.append(cell)
        sheet.append(header_cells)
        for row in rows:
            sheet.append([_safe(v) for v in row])
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _styled_cell(sheet: Any, text: str) -> Any:
    from openpyxl.cell import WriteOnlyCell  # noqa: PLC0415 — only the writer needs it

    cell = WriteOnlyCell(sheet, value=text)
    cell.fill = _HEADER_FILL
    cell.font = _HEADER_FONT
    return cell


def _safe(value: Any) -> Any:
    """A value Excel will show as data, never run as a formula (CSV/formula injection)."""
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return "'" + value
    if isinstance(value, Decimal):
        return float(value)
    return value
