"""Factories for appointment test data.

Every factory returns a *valid* object by default. Tests that need an invalid
one override exactly the field under test.

Times default to a fixed future instant rather than ``now() + delta`` so
assertions are stable, while still passing the "not in the past" rule.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.schemas.appointment import (
    BookAppointmentRequest,
    CancelAppointmentRequest,
    RescheduleAppointmentRequest,
)

__all__ = [
    "DEFAULT_START",
    "build_appointment_model",
    "build_appointment_payload",
    "build_book_request",
    "build_cancel_request",
    "build_reschedule_request",
    "future_window",
]

#: A fixed future Monday 09:00 UTC. Far enough out that the "no booking in the
#: past" rule passes for years, and a weekday so it lines up with the Monday
#: availability the doctor factories create.
DEFAULT_START = datetime(2030, 1, 7, 9, 0, tzinfo=UTC)


def future_window(minutes: int = 15, *, offset_minutes: int = 0) -> tuple[datetime, datetime]:
    """Return a ``(start, end)`` window of a bookable duration.

    :param minutes: Slot length. Must be one of the allowed durations.
    :param offset_minutes: Shift from :data:`DEFAULT_START`, for building
        adjacent or overlapping windows in one test.
    :returns: A timezone-aware half-open window.
    """
    start = DEFAULT_START + timedelta(minutes=offset_minutes)
    return start, start + timedelta(minutes=minutes)


def build_appointment_payload(**overrides: Any) -> dict[str, Any]:
    """Build a valid ``POST /appointments`` body as a plain dict.

    :param overrides: Field values to replace.
    :returns: A dict suitable for ``BookAppointmentRequest.model_validate``.
    """
    start, end = future_window()
    payload: dict[str, Any] = {
        "patient_id": str(uuid.uuid4()),
        "doctor_id": str(uuid.uuid4()),
        "scheduled_start": start.isoformat(),
        "scheduled_end": end.isoformat(),
        "type": "new",
        "reason": "Persistent cough for 5 days",
        "notes": "Prefers morning slots",
    }
    payload.update(overrides)
    return payload


def build_book_request(**overrides: Any) -> BookAppointmentRequest:
    """Build a validated :class:`BookAppointmentRequest`.

    :param overrides: Field values to replace in the default payload.
    :returns: The validated request model.
    """
    return BookAppointmentRequest.model_validate(build_appointment_payload(**overrides))


def build_reschedule_request(**overrides: Any) -> RescheduleAppointmentRequest:
    """Build a validated :class:`RescheduleAppointmentRequest`.

    Defaults to moving the appointment one hour later.

    :param overrides: Field values to replace.
    :returns: The validated request model.
    """
    start, end = future_window(offset_minutes=60)
    payload: dict[str, Any] = {
        "scheduled_start": start.isoformat(),
        "scheduled_end": end.isoformat(),
    }
    payload.update(overrides)
    return RescheduleAppointmentRequest.model_validate(payload)


def build_cancel_request(**overrides: Any) -> CancelAppointmentRequest:
    """Build a validated :class:`CancelAppointmentRequest`.

    :param overrides: Field values to replace.
    :returns: The validated request model.
    """
    payload: dict[str, Any] = {"reason": "Patient called to cancel"}
    payload.update(overrides)
    return CancelAppointmentRequest.model_validate(payload)


def build_appointment_model(**overrides: Any) -> Appointment:
    """Build an unattached :class:`~app.models.appointment.Appointment`.

    Columns normally filled by the database are set explicitly, because an
    instance that was never flushed has ``None`` for all of them and would fail
    response serialization for reasons unrelated to the test.

    ``patient`` and ``doctor`` are left unset — the DTOs read them, so tests
    that serialize must attach doubles.

    :param overrides: Column values to replace.
    :returns: A detached Appointment suitable for unit tests.
    """
    now = datetime(2026, 7, 31, 9, 0, tzinfo=UTC)
    start, end = future_window()
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "hospital_id": uuid.uuid4(),
        "patient_id": uuid.uuid4(),
        "doctor_id": uuid.uuid4(),
        "scheduled_start": start,
        "scheduled_end": end,
        "status": AppointmentStatus.BOOKED,
        "type": AppointmentType.NEW,
        "reason": "Persistent cough for 5 days",
        "notes": None,
        "cancelled_reason": None,
        "checked_in_at": None,
        "started_at": None,
        "completed_at": None,
        "idempotency_key": None,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    values.update(overrides)
    return Appointment(**values)
