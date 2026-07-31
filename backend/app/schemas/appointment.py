"""Pydantic DTOs for the Appointment Management module.

Request models enforce ``docs/modules/05-appointment-management.md`` §11 before
a service sees the payload (``docs/07-SECURITY.md``, rule 5). Response models
are the only appointment shapes that cross the API boundary.

Timestamps must arrive timezone-aware. An appointment is an instant, and a
naive value would be silently reinterpreted — booking someone hours from when
reception meant (CLAUDE.md rule 7: convert at the edge).
"""

from __future__ import annotations

# NOTE: runtime imports, not TYPE_CHECKING — Pydantic resolves field
# annotations against the module's real globals (backend/CLAUDE.md).
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Annotated, Self
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.models.appointment import AppointmentStatus, AppointmentType
from app.models.doctor import SLOT_DURATION_CHOICES
from app.schemas.common import Page

if TYPE_CHECKING:
    from app.models.appointment import Appointment, AppointmentStatusHistory

__all__ = [
    "MAX_REASON_LENGTH",
    "AppointmentListResponse",
    "AppointmentResponse",
    "AppointmentStatus",
    "AppointmentSummaryResponse",
    "AppointmentType",
    "BookAppointmentRequest",
    "CancelAppointmentRequest",
    "RescheduleAppointmentRequest",
    "SlotRecommendation",
    "SlotRecommendationRequest",
    "SlotRecommendationResponse",
    "StatusHistoryEntryResponse",
]

#: Module spec §11: reason is free text but bounded.
MAX_REASON_LENGTH = 500

#: Reusable bounded reason string.
ReasonText = Annotated[str, Field(max_length=MAX_REASON_LENGTH)]


def _require_aware(value: datetime, field: str) -> datetime:
    """Reject a naive datetime.

    :param value: The submitted timestamp.
    :param field: Field name, for the message.
    :returns: The value unchanged when it carries an offset.
    :raises ValueError: If the value has no UTC offset.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        msg = f"{field} must include a UTC offset, e.g. 2026-08-15T09:15:00+05:30."
        raise ValueError(msg)
    return value


def _validate_duration(start: datetime, end: datetime) -> None:
    """Assert the booking length matches a bookable slot (module spec §11).

    :param start: Proposed start.
    :param end: Proposed end.
    :raises ValueError: If the duration is non-positive or not an allowed length.
    """
    if end <= start:
        msg = "scheduled_end must be after scheduled_start."
        raise ValueError(msg)

    minutes, remainder = divmod(int((end - start).total_seconds()), 60)
    if remainder:
        msg = "Duration must be a whole number of minutes."
        raise ValueError(msg)
    if minutes not in SLOT_DURATION_CHOICES:
        msg = f"Duration must be one of {sorted(SLOT_DURATION_CHOICES)} minutes, got {minutes}."
        raise ValueError(msg)


# ── Requests ────────────────────────────────────────────────────────────────


class BookAppointmentRequest(BaseModel):
    """Payload for ``POST /api/v1/appointments`` (module spec §5.2).

    ``hospital_id`` and ``status`` are absent by design: tenancy comes from the
    authenticated user, and a new appointment is always ``booked`` — letting a
    client choose would bypass the state machine.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "patient_id": "3f1c6c1e-2c3d-4a5b-8c7d-9e0f1a2b3c4d",
                "doctor_id": "8a7b6c5d-4e3f-2a1b-0c9d-8e7f6a5b4c3d",
                "scheduled_start": "2026-08-15T09:15:00+05:30",
                "scheduled_end": "2026-08-15T09:30:00+05:30",
                "type": "new",
                "reason": "Persistent cough for 5 days",
                "notes": "Prefers morning slots",
            },
        },
    )

    patient_id: UUID = Field(description="Patient being seen.")
    doctor_id: UUID = Field(description="Doctor seeing the patient.")
    scheduled_start: datetime = Field(description="Start. Timezone-aware ISO 8601.")
    scheduled_end: datetime = Field(description="End, exclusive. Timezone-aware ISO 8601.")
    type: AppointmentType = Field(
        default=AppointmentType.NEW, description="new, follow_up, walk_in, or emergency."
    )
    reason: ReasonText | None = Field(default=None, description="Why the patient is being seen.")
    notes: str | None = Field(default=None, max_length=2000, description="Reception notes.")

    @field_validator("scheduled_start", "scheduled_end")
    @classmethod
    def _aware(cls, value: datetime, info: object) -> datetime:
        """Reject naive timestamps on both ends."""
        name = getattr(info, "field_name", "timestamp")
        return _require_aware(value, name)

    @model_validator(mode="after")
    def _check_window(self) -> Self:
        """Assert the booking length is a bookable slot duration."""
        _validate_duration(self.scheduled_start, self.scheduled_end)
        return self


class RescheduleAppointmentRequest(BaseModel):
    """Payload for ``PATCH /api/v1/appointments/{id}`` (module spec §5.3).

    Reschedule only. Everything else about a booked appointment is either
    immutable or changed through an explicit transition endpoint, so this
    carries just the new window and an optional reason for the history row.
    """

    model_config = ConfigDict(extra="forbid")

    scheduled_start: datetime = Field(description="New start. Timezone-aware ISO 8601.")
    scheduled_end: datetime = Field(description="New end, exclusive. Timezone-aware ISO 8601.")
    reason: ReasonText | None = Field(
        default=None, description="Why it is being moved. Recorded on the history row."
    )

    @field_validator("scheduled_start", "scheduled_end")
    @classmethod
    def _aware(cls, value: datetime, info: object) -> datetime:
        """Reject naive timestamps on both ends."""
        name = getattr(info, "field_name", "timestamp")
        return _require_aware(value, name)

    @model_validator(mode="after")
    def _check_window(self) -> Self:
        """Assert the new window is a bookable slot duration."""
        _validate_duration(self.scheduled_start, self.scheduled_end)
        return self


class CancelAppointmentRequest(BaseModel):
    """Payload for ``POST /api/v1/appointments/{id}/cancel``.

    A reason is **required** (module spec §11). Cancellations are a clinical
    and commercial event — someone will eventually ask why a slot went empty.
    """

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(
        min_length=1, max_length=MAX_REASON_LENGTH, description="Why it is being cancelled."
    )

    @field_validator("reason")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        """Reject a whitespace-only reason."""
        stripped = value.strip()
        if not stripped:
            msg = "Cancellation reason must not be blank."
            raise ValueError(msg)
        return stripped


class SlotRecommendationRequest(BaseModel):
    """Payload for ``POST /api/v1/appointments/recommend-slot`` (module spec §5.9)."""

    model_config = ConfigDict(extra="forbid")

    patient_id: UUID = Field(description="Patient the appointment is for.")
    doctor_id: UUID | None = Field(
        default=None, description="Preferred doctor. Omit to let the model choose."
    )
    urgency: str = Field(default="routine", max_length=20, description="routine, soon, or urgent.")
    preferred_window_start: datetime | None = Field(
        default=None, description="Earliest acceptable start. Timezone-aware."
    )
    preferred_window_end: datetime | None = Field(
        default=None, description="Latest acceptable start. Timezone-aware."
    )
    limit: int = Field(default=3, ge=1, le=10, description="How many ranked slots to return.")

    @field_validator("preferred_window_start", "preferred_window_end")
    @classmethod
    def _aware(cls, value: datetime | None, info: object) -> datetime | None:
        """Reject naive timestamps in the preferred window."""
        if value is None:
            return None
        name = getattr(info, "field_name", "timestamp")
        return _require_aware(value, name)

    @model_validator(mode="after")
    def _check_window(self) -> Self:
        """Reject an inverted preferred window."""
        if (
            self.preferred_window_start is not None
            and self.preferred_window_end is not None
            and self.preferred_window_end <= self.preferred_window_start
        ):
            msg = "preferred_window_end must be after preferred_window_start."
            raise ValueError(msg)
        return self


# ── Responses ───────────────────────────────────────────────────────────────


class StatusHistoryEntryResponse(BaseModel):
    """One recorded transition (module spec §9, AC-6)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="History row UUID.")
    from_status: AppointmentStatus | None = Field(
        description="Previous status. Null on the booking row."
    )
    to_status: AppointmentStatus = Field(description="Status after the change.")
    changed_by: UUID | None = Field(
        description="Acting user. Null when the system acted, e.g. the no-show sweeper."
    )
    changed_at: datetime = Field(description="When the change happened (UTC).")
    reason: str | None = Field(description="Why the change happened.")

    @classmethod
    def from_model(cls, row: AppointmentStatusHistory) -> Self:
        """Build a DTO from an ORM instance.

        :param row: The ORM instance to convert.
        :returns: The populated DTO.
        """
        return cls.model_validate(row)


class AppointmentSummaryResponse(BaseModel):
    """Compact appointment shape for schedules and queues."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Appointment UUID.")
    patient_id: UUID = Field(description="Patient UUID.")
    patient_name: str = Field(description="Patient's display name.")
    doctor_id: UUID = Field(description="Doctor UUID.")
    doctor_name: str = Field(description="Doctor's display name.")
    scheduled_start: datetime = Field(description="Start (UTC).")
    scheduled_end: datetime = Field(description="End (UTC).")
    status: AppointmentStatus = Field(description="Current lifecycle state.")
    type: AppointmentType = Field(description="new, follow_up, walk_in, or emergency.")

    @classmethod
    def from_model(cls, appointment: Appointment) -> Self:
        """Build a summary DTO from an ORM instance.

        Reads ``patient`` and ``doctor``, both ``lazy="joined"``, so this costs
        no extra query.

        :param appointment: The ORM instance to convert.
        :returns: The populated DTO.
        """
        return cls(
            id=appointment.id,
            patient_id=appointment.patient_id,
            patient_name=appointment.patient.full_name,
            doctor_id=appointment.doctor_id,
            doctor_name=(
                f"{appointment.doctor.user.first_name} {appointment.doctor.user.last_name}"
            ),
            scheduled_start=appointment.scheduled_start,
            scheduled_end=appointment.scheduled_end,
            status=appointment.status,
            type=appointment.type,
        )


class AppointmentResponse(BaseModel):
    """Full appointment record (module spec §9)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Appointment UUID.")
    hospital_id: UUID = Field(description="Owning hospital (tenant) UUID.")
    patient_id: UUID = Field(description="Patient UUID.")
    patient_name: str = Field(description="Patient's display name.")
    doctor_id: UUID = Field(description="Doctor UUID.")
    doctor_name: str = Field(description="Doctor's display name.")
    scheduled_start: datetime = Field(description="Start (UTC).")
    scheduled_end: datetime = Field(description="End (UTC).")
    status: AppointmentStatus = Field(description="Current lifecycle state.")
    type: AppointmentType = Field(description="new, follow_up, walk_in, or emergency.")
    reason: str | None = Field(description="Why the patient is being seen.")
    notes: str | None = Field(description="Reception notes.")
    cancelled_reason: str | None = Field(description="Why it was cancelled, if it was.")
    checked_in_at: datetime | None = Field(description="When the patient arrived (UTC).")
    started_at: datetime | None = Field(description="When the consultation began (UTC).")
    completed_at: datetime | None = Field(description="When it finished (UTC).")
    created_at: datetime = Field(description="Creation timestamp (UTC).")
    updated_at: datetime = Field(description="Last update timestamp (UTC).")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def duration_minutes(self) -> int:
        """Length of the appointment in whole minutes."""
        return int((self.scheduled_end - self.scheduled_start).total_seconds() // 60)

    @classmethod
    def from_model(cls, appointment: Appointment) -> Self:
        """Build a full DTO from an ORM instance.

        :param appointment: The ORM instance to convert.
        :returns: The populated DTO.
        """
        return cls(
            id=appointment.id,
            hospital_id=appointment.hospital_id,
            patient_id=appointment.patient_id,
            patient_name=appointment.patient.full_name,
            doctor_id=appointment.doctor_id,
            doctor_name=(
                f"{appointment.doctor.user.first_name} {appointment.doctor.user.last_name}"
            ),
            scheduled_start=appointment.scheduled_start,
            scheduled_end=appointment.scheduled_end,
            status=appointment.status,
            type=appointment.type,
            reason=appointment.reason,
            notes=appointment.notes,
            cancelled_reason=appointment.cancelled_reason,
            checked_in_at=appointment.checked_in_at,
            started_at=appointment.started_at,
            completed_at=appointment.completed_at,
            created_at=appointment.created_at,
            updated_at=appointment.updated_at,
        )


class SlotRecommendation(BaseModel):
    """One AI-ranked slot (module spec §13)."""

    model_config = ConfigDict(from_attributes=True)

    slot_start: datetime = Field(description="Suggested start.")
    slot_end: datetime = Field(description="Suggested end.")
    doctor_id: UUID = Field(description="Doctor the slot belongs to.")
    score: float = Field(ge=0.0, le=1.0, description="Model confidence, 0 to 1.")
    reason: str = Field(max_length=500, description="Why this slot was suggested.")


class SlotRecommendationResponse(BaseModel):
    """Ranked slot suggestions.

    The model only ever recommends — reception books (module spec §13,
    "Safety"). Nothing here reserves a slot, so a suggestion going stale
    between recommendation and booking is caught by the normal overlap check.
    """

    model_config = ConfigDict(from_attributes=True)

    recommendations: list[SlotRecommendation] = Field(
        default_factory=list, description="Ranked best-first."
    )
    model: str | None = Field(default=None, description="Model that produced the ranking.")


#: One page of appointment summaries — the body of a list response.
AppointmentListResponse = Page[AppointmentSummaryResponse]
