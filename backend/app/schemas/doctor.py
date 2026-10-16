"""Pydantic DTOs for the Doctor Management module.

Request models enforce every rule in ``docs/modules/04-doctor-management.md``
§11 before a service sees the payload (``docs/07-SECURITY.md``, rule 5).
Response models are the only doctor shapes that cross the API boundary —
SQLAlchemy models never do (``docs/03-ARCHITECTURE.md`` §15, rule 7).

The availability payload is validated as a *set*, not just row by row: overlap
detection is a property of the whole day's entries, so it lives on
:class:`SetAvailabilityRequest` rather than on the individual entry.
"""

from __future__ import annotations

# Aliased: ``DaySlotsResponse`` has a field literally named ``date`` (module
# spec §9 fixes the response key), which would otherwise shadow the type it is
# annotated with and leave Pydantic unable to resolve the annotation.
from datetime import date as DateType  # noqa: TC003, N812

# NOTE: these must be runtime imports, not TYPE_CHECKING. Pydantic resolves
# field annotations against the module's real globals when it builds each
# model (backend/CLAUDE.md, "Common Pitfalls").
from datetime import datetime, time  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import TYPE_CHECKING, Annotated, Any, Self
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.doctor import SLOT_DURATION_CHOICES, DoctorStatus, SlotStatus
from app.schemas.common import Page

if TYPE_CHECKING:
    from app.models.doctor import Doctor, DoctorAvailability, DoctorLeave

__all__ = [
    "MAX_CONSULTATION_FEE",
    "AvailabilityEntry",
    "AvailabilityResponse",
    "CreateDoctorRequest",
    "CreateLeaveRequest",
    "DaySlotsResponse",
    "DoctorListResponse",
    "DoctorResponse",
    "DoctorStatus",
    "DoctorSummaryResponse",
    "LeaveResponse",
    "Qualification",
    "SetAvailabilityRequest",
    "SlotResponse",
    "SlotStatus",
    "UpdateDoctorRequest",
]

#: Upper bound on a consultation fee (module spec §11). A larger number is a
#: data-entry error — a misplaced decimal point — not a real fee.
MAX_CONSULTATION_FEE = Decimal("999999.99")

#: Reusable constrained string for a licence number (module spec §11).
LicenseNumber = Annotated[str, Field(min_length=1, max_length=50)]

#: Update fields whose columns are ``NOT NULL``. Declared optional so a PATCH
#: can omit them, but an explicit ``null`` is rejected.
_NON_NULLABLE_UPDATE_FIELDS = frozenset(
    {"specialization", "license_number", "consultation_fee", "qualifications", "languages"}
)


class Qualification(BaseModel):
    """One academic or professional qualification."""

    model_config = ConfigDict(extra="forbid")

    degree: str = Field(min_length=1, max_length=100, description="e.g. 'MBBS', 'MD'.")
    institution: str | None = Field(
        default=None, max_length=200, description="Awarding institution."
    )
    year: int | None = Field(default=None, ge=1900, le=2100, description="Year awarded.")


def _validate_fee(value: Decimal | None) -> Decimal | None:
    """Bound a consultation fee to the range in module spec §11.

    :param value: The raw fee.
    :returns: The fee unchanged when valid.
    :raises ValueError: If negative or above :data:`MAX_CONSULTATION_FEE`.
    """
    if value is None:
        return None
    if value < 0:
        msg = "Consultation fee cannot be negative."
        raise ValueError(msg)
    if value > MAX_CONSULTATION_FEE:
        msg = f"Consultation fee cannot exceed {MAX_CONSULTATION_FEE}."
        raise ValueError(msg)
    return value


def _validate_non_blank(value: str | None, field: str) -> str | None:
    """Trim a string and reject one that is only whitespace.

    :param value: The raw value.
    :param field: Field name, for the error message.
    :returns: The trimmed value.
    :raises ValueError: If blank after trimming.
    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        msg = f"{field} must not be blank."
        raise ValueError(msg)
    return stripped


# ── Requests ────────────────────────────────────────────────────────────────


class CreateDoctorRequest(BaseModel):
    """Payload for ``POST /api/v1/doctors`` (module spec §5.1).

    ``user_id`` references an existing user who already has the doctor role;
    this module does not create logins (module spec §2, "Out of Scope").
    ``hospital_id`` is absent by design — it comes from the authenticated user.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "user_id": "3f1c6c1e-2c3d-4a5b-8c7d-9e0f1a2b3c4d",
                "specialization": "Cardiology",
                "license_number": "TSMC-2019-44821",
                "consultation_fee": "800.00",
                "department_id": "8a7b6c5d-4e3f-2a1b-0c9d-8e7f6a5b4c3d",
                "qualifications": [
                    {"degree": "MBBS", "institution": "Osmania Medical College", "year": 2011},
                    {"degree": "MD Cardiology", "institution": "AIIMS", "year": 2015},
                ],
                "languages": ["English", "Telugu", "Hindi"],
                "bio": "Interventional cardiologist with a focus on preventive care.",
            },
        },
    )

    user_id: UUID = Field(description="UUID of the user this doctor profile belongs to.")
    specialization: str = Field(
        min_length=1, max_length=100, description="Clinical specialization."
    )
    license_number: LicenseNumber = Field(description="Medical council licence number.")
    consultation_fee: Decimal = Field(
        default=Decimal("0.00"),
        max_digits=15,
        decimal_places=2,
        description="Fee in the hospital's currency. 0 to 999999.99.",
    )
    department_id: UUID | None = Field(
        default=None, description="Department to assign the doctor to."
    )
    qualifications: list[Qualification] = Field(
        default_factory=list, description="Academic and professional qualifications."
    )
    languages: list[str] = Field(
        default_factory=list, description="Languages the doctor consults in."
    )
    bio: str | None = Field(default=None, max_length=5000, description="Professional biography.")

    @field_validator("consultation_fee")
    @classmethod
    def _check_fee(cls, value: Decimal) -> Decimal:
        """Bound the fee (module spec §11)."""
        checked = _validate_fee(value)
        assert checked is not None
        return checked

    @field_validator("specialization")
    @classmethod
    def _check_specialization(cls, value: str) -> str:
        """Trim and reject a blank specialization."""
        checked = _validate_non_blank(value, "Specialization")
        assert checked is not None
        return checked

    @field_validator("license_number")
    @classmethod
    def _check_license(cls, value: str) -> str:
        """Trim and reject a blank licence number."""
        checked = _validate_non_blank(value, "Licence number")
        assert checked is not None
        return checked

    @field_validator("languages")
    @classmethod
    def _check_languages(cls, value: list[str]) -> list[str]:
        """Trim each language and drop blanks."""
        return [lang.strip() for lang in value if lang.strip()]


class UpdateDoctorRequest(BaseModel):
    """Payload for ``PATCH /api/v1/doctors/{id}``.

    Every field optional; only fields present in the body are applied.
    ``user_id`` and ``hospital_id`` are immutable and rejected — a doctor row
    cannot be moved to a different person or tenant.
    """

    model_config = ConfigDict(extra="forbid")

    specialization: str | None = Field(
        default=None, min_length=1, max_length=100, description="Clinical specialization."
    )
    license_number: LicenseNumber | None = Field(
        default=None, description="Medical council licence number."
    )
    consultation_fee: Decimal | None = Field(
        default=None, max_digits=15, decimal_places=2, description="Fee, 0 to 999999.99."
    )
    department_id: UUID | None = Field(
        default=None, description="Department to assign the doctor to. Explicit null unassigns."
    )
    qualifications: list[Qualification] | None = Field(
        default=None, description="Replaces the qualification list."
    )
    languages: list[str] | None = Field(default=None, description="Replaces the language list.")
    bio: str | None = Field(default=None, max_length=5000, description="Professional biography.")

    @field_validator("consultation_fee")
    @classmethod
    def _check_fee(cls, value: Decimal | None) -> Decimal | None:
        """Bound the fee (module spec §11)."""
        return _validate_fee(value)

    @field_validator("specialization")
    @classmethod
    def _check_specialization(cls, value: str | None) -> str | None:
        """Trim and reject a blank specialization."""
        return _validate_non_blank(value, "Specialization")

    @field_validator("license_number")
    @classmethod
    def _check_license(cls, value: str | None) -> str | None:
        """Trim and reject a blank licence number."""
        return _validate_non_blank(value, "Licence number")

    @field_validator("languages")
    @classmethod
    def _check_languages(cls, value: list[str] | None) -> list[str] | None:
        """Trim each language and drop blanks."""
        if value is None:
            return None
        return [lang.strip() for lang in value if lang.strip()]

    @model_validator(mode="after")
    def _reject_empty_patch(self) -> Self:
        """Reject a PATCH body with no fields — always a client bug."""
        if not self.model_fields_set:
            msg = "Update request must contain at least one field."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _reject_null_for_non_nullable_columns(self) -> Self:
        """Reject an explicit ``null`` on a column the database requires.

        ``department_id`` is deliberately absent from the guarded set: it is
        genuinely nullable, so ``{"department_id": null}`` means "unassign" and
        must be honoured rather than rejected.
        """
        offenders = sorted(
            name
            for name in _NON_NULLABLE_UPDATE_FIELDS & self.model_fields_set
            if getattr(self, name) is None
        )
        if offenders:
            msg = f"These fields cannot be set to null: {', '.join(offenders)}."
            raise ValueError(msg)
        return self

    def changed_fields(self) -> dict[str, Any]:
        """Return only the fields the client actually sent.

        :returns: Mapping of column name to new value, for set fields only.
        """
        return self.model_dump(exclude_unset=True, mode="json")


class AvailabilityEntry(BaseModel):
    """One weekly availability window (module spec §11)."""

    model_config = ConfigDict(extra="forbid")

    day_of_week: int = Field(ge=0, le=6, description="0=Monday .. 6=Sunday.")
    start_time: time = Field(description="Window start, wall-clock in the hospital's timezone.")
    end_time: time = Field(description="Window end, wall-clock in the hospital's timezone.")
    slot_duration_minutes: int = Field(
        default=15,
        description=f"Slot length. One of {sorted(SLOT_DURATION_CHOICES)}.",
    )

    @field_validator("slot_duration_minutes")
    @classmethod
    def _check_duration(cls, value: int) -> int:
        """Restrict to the durations the scheduler supports."""
        if value not in SLOT_DURATION_CHOICES:
            msg = f"Slot duration must be one of {sorted(SLOT_DURATION_CHOICES)}."
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _check_time_order(self) -> Self:
        """Reject a window that ends before it starts.

        Equal times are rejected too: a zero-length window generates no slots,
        so accepting it would silently store a row that does nothing.
        """
        if self.start_time >= self.end_time:
            msg = "start_time must be strictly before end_time."
            raise ValueError(msg)
        return self


class SetAvailabilityRequest(BaseModel):
    """Payload for ``PUT /api/v1/doctors/{id}/availability`` (module spec §5.2).

    The whole weekly schedule, replacing whatever is stored. An empty list is
    valid and means "this doctor has no bookable time".
    """

    model_config = ConfigDict(extra="forbid")

    entries: list[AvailabilityEntry] = Field(
        default_factory=list, description="The complete weekly schedule."
    )

    @model_validator(mode="after")
    def _reject_overlaps(self) -> Self:
        """Reject overlapping windows within the same day (module spec §11, §14).

        Overlap is a property of the set, not of any single entry, so it cannot
        be checked on :class:`AvailabilityEntry`. Windows that merely touch —
        one ending exactly when the next begins — are fine and are the normal
        way to express a duration change mid-day.
        """
        by_day: dict[int, list[AvailabilityEntry]] = {}
        for entry in self.entries:
            by_day.setdefault(entry.day_of_week, []).append(entry)

        for day, entries in sorted(by_day.items()):
            ordered = sorted(entries, key=lambda e: e.start_time)
            for earlier, later in zip(ordered, ordered[1:], strict=False):
                if later.start_time < earlier.end_time:
                    msg = (
                        f"Overlapping availability on day {day}: "
                        f"{earlier.start_time}-{earlier.end_time} overlaps "
                        f"{later.start_time}-{later.end_time}."
                    )
                    raise ValueError(msg)
        return self


class CreateLeaveRequest(BaseModel):
    """Payload for ``POST /api/v1/doctors/{id}/leaves`` (module spec §5.3)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "starts_at": "2026-08-15T00:00:00+05:30",
                "ends_at": "2026-08-18T00:00:00+05:30",
                "reason": "Conference",
            },
        },
    )

    starts_at: datetime = Field(description="Inclusive start. Timezone-aware ISO 8601.")
    ends_at: datetime = Field(description="Exclusive end. Timezone-aware ISO 8601.")
    reason: str | None = Field(default=None, max_length=200, description="Reason for the leave.")

    @field_validator("starts_at", "ends_at")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        """Reject a naive datetime.

        Without an offset there is no way to know which instant is meant, and
        guessing would silently shift a leave by hours (CLAUDE.md rule 7:
        convert at the edge).
        """
        if value.tzinfo is None or value.utcoffset() is None:
            msg = "Must include a UTC offset, e.g. 2026-08-15T00:00:00+05:30."
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _check_range(self) -> Self:
        """Reject a leave that ends at or before it starts (module spec §11)."""
        if self.ends_at <= self.starts_at:
            msg = "ends_at must be after starts_at."
            raise ValueError(msg)
        return self


# ── Responses ───────────────────────────────────────────────────────────────


class AvailabilityResponse(BaseModel):
    """One stored availability window."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Availability row UUID.")
    day_of_week: int = Field(description="0=Monday .. 6=Sunday.")
    start_time: time = Field(description="Window start (hospital wall-clock).")
    end_time: time = Field(description="Window end (hospital wall-clock).")
    slot_duration_minutes: int = Field(description="Slot length in minutes.")

    @classmethod
    def from_model(cls, row: DoctorAvailability) -> Self:
        """Build a DTO from an ORM instance.

        :param row: The ORM instance to convert.
        :returns: The populated DTO.
        """
        return cls.model_validate(row)


class LeaveResponse(BaseModel):
    """One stored leave interval."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Leave UUID.")
    doctor_id: UUID = Field(description="Doctor the leave belongs to.")
    starts_at: datetime = Field(description="Inclusive start (UTC).")
    ends_at: datetime = Field(description="Exclusive end (UTC).")
    reason: str | None = Field(description="Reason for the leave.")

    @classmethod
    def from_model(cls, row: DoctorLeave) -> Self:
        """Build a DTO from an ORM instance.

        :param row: The ORM instance to convert.
        :returns: The populated DTO.
        """
        return cls.model_validate(row)


class DoctorSummaryResponse(BaseModel):
    """Compact doctor shape for list views and cross-module references."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Doctor UUID.")
    user_id: UUID = Field(description="Backing user UUID.")
    full_name: str = Field(description="Doctor's display name.")
    specialization: str = Field(description="Clinical specialization.")
    department_id: UUID | None = Field(description="Assigned department, if any.")
    department_name: str | None = Field(description="Assigned department's name, if any.")
    consultation_fee: Decimal = Field(description="Fee in the hospital's currency.")
    status: DoctorStatus = Field(description="active or inactive (derived from soft delete).")

    @classmethod
    def from_model(cls, doctor: Doctor) -> Self:
        """Build a summary DTO from an ORM instance.

        Reads ``doctor.user`` and ``doctor.department``, both of which are
        ``lazy="joined"`` so this costs no extra query.

        :param doctor: The ORM instance to convert.
        :returns: The populated DTO.
        """
        return cls(
            id=doctor.id,
            user_id=doctor.user_id,
            full_name=f"{doctor.user.first_name} {doctor.user.last_name}",
            specialization=doctor.specialization,
            department_id=doctor.department_id,
            department_name=doctor.department.name if doctor.department else None,
            consultation_fee=doctor.consultation_fee,
            status=doctor.status,
        )


class DoctorResponse(BaseModel):
    """Full doctor record returned by create, get, and update (module spec §9)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Doctor UUID.")
    hospital_id: UUID = Field(description="Owning hospital (tenant) UUID.")
    user_id: UUID = Field(description="Backing user UUID.")
    full_name: str = Field(description="Doctor's display name.")
    email: str | None = Field(description="Doctor's contact email, from the user record.")
    specialization: str = Field(description="Clinical specialization.")
    license_number: str = Field(description="Medical council licence number.")
    consultation_fee: Decimal = Field(description="Fee in the hospital's currency.")
    department_id: UUID | None = Field(description="Assigned department, if any.")
    department_name: str | None = Field(description="Assigned department's name, if any.")
    qualifications: list[dict[str, Any]] = Field(description="Qualifications.")
    languages: list[str] = Field(description="Languages the doctor consults in.")
    bio: str | None = Field(description="Professional biography.")
    status: DoctorStatus = Field(description="active or inactive (derived from soft delete).")
    created_at: datetime = Field(description="Creation timestamp (UTC).")
    updated_at: datetime = Field(description="Last update timestamp (UTC).")

    @classmethod
    def from_model(cls, doctor: Doctor) -> Self:
        """Build a full DTO from an ORM instance.

        :param doctor: The ORM instance to convert.
        :returns: The populated DTO.
        """
        return cls(
            id=doctor.id,
            hospital_id=doctor.hospital_id,
            user_id=doctor.user_id,
            full_name=f"{doctor.user.first_name} {doctor.user.last_name}",
            email=doctor.user.email,
            specialization=doctor.specialization,
            license_number=doctor.license_number,
            consultation_fee=doctor.consultation_fee,
            department_id=doctor.department_id,
            department_name=doctor.department.name if doctor.department else None,
            qualifications=list(doctor.qualifications),
            languages=list(doctor.languages),
            bio=doctor.bio,
            status=doctor.status,
            created_at=doctor.created_at,
            updated_at=doctor.updated_at,
        )


class SlotResponse(BaseModel):
    """One computed slot (module spec §9).

    Never persisted — see :class:`~app.models.doctor.SlotStatus`.
    """

    model_config = ConfigDict(from_attributes=True)

    start: datetime = Field(description="Slot start, in the hospital's timezone.")
    end: datetime = Field(description="Slot end, in the hospital's timezone.")
    status: SlotStatus = Field(description="available, booked, or on_leave.")
    appointment_id: UUID | None = Field(
        default=None, description="Set only when status is 'booked'."
    )


class DaySlotsResponse(BaseModel):
    """A single day's computed slots for one doctor (module spec §9)."""

    model_config = ConfigDict(from_attributes=True)

    date: DateType = Field(description="The requested date.")
    doctor_id: UUID = Field(description="Doctor the slots belong to.")
    timezone: str = Field(description="IANA timezone the slot times are expressed in.")
    slots: list[SlotResponse] = Field(
        default_factory=list, description="Slots in chronological order."
    )


#: One page of doctor summaries — the body of a list or search response.
DoctorListResponse = Page[DoctorSummaryResponse]
