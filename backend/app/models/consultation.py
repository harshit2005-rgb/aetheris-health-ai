"""Consultation (EMR) models (``docs/modules/16-consultation.md`` §8).

One :class:`Consultation` per appointment: the doctor's clinical note, with the
visit's vitals. Once finalized it is never edited; :class:`ConsultationAddendum`
rows are added instead (rule 6).
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Mapped[uuid.UUID] resolution
from datetime import date, datetime  # noqa: TC003 — needed at runtime for Mapped[...] resolution
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Text, text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CommonColumnsMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.doctor import Doctor
    from app.models.patient import Patient

__all__ = ["Consultation", "ConsultationAddendum", "ConsultationStatus"]


class ConsultationStatus(StrEnum):
    """Whether a note can still be edited — ``consultation_status``."""

    DRAFT = "draft"
    FINALIZED = "finalized"


def _fk(target: str, comment: str, *, nullable: bool = False, ondelete: str = "RESTRICT") -> Any:
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
        comment=comment,
    )


class Consultation(UUIDPrimaryKeyMixin, CommonColumnsMixin, Base):
    """The clinical note for one visit (FR-1 to FR-4)."""

    __tablename__ = "consultations"

    __table_args__ = (
        CheckConstraint(
            "(status = 'finalized') = (finalized_at IS NOT NULL)",
            name="ck_consultations_finalized_has_time",
        ),
        Index(
            "uq_consultations_hospital_appointment", "hospital_id", "appointment_id", unique=True
        ),
        Index("ix_consultations_hospital_patient", "hospital_id", "patient_id", "created_at"),
        Index("ix_consultations_hospital_doctor", "hospital_id", "doctor_id", "created_at"),
    )

    hospital_id: Mapped[uuid.UUID] = _fk("hospitals.id", "UUID of the owning hospital (tenant).")
    appointment_id: Mapped[uuid.UUID] = _fk("appointments.id", "The visit this note documents.")
    patient_id: Mapped[uuid.UUID] = _fk("patients.id", "Patient seen.")
    doctor_id: Mapped[uuid.UUID] = _fk("doctors.id", "Doctor who owns the note.")
    status: Mapped[ConsultationStatus] = mapped_column(
        SQLEnum(
            ConsultationStatus,
            name="consultation_status",
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=ConsultationStatus.DRAFT,
        server_default=text("'draft'"),
        comment="draft or finalized.",
    )
    chief_complaint: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Why the patient came."
    )
    history: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="History of the present illness, past history."
    )
    examination: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Examination findings."
    )
    diagnoses: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        comment="Array of {code, description}.",
    )
    plan: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Plan and advice.")
    follow_up_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="When the patient should come back."
    )
    vitals: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, comment="Vital signs recorded at the visit."
    )
    vitals_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="When the vitals were recorded (UTC)."
    )
    vitals_recorded_by: Mapped[uuid.UUID | None] = _fk(
        "users.id", "Who recorded the vitals.", nullable=True, ondelete="SET NULL"
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="When the note was finalized (UTC)."
    )
    finalized_by: Mapped[uuid.UUID | None] = _fk(
        "users.id", "Who finalized the note.", nullable=True, ondelete="SET NULL"
    )

    addenda: Mapped[list[ConsultationAddendum]] = relationship(
        "ConsultationAddendum",
        back_populates="consultation",
        order_by="ConsultationAddendum.added_at",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    patient: Mapped[Patient] = relationship(
        "Patient", foreign_keys="Consultation.patient_id", lazy="joined"
    )
    doctor: Mapped[Doctor] = relationship(
        "Doctor", foreign_keys="Consultation.doctor_id", lazy="joined"
    )
    appointment: Mapped[Appointment] = relationship(
        "Appointment", foreign_keys="Consultation.appointment_id", lazy="joined"
    )

    def __repr__(self) -> str:
        return f"<Consultation id={self.id!s:.8} status={self.status}>"


class ConsultationAddendum(UUIDPrimaryKeyMixin, CommonColumnsMixin, Base):
    """Something added to a finalized note, with its author and time (rule 6)."""

    __tablename__ = "consultation_addenda"

    __table_args__ = (
        Index("ix_consultation_addenda_consultation", "hospital_id", "consultation_id", "added_at"),
    )

    hospital_id: Mapped[uuid.UUID] = _fk("hospitals.id", "UUID of the owning hospital (tenant).")
    consultation_id: Mapped[uuid.UUID] = _fk(
        "consultations.id", "The note this adds to.", ondelete="CASCADE"
    )
    text: Mapped[str] = mapped_column(Text, nullable=False, comment="What is added.")
    added_by: Mapped[uuid.UUID] = _fk("users.id", "Who added it.")
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="When it was added (UTC)."
    )

    consultation: Mapped[Consultation] = relationship(
        "Consultation", back_populates="addenda", lazy="raise_on_sql"
    )
