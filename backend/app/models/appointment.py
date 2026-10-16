"""Appointment models — the schedule the clinic runs on.

An appointment is the meeting between a patient and a doctor, and the container
a later Consultation and Billing invoice hang off
(``docs/modules/05-appointment-management.md`` §1, §15). Columns follow
``docs/05-DATABASE_DESIGN.md`` §2.11–2.12.

**Status is a stored column here, unlike Patient and Doctor.** Those derive
their lifecycle from ``deleted_at`` because they only have two states. An
appointment has six, moves between them under a state machine (§5.1), and every
move is recorded — so the current status has to be a real column that
:class:`AppointmentStatusHistory` rows point at.

**Double-booking is not prevented in Python.** The ``no_overlap_per_doctor``
exclusion constraint from migration 0008 does it in Postgres. Two receptionists
booking the same slot is a race no application check can close, because both
transactions read before either writes (§14).
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Mapped[uuid.UUID] resolution
from datetime import datetime  # noqa: TC003 — needed at runtime for Mapped[...] resolution
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CommonColumnsMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.doctor import Doctor
    from app.models.hospital import Hospital
    from app.models.patient import Patient

__all__ = [
    "TERMINAL_STATUSES",
    "Appointment",
    "AppointmentStatus",
    "AppointmentStatusHistory",
    "AppointmentType",
]


class AppointmentStatus(StrEnum):
    """Lifecycle state of an appointment (module spec §5.1).

    Values are fixed by ``docs/05-DATABASE_DESIGN.md`` §2.11 and backed by the
    ``appointment_status`` Postgres enum.
    """

    BOOKED = "booked"
    CHECKED_IN = "checked_in"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class AppointmentType(StrEnum):
    """Why the appointment exists — the ``appointment_type`` Postgres enum."""

    NEW = "new"
    FOLLOW_UP = "follow_up"
    WALK_IN = "walk_in"
    EMERGENCY = "emergency"


#: States an appointment can never leave. Business rule 5: a cancelled
#: appointment is not reactivated, a new one is booked instead. ``no_show`` is
#: terminal for the same reason — the visit did not happen and cannot
#: retroactively start.
TERMINAL_STATUSES: frozenset[AppointmentStatus] = frozenset(
    {
        AppointmentStatus.COMPLETED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    }
)

#: Statuses that release the doctor's time. Mirrors the ``WHERE`` clause of the
#: ``no_overlap_per_doctor`` exclusion constraint in migration 0008 — an
#: appointment in one of these no longer blocks its slot.
SLOT_FREEING_STATUSES: frozenset[AppointmentStatus] = frozenset(
    {AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW}
)


def _status_enum() -> SQLEnum:
    """Return the shared ``appointment_status`` column type.

    ``create_type=False`` because migration 0008 owns creating the Postgres
    type; declaring it again here would try to create it a second time when the
    two tables are emitted.
    """
    return SQLEnum(
        AppointmentStatus,
        name="appointment_status",
        create_type=False,
        values_callable=lambda e: [m.value for m in e],
    )


class Appointment(UUIDPrimaryKeyMixin, CommonColumnsMixin, Base):
    """A scheduled meeting between a patient and a doctor."""

    __tablename__ = "appointments"

    __table_args__ = (
        CheckConstraint("scheduled_end > scheduled_start", name="time_order"),
        Index(
            "uq_appointments_hospital_idempotency_key",
            "hospital_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("ix_appointments_hospital_scheduled_start", "hospital_id", "scheduled_start"),
        Index("ix_appointments_doctor_scheduled_start", "doctor_id", "scheduled_start"),
        Index(
            "ix_appointments_patient_scheduled_start",
            "patient_id",
            text("scheduled_start DESC"),
        ),
        Index("ix_appointments_status", "hospital_id", "status"),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="RESTRICT"),
        nullable=False,
        comment="UUID of the hospital (tenant) this appointment belongs to.",
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Patient being seen.",
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Doctor seeing the patient.",
    )
    scheduled_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Appointment start (UTC)."
    )
    scheduled_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Appointment end (UTC), exclusive."
    )
    status: Mapped[AppointmentStatus] = mapped_column(
        _status_enum(),
        nullable=False,
        default=AppointmentStatus.BOOKED,
        comment="Current lifecycle state. Moves only along the state machine.",
    )
    type: Mapped[AppointmentType] = mapped_column(
        SQLEnum(
            AppointmentType,
            name="appointment_type",
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        comment="new, follow_up, walk_in, or emergency.",
    )
    reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Why the patient is being seen, as given at booking."
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Reception notes captured at booking."
    )
    cancelled_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Why the appointment was cancelled. Required on cancel."
    )
    checked_in_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="When the patient arrived (UTC)."
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="When the consultation began (UTC)."
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="When the consultation finished (UTC)."
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Client-supplied key making booking retries safe (business rule 8).",
    )

    # ── Relationships ───────────────────────────────────────────────────
    # `foreign_keys` everywhere: the audit mixins add created_by/updated_by/
    # deleted_by FKs to users.id, so several of these have more than one
    # candidate join path (backend/CLAUDE.md, "Common Pitfalls").
    #
    # patient and doctor are `lazy="joined"` — every schedule view shows both
    # names, so a separate query each would be an N+1 on the day's list.
    patient: Mapped[Patient] = relationship(
        "Patient", foreign_keys="Appointment.patient_id", lazy="joined"
    )
    doctor: Mapped[Doctor] = relationship(
        "Doctor", foreign_keys="Appointment.doctor_id", lazy="joined"
    )
    hospital: Mapped[Hospital] = relationship(
        "Hospital", foreign_keys="Appointment.hospital_id", lazy="raise"
    )
    # History is read only on the dedicated endpoint, and grows with every
    # transition, so it is never loaded implicitly.
    status_history: Mapped[list[AppointmentStatusHistory]] = relationship(
        "AppointmentStatusHistory",
        foreign_keys="AppointmentStatusHistory.appointment_id",
        back_populates="appointment",
        lazy="raise",
        order_by="AppointmentStatusHistory.changed_at",
    )

    @property
    def is_terminal(self) -> bool:
        """Whether the appointment can still change state.

        Used by the service before attempting a transition, and by the no-show
        sweeper to skip appointments that already resolved.
        """
        return self.status in TERMINAL_STATUSES

    @property
    def occupies_slot(self) -> bool:
        """Whether this appointment still holds the doctor's time.

        Matches the exclusion constraint's ``WHERE`` clause, so Python and
        Postgres agree on what "booked" means for a slot.
        """
        return self.deleted_at is None and self.status not in SLOT_FREEING_STATUSES

    def __repr__(self) -> str:
        return (
            f"<Appointment id={self.id!s:.8} doctor={self.doctor_id!s:.8} "
            f"{self.scheduled_start} status={self.status}>"
        )


class AppointmentStatusHistory(UUIDPrimaryKeyMixin, Base):
    """One recorded transition in an appointment's lifecycle.

    Immutable and append-only (``docs/05-DATABASE_DESIGN.md`` §2.12), which is
    why this model has neither :class:`~app.models.base.TimestampMixin` nor
    soft-delete columns: there is nothing to update and nothing to retract.
    Business rule 7 and AC-6 require one row per status change.
    """

    __tablename__ = "appointment_status_history"

    __table_args__ = (Index("ix_appt_status_history_appointment", "appointment_id", "changed_at"),)

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        comment="Appointment whose status changed.",
    )
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Owning tenant, carried so history is directly tenant-filterable.",
    )
    from_status: Mapped[AppointmentStatus | None] = mapped_column(
        _status_enum(),
        nullable=True,
        comment="Previous status. NULL on the first row — booking comes from nothing.",
    )
    to_status: Mapped[AppointmentStatus] = mapped_column(
        _status_enum(), nullable=False, comment="Status after the change."
    )
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Acting user. NULL means the system acted — e.g. the no-show sweeper.",
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        comment="When the change happened (UTC).",
    )
    reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Why the change happened, e.g. 'reschedule' or a cancellation."
    )

    appointment: Mapped[Appointment] = relationship(
        "Appointment",
        foreign_keys="AppointmentStatusHistory.appointment_id",
        back_populates="status_history",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return (
            f"<AppointmentStatusHistory appointment={self.appointment_id!s:.8} "
            f"{self.from_status}->{self.to_status}>"
        )
