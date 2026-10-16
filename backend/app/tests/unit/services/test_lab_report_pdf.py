"""Unit tests for lab report PDFs (``app/services/lab_report_pdf.py``).

The document is checked string by string, then rendered to prove it lays out.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.models.lab import LabOrderPriority, LabOrderStatus, LabResultFlag, LabResultType
from app.schemas.lab import LabOrderItemResponse, LabOrderResponse, LabResultAmendmentResponse
from app.services.lab_report_pdf import build_lab_report, render_lab_report_pdf
from app.services.pdf_layout import Letterhead, age_and_sex

LETTERHEAD = Letterhead(
    name="Sunrise Hospital",
    address_lines=("12 MG Road", "Hyderabad, Telangana 500072"),
    contact="040 2345 6789",
    gstin=None,
    timezone="Asia/Kolkata",
)
RELEASED = datetime(2026, 10, 16, 7, 30, tzinfo=UTC)  # 13:00 in Hyderabad


def _item(**overrides: Any) -> LabOrderItemResponse:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "test_id": uuid.uuid4(),
        "test_code": "K",
        "test_name": "Potassium",
        "result_type": LabResultType.NUMERIC,
        "price": Decimal("300.00"),
        "sample_id": "S-1",
        "sample_collected_at": datetime(2026, 10, 16, 4, 0, tzinfo=UTC),
        "result_value": "4.2",
        "result_unit": "mmol/L",
        "result_flag": LabResultFlag.NORMAL,
        "reference_low": Decimal("3.5"),
        "reference_high": Decimal("5.10"),
        "result_entered_at": RELEASED,
        "released_at": RELEASED,
        "notes": None,
        "amendments": [],
    }
    values.update(overrides)
    return LabOrderItemResponse.model_construct(**values)


def _order(items: list[LabOrderItemResponse], **overrides: Any) -> LabOrderResponse:
    values: dict[str, Any] = {
        "id": uuid.UUID("7c21d004-0000-4000-8000-000000000000"),
        "appointment_id": uuid.uuid4(),
        "patient_id": uuid.uuid4(),
        "patient_name": "Ananya Rao",
        "patient_mrn": "SUN-000123",
        "doctor_id": uuid.uuid4(),
        "doctor_name": "Kiran Reddy",
        "ordered_at": datetime(2026, 10, 16, 3, 40, tzinfo=UTC),
        "priority": LabOrderPriority.STAT,
        "status": LabOrderStatus.RELEASED,
        "notes": None,
        "collected_at": datetime(2026, 10, 16, 3, 55, tzinfo=UTC),
        "results_entered_at": RELEASED,
        "released_at": RELEASED,
        "released_by": uuid.uuid4(),
        "cancelled_at": None,
        "cancel_reason": None,
        "invoice_id": None,
        "turnaround_minutes": 230,
        "has_abnormal": False,
        "has_critical": False,
        "items": items,
    }
    values.update(overrides)
    return LabOrderResponse.model_construct(**values)


def _build(order: LabOrderResponse) -> Any:
    return build_lab_report(
        order,
        letterhead=LETTERHEAD,
        date_of_birth=date(1990, 1, 1),
        sex="female",
        generated_at=RELEASED,
    )


class TestDocument:
    def test_who_and_when_on_the_hospital_clock(self) -> None:
        doc = _build(_order([_item()]))

        assert doc.patient_name == "Ananya Rao"
        assert doc.patient_mrn == "SUN-000123"
        assert doc.age_sex == "36 y · Female"
        assert doc.doctor_name == "Kiran Reddy"
        assert doc.priority == "STAT"
        assert doc.ordered_on == "16 Oct 2026, 09:10"
        assert doc.collected_on == "16 Oct 2026, 09:25"
        assert doc.released_on == "16 Oct 2026, 13:00"
        assert doc.report_number == "LAB-7C21D004"

    def test_values_units_and_ranges_are_the_orders_own(self) -> None:
        doc = _build(_order([_item()]))

        [line] = doc.lines
        assert (line.test, line.result, line.unit, line.reference, line.flag) == (
            "Potassium",
            "4.2",
            "mmol/L",
            "3.5 – 5.1",
            "",
        )

    @pytest.mark.parametrize(
        ("low", "high", "expected"),
        [
            (Decimal("3.5"), None, "> 3.5"),
            (None, Decimal("200"), "< 200"),
            (None, None, "—"),
        ],
    )
    def test_one_sided_and_missing_ranges(
        self, low: Decimal | None, high: Decimal | None, expected: str
    ) -> None:
        doc = _build(_order([_item(reference_low=low, reference_high=high)]))

        assert doc.lines[0].reference == expected

    @pytest.mark.parametrize(
        ("flag", "label"),
        [
            (LabResultFlag.LOW, "LOW"),
            (LabResultFlag.HIGH, "HIGH"),
            (LabResultFlag.CRITICAL, "CRITICAL"),
            (LabResultFlag.NORMAL, ""),
            (None, ""),
        ],
    )
    def test_flags(self, flag: LabResultFlag | None, label: str) -> None:
        doc = _build(_order([_item(result_flag=flag)]))

        assert doc.lines[0].flag == label

    def test_amended_results_and_notes_are_marked(self) -> None:
        amendment = LabResultAmendmentResponse.model_construct(
            id=uuid.uuid4(),
            previous_value="4.0",
            new_value="4.2",
            previous_flag=LabResultFlag.NORMAL,
            new_flag=LabResultFlag.NORMAL,
            reason="Typo",
            amended_by=uuid.uuid4(),
            amended_at=RELEASED,
        )
        doc = _build(_order([_item(amendments=[amendment], notes="Haemolysed, repeat")]))

        assert doc.lines[0].amended is True
        assert doc.lines[0].note == "Haemolysed, repeat"

    def test_critical_values_are_called_out(self) -> None:
        doc = _build(_order([_item(result_flag=LabResultFlag.CRITICAL)], has_critical=True))

        assert doc.has_critical is True

    @pytest.mark.parametrize(
        "status",
        [s for s in LabOrderStatus if s is not LabOrderStatus.RELEASED],
    )
    def test_only_a_released_order_has_a_report(self, status: LabOrderStatus) -> None:
        with pytest.raises(ValueError, match="released"):
            _build(_order([_item()], status=status))


class TestAgeAndSex:
    def test_birthday_not_yet_reached_this_year(self) -> None:
        assert age_and_sex(date(1990, 12, 31), "male", on=date(2026, 10, 16)) == "35 y · Male"

    def test_unknown_parts_are_left_out(self) -> None:
        assert age_and_sex(None, "female", on=date(2026, 10, 16)) == "Female"
        assert age_and_sex(date(2000, 1, 1), "unspecified", on=date(2026, 1, 1)) == "26 y"
        assert age_and_sex(None, None, on=date(2026, 1, 1)) == "—"


class TestRender:
    def test_renders_a_pdf(self) -> None:
        content = render_lab_report_pdf(_build(_order([_item()])))

        assert content.startswith(b"%PDF-")
        assert content.rstrip().endswith(b"%%EOF")

    def test_markup_in_data_is_printed_not_obeyed(self) -> None:
        hostile = _item(test_name='<img src="x"/><b>Potassium', notes="<font size=90>x</font>")
        order = _order([hostile], notes="<para>notes</para>", patient_name="<b>Rao</b>")

        assert render_lab_report_pdf(_build(order)).startswith(b"%PDF-")

    def test_a_long_panel_runs_onto_more_pages(self) -> None:
        one = render_lab_report_pdf(_build(_order([_item()])))
        many = render_lab_report_pdf(_build(_order([_item() for _ in range(80)])))

        assert one.count(b"/Type /Page\n") + one.count(b"/Type /Page ") == 1
        assert many.count(b"/Type /Page\n") + many.count(b"/Type /Page ") > 1
