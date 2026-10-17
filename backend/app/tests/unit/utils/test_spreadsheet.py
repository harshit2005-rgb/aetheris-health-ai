"""Unit tests for reading and writing import/export spreadsheets (spec 17 §4, §11)."""

from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal

import pytest
from openpyxl import Workbook, load_workbook

from app.utils.spreadsheet import (
    MAX_ROWS,
    XLSX_TYPE,
    CellError,
    SpreadsheetError,
    header_key,
    parse_bool,
    parse_date,
    parse_decimal,
    parse_int,
    parse_phone,
    read_spreadsheet,
    workbook_bytes,
)


def _xlsx(rows: list[list[object]]) -> bytes:
    book = Workbook()
    sheet = book.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _read_xlsx(rows: list[list[object]]):  # type: ignore[no-untyped-def]
    return read_spreadsheet(_xlsx(rows), filename="patients.xlsx", content_type=XLSX_TYPE)


class TestReading:
    def test_xlsx_rows_are_keyed_by_header_and_numbered_as_excel_shows_them(self) -> None:
        sheet = _read_xlsx(
            [
                ["First name", "Date of birth (YYYY-MM-DD)", "Phone"],
                ["Ananya", datetime(1990, 1, 31), 9812345678],
                [None, None, None],
                ["Ravi", "15/08/1985", ""],
            ]
        )

        assert sheet.headers == ("first_name", "date_of_birth", "phone")
        assert [n for n, _ in sheet.rows] == [2, 3]
        assert sheet.rows[0][1]["first_name"] == "Ananya"
        # Blank cells are left out rather than passed on as "".
        assert "phone" not in sheet.rows[1][1]

    def test_csv_with_a_byte_order_mark(self) -> None:
        data = "﻿Code,Name,Price\nCONS,Consultation,500\n".encode()

        sheet = read_spreadsheet(data, filename="services.csv", content_type="text/csv")

        assert sheet.headers == ("code", "name", "price")
        assert sheet.rows == ((2, {"code": "CONS", "name": "Consultation", "price": "500"}),)

    @pytest.mark.parametrize(
        ("filename", "content_type", "data"),
        [
            ("patients.pdf", "application/pdf", b"%PDF-1.7"),
            ("patients.xlsx", XLSX_TYPE, b"not a zip at all"),
            ("patients.xlsx", "image/png", b"PK\x03\x04rest"),
            ("patients.csv", "text/csv", b"PK\x03\x04 a zip renamed to csv"),
            ("patients.xlsx", XLSX_TYPE, b"PK\x03\x04 broken zip"),
        ],
    )
    def test_a_file_whose_name_type_and_content_disagree_is_refused(
        self, filename: str, content_type: str, data: bytes
    ) -> None:
        with pytest.raises(SpreadsheetError):
            read_spreadsheet(data, filename=filename, content_type=content_type)

    def test_a_file_over_five_megabytes_is_refused(self) -> None:
        with pytest.raises(SpreadsheetError, match="5 MB"):
            read_spreadsheet(
                b"a" * (5 * 1024 * 1024 + 1), filename="x.csv", content_type="text/csv"
            )

    def test_too_many_rows_are_refused(self) -> None:
        data = ("Code\n" + "X\n" * (MAX_ROWS + 1)).encode()

        with pytest.raises(SpreadsheetError, match="2,000"):
            read_spreadsheet(data, filename="x.csv", content_type="text/csv")

    def test_exactly_the_limit_is_accepted(self) -> None:
        data = ("Code\n" + "X\n" * MAX_ROWS).encode()

        sheet = read_spreadsheet(data, filename="x.csv", content_type="text/csv")

        assert len(sheet.rows) == MAX_ROWS

    @pytest.mark.parametrize("data", [b"", b"\n\n", b"Code,Name\n"])
    def test_an_empty_file_or_headers_only_is_refused(self, data: bytes) -> None:
        with pytest.raises(SpreadsheetError):
            read_spreadsheet(data, filename="x.csv", content_type="text/csv")


class TestHeaders:
    @pytest.mark.parametrize(
        ("text", "key"),
        [
            ("First name", "first_name"),
            ("  DATE OF BIRTH (YYYY-MM-DD) ", "date_of_birth"),
            ("Previous record no.", "previous_record_no"),
            ("PIN code", "pin_code"),
            (None, ""),
        ],
    )
    def test_header_key(self, text: object, key: str) -> None:
        assert header_key(text) == key


class TestCells:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("1990-01-31", date(1990, 1, 31)),
            ("31/01/1990", date(1990, 1, 31)),
            ("31-01-1990", date(1990, 1, 31)),
            (datetime(1990, 1, 31, 0, 0), date(1990, 1, 31)),
            (date(1990, 1, 31), date(1990, 1, 31)),
        ],
    )
    def test_dates(self, value: object, expected: date) -> None:
        assert parse_date(value) == expected

    @pytest.mark.parametrize("value", ["31 Jan 1990", "1990/31/01", "yesterday"])
    def test_bad_dates(self, value: str) -> None:
        with pytest.raises(CellError):
            parse_date(value)

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("9812345678", "+919812345678"),
            (9812345678.0, "+919812345678"),
            ("98123 45678", "+919812345678"),
            ("09812345678", "+919812345678"),
            ("919812345678", "+919812345678"),
            ("+44 20 7946 0958", "+442079460958"),
        ],
    )
    def test_phones(self, value: object, expected: str) -> None:
        assert parse_phone(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [("Yes", True), ("n", False), ("TRUE", True), (0, False), (1, True), (True, True)],
    )
    def test_booleans(self, value: object, expected: bool) -> None:
        assert parse_bool(value) is expected

    def test_a_bad_boolean(self) -> None:
        with pytest.raises(CellError):
            parse_bool("maybe")

    @pytest.mark.parametrize(
        ("value", "expected"),
        [("1,250.50", Decimal("1250.50")), ("₹99", Decimal("99")), (12.5, Decimal("12.5"))],
    )
    def test_decimals(self, value: object, expected: Decimal) -> None:
        assert parse_decimal(value) == expected

    @pytest.mark.parametrize("value", ["abc", "NaN", "Infinity"])
    def test_bad_decimals(self, value: str) -> None:
        with pytest.raises(CellError):
            parse_decimal(value)

    def test_whole_numbers(self) -> None:
        assert parse_int("4") == 4
        with pytest.raises(CellError):
            parse_int("4.5")


class TestWriting:
    def test_sheets_headers_and_rows_round_trip(self) -> None:
        data = workbook_bytes(
            [("Patients", ["Name", "Fee"], [["Ananya", Decimal("500.00")]]), ("Empty", ["A"], [])]
        )

        book = load_workbook(io.BytesIO(data))
        assert book.sheetnames == ["Patients", "Empty"]
        rows = list(book["Patients"].iter_rows(values_only=True))
        assert rows == [("Name", "Fee"), ("Ananya", 500.0)]

    @pytest.mark.parametrize("value", ['=HYPERLINK("http://x")', "+1+1", "-2", "@SUM(A1)"])
    def test_text_that_looks_like_a_formula_is_written_as_text(self, value: str) -> None:
        data = workbook_bytes([("S", ["A"], [[value]])])

        cell = load_workbook(io.BytesIO(data))["S"]["A2"]
        assert cell.data_type != "f"
        assert cell.value == "'" + value
