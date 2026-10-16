"""Patient model, patient enums, and the per-hospital MRN counter.

The patient is the entity every clinical workflow revolves around
(``docs/modules/03-patient-management.md`` §1). Columns follow
``docs/05-DATABASE_DESIGN.md`` §2.7 exactly.

Two design points worth stating up front:

**No ``status`` column.** ``docs/05-DATABASE_DESIGN.md`` §2.7 defines no status
column, and business rule 4 of the module spec allows soft delete only. A
patient's lifecycle state is therefore *derived* from ``deleted_at``: see
:attr:`Patient.status`. "Deactivate" is a soft delete; "activate" clears
``deleted_at``. Adding a real column would duplicate that state and let the two
disagree.

**Medical history is structured JSON.** ``allergies``, ``chronic_conditions``,
and ``current_medications`` are JSONB arrays of typed objects, never free text
(module spec §4, rule 5). Their object shapes are enforced at the API boundary
by the Pydantic schemas in :mod:`app.schemas.patient`.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Mapped[uuid.UUID] resolution
from datetime import date, datetime  # noqa: TC003 — needed at runtime for Mapped[...] resolution
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CommonColumnsMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.hospital import Hospital


class Gender(StrEnum):
    """Patient gender — the ``gender_enum`` Postgres type.

    Values are fixed by ``docs/05-DATABASE_DESIGN.md`` §2.7. ``UNSPECIFIED``
    exists so that a refusal to answer is recorded as such, rather than being
    silently coerced into ``OTHER``.
    """

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNSPECIFIED = "unspecified"


class BloodGroup(StrEnum):
    """ABO/Rh blood group (module spec §11).

    Stored as ``VARCHAR(5)`` rather than a Postgres enum because
    ``docs/05-DATABASE_DESIGN.md`` §2.7 specifies ``VARCHAR(5)``; the closed
    value set is enforced at the API boundary.
    """

    A_POSITIVE = "A+"
    A_NEGATIVE = "A-"
    B_POSITIVE = "B+"
    B_NEGATIVE = "B-"
    AB_POSITIVE = "AB+"
    AB_NEGATIVE = "AB-"
    O_POSITIVE = "O+"
    O_NEGATIVE = "O-"


class PatientStatus(StrEnum):
    """Derived lifecycle state of a patient record.

    Not a stored column — computed from ``deleted_at`` by
    :attr:`Patient.status`. See the module docstring for why.
    """

    ACTIVE = "active"
    INACTIVE = "inactive"


class Patient(UUIDPrimaryKeyMixin, CommonColumnsMixin, Base):
    """A patient registered at a hospital.

    Every patient belongs to exactly one hospital and carries an MRN that is
    unique within that hospital. Patients are never hard-deleted (module spec
    §4, rule 4).
    """

    __tablename__ = "patients"

    __table_args__ = (
        UniqueConstraint("hospital_id", "mrn", name="uq_patients_hospital_mrn"),
        Index("ix_patients_phone", "phone"),
        Index("ix_patients_name", "hospital_id", "last_name", "first_name"),
        Index("ix_patients_dob", "hospital_id", "date_of_birth"),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="RESTRICT"),
        nullable=False,
        comment="UUID of the hospital (tenant) this patient belongs to.",
    )
    mrn: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="Medical Record Number. Unique per hospital, generated on registration.",
    )
    first_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Patient's given name."
    )
    last_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Patient's family name."
    )
    date_of_birth: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Date of birth. Required; never in the future.",
    )
    gender: Mapped[Gender] = mapped_column(
        SQLEnum(
            Gender,
            name="gender_enum",
            create_type=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        comment="Patient gender (male, female, other, unspecified).",
    )
    blood_group: Mapped[str | None] = mapped_column(
        String(5), nullable=True, comment="ABO/Rh blood group, e.g. 'B+'. NULL when unknown."
    )
    phone: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="Contact phone number in E.164 form."
    )
    email: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="Contact email address."
    )
    address: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Structured address (line1, line2, city, state, postal_code, country).",
    )
    emergency_contact: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, comment="Emergency contact object (name, phone, relation)."
    )
    marital_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="Marital status, free-form but bounded."
    )
    occupation: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Patient's occupation."
    )
    allergies: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="Array of allergy objects: {name, severity, reaction, noted_on}.",
    )
    chronic_conditions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="Array of condition objects: {name, since_year, notes}.",
    )
    current_medications: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="Array of medication objects: {name, dosage, frequency, started_on}.",
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Free-form administrative notes. Not clinical documentation."
    )

    # ── Relationships ───────────────────────────────────────────────────
    # `foreign_keys` is mandatory on every relationship touching a table that
    # the audit mixins also point at: created_by/updated_by/deleted_by are FKs
    # to users.id, so SQLAlchemy sees multiple join paths (see backend/CLAUDE.md).
    #
    # `lazy="raise"` on purpose. Nothing in this module needs the Hospital
    # object — services carry `hospital_id` directly — and eager-loading it
    # would cascade: Hospital.users is `lazy="selectin"`, so every patient read
    # would also pull every user in the hospital. That breaks the "patient list
    # p95 < 300ms at 100k patients" budget in the module spec §7. Raising makes
    # an accidental lazy load a loud error instead of a silent query storm.
    hospital: Mapped[Hospital] = relationship(
        "Hospital",
        foreign_keys="Patient.hospital_id",
        lazy="raise",
    )

    # Appointments, bills, and lab reports back-populate onto this model when
    # those modules land (module spec §15). They are not declared here: a
    # relationship to a model that does not exist yet fails mapper
    # configuration at import time.

    @property
    def full_name(self) -> str:
        """Full display name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def status(self) -> PatientStatus:
        """Lifecycle state derived from ``deleted_at``.

        ``ACTIVE`` while ``deleted_at`` is NULL; ``INACTIVE`` once the record
        has been soft-deleted (deactivated).
        """
        return PatientStatus.INACTIVE if self.deleted_at is not None else PatientStatus.ACTIVE

    def __repr__(self) -> str:
        return f"<Patient id={self.id!s:.8} mrn={self.mrn!r} hospital={self.hospital_id!s:.8}>"


class MrnSequence(Base):
    """Per-hospital counter and format template backing MRN generation.

    One row per hospital, keyed by ``hospital_id`` (module spec §8). The
    counter is advanced under ``SELECT ... FOR UPDATE`` inside the registration
    transaction, so two concurrent registrations in the same hospital cannot
    take the same sequence value.

    Deliberately has no audit or soft-delete columns: it is an internal counter,
    not a business record, and the module spec defines exactly these four
    columns.
    """

    __tablename__ = "mrn_sequences"

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="RESTRICT"),
        primary_key=True,
        comment="UUID of the hospital this counter belongs to.",
    )
    current_value: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment="Last issued sequence value. The next MRN uses current_value + 1.",
    )
    format_template: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="MRN-{year}-{seq:05d}",
        server_default="MRN-{year}-{seq:05d}",
        comment="MRN template for this hospital, e.g. 'MRN-{year}-{seq:05d}'.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp of the last counter advance (UTC).",
    )

    def __repr__(self) -> str:
        return f"<MrnSequence hospital={self.hospital_id!s:.8} current_value={self.current_value}>"
