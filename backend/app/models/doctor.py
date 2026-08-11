"""Doctor models — profile, weekly availability, and leave.

A doctor is a :class:`~app.models.user.User` plus a clinical profile
(``docs/modules/04-doctor-management.md`` §4, rule 1). Columns follow
``docs/05-DATABASE_DESIGN.md`` §2.8–2.10, with two documented additions
explained in migration ``0006``: ``hospital_id`` on the child tables, and
``department_id`` on :class:`Doctor`.

**Slots are not modelled here.** Business rule 5 makes slot generation a read
model, recomputed on demand and never stored. :class:`SlotStatus` describes
what a computed slot can be; the computation itself lives in
:mod:`app.services.doctor_service`.

**``day_of_week`` is 0=Monday .. 6=Sunday** (``docs/05-DATABASE_DESIGN.md``
§2.9), deliberately the same numbering as :meth:`datetime.date.weekday` so slot
generation needs no translation table. The ``hospital_working_hours`` table
sketched in ``docs/modules/14-hospital-settings.md`` §8 previously specified
0=Sunday; that spec has been reconciled to 0=Monday, so the platform now has a
single weekday convention.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Mapped[uuid.UUID] resolution
from datetime import datetime, time  # noqa: TC003 — needed at runtime for Mapped[...] resolution
from decimal import Decimal  # noqa: TC003 — needed at runtime for Mapped[Decimal] resolution
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CommonColumnsMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.hospital import Hospital
    from app.models.user import User

__all__ = [
    "SLOT_DURATION_CHOICES",
    "Doctor",
    "DoctorAvailability",
    "DoctorLeave",
    "DoctorStatus",
    "SlotStatus",
]

#: Slot durations the scheduler supports (module spec §11). Mirrors the
#: ``ck_doctor_availability_slot_duration`` constraint in migration 0006.
SLOT_DURATION_CHOICES: tuple[int, ...] = (10, 15, 20, 30, 45, 60)


class DoctorStatus(StrEnum):
    """Derived lifecycle state of a doctor.

    Not a stored column — computed from ``deleted_at``, the same choice
    :class:`~app.models.patient.Patient` and
    :class:`~app.models.department.Department` make.
    """

    ACTIVE = "active"
    INACTIVE = "inactive"


class SlotStatus(StrEnum):
    """State of a computed slot (module spec §9).

    Never stored. Slot generation returns these; the database has no column and
    no enum type for them, because a stored slot would go stale the moment an
    appointment moved.
    """

    AVAILABLE = "available"
    BOOKED = "booked"
    ON_LEAVE = "on_leave"


class Doctor(UUIDPrimaryKeyMixin, CommonColumnsMixin, Base):
    """A doctor's clinical profile, attached to exactly one user.

    Doctors are never hard-deleted: appointments, consultations, and invoices
    reference them. Deactivation is a soft delete, and is refused while future
    appointments exist (module spec §4, rule 7 and FR-5).
    """

    __tablename__ = "doctors"

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_doctors_user_id"),
        Index("ix_doctors_hospital_specialization", "hospital_id", "specialization"),
        Index("ix_doctors_department", "department_id"),
        Index(
            "ix_doctors_hospital_active",
            "hospital_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="UUID of the user account backing this doctor. Unique — one doctor row per user.",
    )
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="RESTRICT"),
        nullable=False,
        comment="UUID of the hospital (tenant) this doctor belongs to.",
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Department the doctor is assigned to. NULL until assigned.",
    )
    specialization: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Clinical specialization, e.g. 'Cardiology'."
    )
    qualifications: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="Array of qualification objects: {degree, institution, year}.",
    )
    license_number: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Medical council licence number."
    )
    consultation_fee: Mapped[Decimal] = mapped_column(
        # NUMERIC(15,2), never float (CLAUDE.md rule 6). Currency is inherited
        # from hospital settings (module spec §4, rule 6), so no currency column.
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0"),
        comment="Consultation fee in the hospital's configured currency.",
    )
    bio: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Free-form professional biography for patient-facing display."
    )
    languages: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="Array of language names the doctor consults in.",
    )

    # ── Relationships ───────────────────────────────────────────────────
    # `foreign_keys` is mandatory everywhere: the audit mixins add
    # created_by/updated_by/deleted_by FKs to users.id, so `user` alone has four
    # candidate join paths and SQLAlchemy raises at mapper configuration time
    # (backend/CLAUDE.md, "Common Pitfalls").
    #
    # `user` is `lazy="joined"` because essentially every doctor read needs the
    # name and email to display — a separate query per doctor would be an N+1 on
    # the list endpoint.
    user: Mapped[User] = relationship(
        "User",
        foreign_keys="Doctor.user_id",
        lazy="joined",
    )
    # `department` is `lazy="joined"` for the same reason: the list endpoint
    # shows it, and it is a single small row.
    department: Mapped[Department | None] = relationship(
        "Department",
        foreign_keys="Doctor.department_id",
        back_populates="doctors",
        lazy="joined",
    )
    # `lazy="raise"` — services carry `hospital_id` directly, and Hospital.users
    # is `lazy="selectin"`, so eager-loading the hospital would pull every user
    # in it on every doctor read.
    hospital: Mapped[Hospital] = relationship(
        "Hospital",
        foreign_keys="Doctor.hospital_id",
        lazy="raise",
    )
    availability: Mapped[list[DoctorAvailability]] = relationship(
        "DoctorAvailability",
        foreign_keys="DoctorAvailability.doctor_id",
        back_populates="doctor",
        # Replaced wholesale on every PUT, so the ORM must forget deleted rows.
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    leaves: Mapped[list[DoctorLeave]] = relationship(
        "DoctorLeave",
        foreign_keys="DoctorLeave.doctor_id",
        back_populates="doctor",
        # `lazy="raise"`: leaves are queried by date range, never as a whole
        # collection, and a doctor can accumulate years of them.
        lazy="raise",
    )

    @property
    def status(self) -> DoctorStatus:
        """Lifecycle state derived from ``deleted_at``."""
        return DoctorStatus.INACTIVE if self.deleted_at is not None else DoctorStatus.ACTIVE

    def __repr__(self) -> str:
        return f"<Doctor id={self.id!s:.8} user={self.user_id!s:.8} spec={self.specialization!r}>"


class DoctorAvailability(UUIDPrimaryKeyMixin, CommonColumnsMixin, Base):
    """One recurring weekly window in which a doctor sees patients.

    A doctor's schedule is the set of these rows. They are replaced atomically
    on every update (module spec §5.2) rather than patched, because partial
    edits to a weekly grid are ambiguous.
    """

    __tablename__ = "doctor_availability"

    __table_args__ = (
        # Bare suffixes: the naming convention is
        # ``ck_%(table_name)s_%(constraint_name)s`` and expands these to match
        # migration 0006.
        CheckConstraint("end_time > start_time", name="time_order"),
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="day_of_week_range"),
        CheckConstraint(
            f"slot_duration_minutes IN ({', '.join(str(d) for d in SLOT_DURATION_CHOICES)})",
            name="slot_duration",
        ),
        Index("ix_doctor_avail_doctor_day", "doctor_id", "day_of_week"),
    )

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        comment="Doctor this availability window belongs to.",
    )
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Owning tenant, carried so the row is directly tenant-filterable.",
    )
    day_of_week: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        comment="0=Monday .. 6=Sunday, matching datetime.date.weekday().",
    )
    start_time: Mapped[time] = mapped_column(
        Time, nullable=False, comment="Window start as wall-clock time in the hospital's timezone."
    )
    end_time: Mapped[time] = mapped_column(
        Time, nullable=False, comment="Window end as wall-clock time in the hospital's timezone."
    )
    slot_duration_minutes: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=15,
        server_default=text("15"),
        comment="Length of each generated slot within this window.",
    )

    doctor: Mapped[Doctor] = relationship(
        "Doctor",
        foreign_keys="DoctorAvailability.doctor_id",
        back_populates="availability",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return (
            f"<DoctorAvailability doctor={self.doctor_id!s:.8} "
            f"day={self.day_of_week} {self.start_time}-{self.end_time}>"
        )


class DoctorLeave(UUIDPrimaryKeyMixin, CommonColumnsMixin, Base):
    """A time-off interval that removes slots from a doctor's schedule.

    Stored in UTC (CLAUDE.md rule 7). Auto-approved in MVP (module spec §5.3);
    the approval workflow arrives in v2.1 and will add a status column then.
    """

    __tablename__ = "doctor_leaves"

    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="range_order"),
        Index("ix_doctor_leaves_doctor_range", "doctor_id", "starts_at", "ends_at"),
        Index(
            "ix_doctor_leaves_hospital_active",
            "hospital_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Doctor taking the leave.",
    )
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Owning tenant, carried so the row is directly tenant-filterable.",
    )
    starts_at: Mapped[datetime] = mapped_column(
        # TIMESTAMPTZ in UTC. Leaves are absolute instants, unlike availability,
        # which is wall-clock and resolves against the hospital timezone.
        DateTime(timezone=True),
        nullable=False,
        comment="Inclusive start of the leave (UTC).",
    )
    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Exclusive end of the leave (UTC).",
    )
    reason: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="Free-text reason for the leave."
    )

    doctor: Mapped[Doctor] = relationship(
        "Doctor",
        foreign_keys="DoctorLeave.doctor_id",
        back_populates="leaves",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<DoctorLeave doctor={self.doctor_id!s:.8} {self.starts_at}..{self.ends_at}>"
