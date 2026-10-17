"""Consultation (EMR) DTOs (``docs/modules/16-consultation.md`` §9, §11).

Request models validate shape and ranges; the service enforces the rules that
need the database (ownership, status, the appointment's state).
"""

from __future__ import annotations

# NOTE: runtime imports, not TYPE_CHECKING — Pydantic resolves field
# annotations at class creation.
from datetime import date, datetime  # noqa: TC003
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Annotated, Any, Self
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.consultation import ConsultationStatus  # noqa: TC001

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.models.consultation import Consultation, ConsultationAddendum
    from app.models.lab import LabOrder
    from app.models.pharmacy import Prescription

__all__ = [
    "AddAddendumRequest",
    "ConsultationAddendumResponse",
    "ConsultationLabOrderSummary",
    "ConsultationPrescriptionSummary",
    "ConsultationResponse",
    "ConsultationSummary",
    "CreateConsultationRequest",
    "Diagnosis",
    "RecordVitalsRequest",
    "UpdateConsultationRequest",
    "Vitals",
]

Section = Annotated[str, StringConstraints(strip_whitespace=True, max_length=10_000)]


class Diagnosis(BaseModel):
    """One diagnosis: a description, with an optional code (ICD-10 when known)."""

    model_config = ConfigDict(extra="forbid")

    code: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = Field(
        default=None, description="Optional diagnosis code, e.g. an ICD-10 code."
    )
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ] = Field(description="The diagnosis in words.")


class Vitals(BaseModel):
    """Vital signs. Every field optional; at least one is required (§11)."""

    model_config = ConfigDict(extra="forbid")

    bp_systolic: int | None = Field(default=None, ge=50, le=300, description="mmHg.")
    bp_diastolic: int | None = Field(default=None, ge=20, le=200, description="mmHg.")
    pulse: int | None = Field(default=None, ge=20, le=250, description="Beats per minute.")
    temperature_c: Decimal | None = Field(
        default=None, ge=30, le=45, max_digits=4, decimal_places=1, description="°C."
    )
    spo2: int | None = Field(default=None, ge=50, le=100, description="Oxygen saturation, %.")
    respiratory_rate: int | None = Field(default=None, ge=4, le=80, description="Breaths/min.")
    weight_kg: Decimal | None = Field(
        default=None, ge=Decimal("0.5"), le=400, max_digits=5, decimal_places=1, description="kg."
    )
    height_cm: Decimal | None = Field(
        default=None, ge=30, le=250, max_digits=4, decimal_places=1, description="cm."
    )

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if all(value is None for value in self.model_dump().values()):
            msg = "Record at least one vital sign."
            raise ValueError(msg)
        if (self.bp_systolic is None) != (self.bp_diastolic is None):
            msg = "Blood pressure needs both systolic and diastolic."
            raise ValueError(msg)
        if (
            self.bp_systolic is not None
            and self.bp_diastolic is not None
            and self.bp_diastolic >= self.bp_systolic
        ):
            msg = "Diastolic pressure must be lower than systolic."
            raise ValueError(msg)
        return self

    def to_json(self) -> dict[str, Any]:
        """The vitals as stored: numbers as strings for decimals, nulls dropped."""
        return {
            key: (str(value) if isinstance(value, Decimal) else value)
            for key, value in self.model_dump().items()
            if value is not None
        }


def bmi(vitals: dict[str, Any] | None) -> Decimal | None:
    """Body-mass index from stored vitals, to one decimal, or ``None``."""
    if not vitals or vitals.get("weight_kg") is None or vitals.get("height_cm") is None:
        return None
    metres = Decimal(str(vitals["height_cm"])) / 100
    if metres <= 0:
        return None
    value = Decimal(str(vitals["weight_kg"])) / (metres * metres)
    return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


class _ClinicalSections(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chief_complaint: Section | None = Field(default=None, description="Why the patient came.")
    history: Section | None = Field(default=None, description="History of present illness.")
    examination: Section | None = Field(default=None, description="Examination findings.")
    diagnoses: list[Diagnosis] | None = Field(
        default=None, max_length=20, description="Diagnoses, most important first."
    )
    plan: Section | None = Field(default=None, description="Plan and advice.")
    follow_up_date: date | None = Field(default=None, description="When to come back.")


class CreateConsultationRequest(_ClinicalSections):
    """Start the note for a visit (``POST /consultations``)."""

    appointment_id: UUID = Field(description="The visit to document.")
    vitals: Vitals | None = Field(default=None, description="Vitals, if already taken.")


class UpdateConsultationRequest(_ClinicalSections):
    """Change clinical sections of a draft. Fields left out are unchanged."""

    @model_validator(mode="after")
    def _something(self) -> Self:
        if not self.model_fields_set:
            msg = "Send at least one field to change."
            raise ValueError(msg)
        return self


class RecordVitalsRequest(BaseModel):
    """Record (replace) the visit's vitals."""

    model_config = ConfigDict(extra="forbid")

    vitals: Vitals = Field(description="The vital signs.")


class AddAddendumRequest(BaseModel):
    """Add to a finalized note."""

    model_config = ConfigDict(extra="forbid")

    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
    ] = Field(description="What to add.")


# ── Responses ────────────────────────────────────────────────────────────────


class ConsultationAddendumResponse(BaseModel):
    """One addendum."""

    id: UUID = Field(description="Addendum UUID.")
    text: str = Field(description="What was added.")
    added_by: UUID = Field(description="Who added it.")
    added_at: datetime = Field(description="When it was added (UTC).")

    @classmethod
    def from_model(cls, addendum: ConsultationAddendum) -> Self:
        """Build the DTO from the ORM row."""
        return cls(
            id=addendum.id,
            text=addendum.text,
            added_by=addendum.added_by,
            added_at=addendum.added_at,
        )


class ConsultationPrescriptionLine(BaseModel):
    """One medicine on a visit's prescription."""

    medicine_name: str
    dosage: str
    frequency: str
    duration_days: int | None
    quantity: int


class ConsultationPrescriptionSummary(BaseModel):
    """A prescription written in the visit, as the note shows it."""

    id: UUID = Field(description="Prescription UUID.")
    status: str = Field(description="Its dispensing status.")
    prescribed_at: datetime = Field(description="When it was written (UTC).")
    items: list[ConsultationPrescriptionLine] = Field(description="The medicines.")

    @classmethod
    def from_model(cls, prescription: Prescription) -> Self:
        """Build the summary from the ORM row."""
        return cls(
            id=prescription.id,
            status=str(prescription.status.value),
            prescribed_at=prescription.prescribed_at,
            items=[
                ConsultationPrescriptionLine(
                    medicine_name=item.medicine_name,
                    dosage=item.dosage,
                    frequency=item.frequency,
                    duration_days=item.duration_days,
                    quantity=item.quantity,
                )
                for item in prescription.items
            ],
        )


class ConsultationLabOrderSummary(BaseModel):
    """A lab order raised in the visit, as the note shows it."""

    id: UUID = Field(description="Lab order UUID.")
    status: str = Field(description="Its lifecycle status.")
    priority: str = Field(description="routine, urgent or stat.")
    ordered_at: datetime = Field(description="When it was ordered (UTC).")
    tests: list[str] = Field(description="Names of the tests ordered.")
    has_abnormal: bool = Field(description="Whether any released result is abnormal.")

    @classmethod
    def from_model(cls, order: LabOrder) -> Self:
        """Build the summary from the ORM row."""
        from app.models.lab import LabResultFlag  # noqa: PLC0415 — keep the import local

        return cls(
            id=order.id,
            status=str(order.status.value),
            priority=str(order.priority.value),
            ordered_at=order.ordered_at,
            tests=[item.test_name for item in order.items],
            has_abnormal=any(
                item.result_flag not in (None, LabResultFlag.NORMAL) for item in order.items
            ),
        )


class ConsultationSummary(BaseModel):
    """A consultation in a list (patient history, doctor's notes)."""

    id: UUID = Field(description="Consultation UUID.")
    appointment_id: UUID = Field(description="The visit.")
    patient_id: UUID = Field(description="Patient UUID.")
    patient_name: str = Field(description="Patient's full name.")
    patient_mrn: str = Field(description="Patient's medical record number.")
    doctor_id: UUID = Field(description="Doctor UUID.")
    doctor_name: str = Field(description="Doctor's name.")
    status: ConsultationStatus = Field(description="draft or finalized.")
    visit_at: datetime = Field(description="When the visit was scheduled (UTC).")
    chief_complaint: str | None = Field(description="Why the patient came.")
    diagnoses: list[Diagnosis] = Field(description="Diagnoses.")
    finalized_at: datetime | None = Field(description="When it was finalized (UTC).")
    created_at: datetime = Field(description="When the note was started (UTC).")
    updated_at: datetime = Field(description="When it last changed (UTC).")

    @classmethod
    def _base(cls, consultation: Consultation) -> dict[str, Any]:
        doctor_user = consultation.doctor.user
        return {
            "id": consultation.id,
            "appointment_id": consultation.appointment_id,
            "patient_id": consultation.patient_id,
            "patient_name": consultation.patient.full_name,
            "patient_mrn": consultation.patient.mrn,
            "doctor_id": consultation.doctor_id,
            "doctor_name": f"Dr. {doctor_user.first_name} {doctor_user.last_name}",
            "status": consultation.status,
            "visit_at": consultation.appointment.scheduled_start,
            "chief_complaint": consultation.chief_complaint,
            "diagnoses": [Diagnosis.model_validate(d) for d in consultation.diagnoses or []],
            "finalized_at": consultation.finalized_at,
            "created_at": consultation.created_at,
            "updated_at": consultation.updated_at,
        }

    @classmethod
    def from_model(cls, consultation: Consultation) -> Self:
        """Build the summary from the ORM row."""
        return cls(**cls._base(consultation))


class ConsultationResponse(ConsultationSummary):
    """One consultation in full (``GET /consultations/{id}``)."""

    history: str | None = Field(description="History of present illness.")
    examination: str | None = Field(description="Examination findings.")
    plan: str | None = Field(description="Plan and advice.")
    follow_up_date: date | None = Field(description="When to come back.")
    vitals: dict[str, Any] | None = Field(description="Vital signs, as recorded.")
    bmi: Decimal | None = Field(description="Body-mass index from weight and height.")
    vitals_recorded_at: datetime | None = Field(description="When vitals were recorded (UTC).")
    vitals_recorded_by: UUID | None = Field(description="Who recorded the vitals.")
    finalized_by: UUID | None = Field(description="Who finalized the note.")
    is_own: bool = Field(description="Whether the caller is this note's doctor.")
    addenda: list[ConsultationAddendumResponse] = Field(description="Additions, oldest first.")
    prescriptions: list[ConsultationPrescriptionSummary] = Field(
        description="Prescriptions written in this visit."
    )
    lab_orders: list[ConsultationLabOrderSummary] = Field(
        description="Lab orders raised in this visit."
    )

    @classmethod
    def build(
        cls,
        consultation: Consultation,
        *,
        is_own: bool,
        prescriptions: Sequence[Prescription] = (),
        lab_orders: Sequence[LabOrder] = (),
    ) -> Self:
        """Build the full DTO from the ORM row and the visit's orders."""
        return cls(
            **cls._base(consultation),
            history=consultation.history,
            examination=consultation.examination,
            plan=consultation.plan,
            follow_up_date=consultation.follow_up_date,
            vitals=consultation.vitals,
            bmi=bmi(consultation.vitals),
            vitals_recorded_at=consultation.vitals_recorded_at,
            vitals_recorded_by=consultation.vitals_recorded_by,
            finalized_by=consultation.finalized_by,
            is_own=is_own,
            addenda=[ConsultationAddendumResponse.from_model(a) for a in consultation.addenda],
            prescriptions=[ConsultationPrescriptionSummary.from_model(p) for p in prescriptions],
            lab_orders=[ConsultationLabOrderSummary.from_model(o) for o in lab_orders],
        )
