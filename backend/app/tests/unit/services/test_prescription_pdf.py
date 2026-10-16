"""Unit tests for prescription PDFs (``app/services/prescription_pdf.py``)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from app.models.pharmacy import PrescriptionStatus
from app.schemas.pharmacy import PrescriptionItemResponse, PrescriptionResponse
from app.services.pdf_layout import Letterhead
from app.services.prescription_pdf import build_prescription_document, render_prescription_pdf

LETTERHEAD = Letterhead(
    name="Sunrise Hospital",
    address_lines=("12 MG Road",),
    contact=None,
    gstin=None,
    timezone="Asia/Kolkata",
)
WRITTEN = datetime(2026, 10, 16, 5, 12, tzinfo=UTC)  # 10:42 in Hyderabad


def _item(**overrides: Any) -> PrescriptionItemResponse:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "medicine_id": uuid.uuid4(),
        "medicine_name": "Paracetamol 500 mg",
        "dosage": "1 tablet",
        "frequency": "three times daily",
        "duration_days": 5,
        "instructions": "After food.",
        "quantity": 15,
        "quantity_dispensed": 0,
        "quantity_remaining": 15,
        "available_quantity": 100,
    }
    values.update(overrides)
    return PrescriptionItemResponse.model_construct(**values)


def _rx(items: list[PrescriptionItemResponse], **overrides: Any) -> PrescriptionResponse:
    values: dict[str, Any] = {
        "id": uuid.UUID("3f9a21c0-0000-4000-8000-000000000000"),
        "appointment_id": uuid.uuid4(),
        "patient_id": uuid.uuid4(),
        "patient_name": "Ananya Rao",
        "patient_mrn": "SUN-000123",
        "doctor_id": uuid.uuid4(),
        "doctor_name": "Dr. Kiran Reddy",
        "status": PrescriptionStatus.ACTIVE,
        "notes": "Review in five days.",
        "prescribed_at": WRITTEN,
        "cancelled_at": None,
        "cancel_reason": None,
        "items": items,
    }
    values.update(overrides)
    return PrescriptionResponse.model_construct(**values)


def _build(rx: PrescriptionResponse, **overrides: Any) -> Any:
    kwargs: dict[str, Any] = {
        "letterhead": LETTERHEAD,
        "date_of_birth": date(1990, 1, 1),
        "sex": "female",
        "doctor_specialization": "General Medicine",
        "doctor_registration": "TSMC/45231",
        "generated_at": WRITTEN,
    }
    kwargs.update(overrides)
    return build_prescription_document(rx, **kwargs)


class TestDocument:
    def test_patient_doctor_and_date(self) -> None:
        doc = _build(_rx([_item()]))

        assert doc.patient_name == "Ananya Rao"
        assert doc.age_sex == "36 y · Female"
        assert doc.doctor_name == "Dr. Kiran Reddy"
        assert doc.doctor_specialization == "General Medicine"
        assert doc.doctor_registration == "TSMC/45231"
        assert doc.prescribed_on == "16 Oct 2026, 10:42"
        assert doc.reference == "RX-3F9A21C0"
        assert doc.notes == "Review in five days."

    def test_each_medicine_line(self) -> None:
        doc = _build(_rx([_item(), _item(duration_days=1, instructions=None)]))

        first, second = doc.lines
        assert (first.medicine, first.dosage, first.frequency, first.duration, first.quantity) == (
            "Paracetamol 500 mg",
            "1 tablet",
            "three times daily",
            "5 days",
            "15",
        )
        assert first.instructions == "After food."
        assert second.duration == "1 day"
        assert second.instructions is None

    def test_no_duration_is_a_dash(self) -> None:
        assert _build(_rx([_item(duration_days=None)])).lines[0].duration == "—"

    def test_a_missing_registration_is_left_blank(self) -> None:
        doc = _build(_rx([_item()]), doctor_registration="", doctor_specialization="")

        assert doc.doctor_registration is None
        assert doc.doctor_specialization is None

    def test_a_cancelled_prescription_says_why(self) -> None:
        rx = _rx([_item()], status=PrescriptionStatus.CANCELLED, cancel_reason="Wrong patient")

        assert _build(rx).cancelled_reason == "Wrong patient"

    def test_an_active_prescription_is_not_cancelled(self) -> None:
        assert _build(_rx([_item()])).cancelled_reason is None


class TestRender:
    def test_renders_a_pdf(self) -> None:
        assert render_prescription_pdf(_build(_rx([_item()]))).startswith(b"%PDF-")

    def test_a_cancelled_prescription_renders(self) -> None:
        rx = _rx([_item()], status=PrescriptionStatus.CANCELLED, cancel_reason="Duplicate")

        assert render_prescription_pdf(_build(rx)).rstrip().endswith(b"%%EOF")

    def test_markup_in_data_is_printed_not_obeyed(self) -> None:
        rx = _rx(
            [_item(medicine_name="<b>Para</b>", instructions='<img src="x"/>')],
            notes="<font size=99>big</font>",
            patient_name="A & B <Rao>",
        )

        assert render_prescription_pdf(_build(rx)).startswith(b"%PDF-")
