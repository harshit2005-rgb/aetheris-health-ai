"""Factories for doctor test data.

Every factory returns a *valid* object by default. Tests that need an invalid
one override exactly the field under test, so the failure a test asserts on is
unambiguously the one it set up.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time
from decimal import Decimal
from typing import Any

from app.models.doctor import Doctor, DoctorAvailability, DoctorLeave
from app.schemas.doctor import (
    CreateDoctorRequest,
    CreateLeaveRequest,
    SetAvailabilityRequest,
    UpdateDoctorRequest,
)

__all__ = [
    "build_availability_payload",
    "build_create_doctor_request",
    "build_doctor_model",
    "build_doctor_payload",
    "build_leave_payload",
    "build_leave_request",
    "build_set_availability_request",
    "build_update_doctor_request",
]


def build_doctor_payload(**overrides: Any) -> dict[str, Any]:
    """Build a valid ``POST /doctors`` body as a plain dict.

    ``user_id`` defaults to a random UUID, which is fine for schema-level tests
    but must be overridden with a real user for anything touching the database.

    :param overrides: Field values to replace.
    :returns: A dict suitable for ``CreateDoctorRequest.model_validate``.
    """
    payload: dict[str, Any] = {
        "user_id": str(uuid.uuid4()),
        "specialization": "Cardiology",
        "license_number": "TSMC-2019-44821",
        "consultation_fee": "800.00",
        "qualifications": [
            {"degree": "MBBS", "institution": "Osmania Medical College", "year": 2011}
        ],
        "languages": ["English", "Telugu"],
        "bio": "Interventional cardiologist.",
    }
    payload.update(overrides)
    return payload


def build_create_doctor_request(**overrides: Any) -> CreateDoctorRequest:
    """Build a validated :class:`CreateDoctorRequest`.

    :param overrides: Field values to replace in the default payload.
    :returns: The validated request model.
    """
    return CreateDoctorRequest.model_validate(build_doctor_payload(**overrides))


def build_update_doctor_request(**fields: Any) -> UpdateDoctorRequest:
    """Build a validated :class:`UpdateDoctorRequest` with exactly ``fields`` set.

    :param fields: The fields the request sets. At least one is required.
    :returns: The validated request model.
    """
    return UpdateDoctorRequest.model_validate(fields)


def build_availability_payload(**overrides: Any) -> dict[str, Any]:
    """Build a valid ``PUT /doctors/{id}/availability`` body.

    Defaults to Monday and Wednesday mornings, 15-minute slots.

    :param overrides: Field values to replace.
    :returns: A dict suitable for ``SetAvailabilityRequest.model_validate``.
    """
    payload: dict[str, Any] = {
        "entries": [
            {
                "day_of_week": 0,
                "start_time": "09:00:00",
                "end_time": "12:00:00",
                "slot_duration_minutes": 15,
            },
            {
                "day_of_week": 2,
                "start_time": "14:00:00",
                "end_time": "17:00:00",
                "slot_duration_minutes": 30,
            },
        ]
    }
    payload.update(overrides)
    return payload


def build_set_availability_request(**overrides: Any) -> SetAvailabilityRequest:
    """Build a validated :class:`SetAvailabilityRequest`.

    :param overrides: Field values to replace in the default payload.
    :returns: The validated request model.
    """
    return SetAvailabilityRequest.model_validate(build_availability_payload(**overrides))


def build_leave_payload(**overrides: Any) -> dict[str, Any]:
    """Build a valid ``POST /doctors/{id}/leaves`` body.

    Fixed dates so assertions stay stable across runs.

    :param overrides: Field values to replace.
    :returns: A dict suitable for ``CreateLeaveRequest.model_validate``.
    """
    payload: dict[str, Any] = {
        "starts_at": "2026-08-15T00:00:00+00:00",
        "ends_at": "2026-08-18T00:00:00+00:00",
        "reason": "Conference",
    }
    payload.update(overrides)
    return payload


def build_leave_request(**overrides: Any) -> CreateLeaveRequest:
    """Build a validated :class:`CreateLeaveRequest`.

    :param overrides: Field values to replace in the default payload.
    :returns: The validated request model.
    """
    return CreateLeaveRequest.model_validate(build_leave_payload(**overrides))


def build_doctor_model(**overrides: Any) -> Doctor:
    """Build an unattached :class:`~app.models.doctor.Doctor` instance.

    Columns normally filled by the database (``id``, timestamps) are set
    explicitly, because an instance that has never been flushed has ``None``
    for all of them and would fail response serialization for reasons
    unrelated to the test.

    ``user`` and ``department`` are left for the caller to set when a test
    needs them — :meth:`DoctorResponse.from_model` reads both.

    :param overrides: Column values to replace.
    :returns: A detached Doctor suitable for unit tests.
    """
    now = datetime(2026, 7, 31, 9, 0, tzinfo=UTC)
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "hospital_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "department_id": None,
        "specialization": "Cardiology",
        "license_number": "TSMC-2019-44821",
        "consultation_fee": Decimal("800.00"),
        "qualifications": [],
        "languages": ["English"],
        "bio": None,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    values.update(overrides)
    return Doctor(**values)


def build_availability_model(**overrides: Any) -> DoctorAvailability:
    """Build an unattached :class:`~app.models.doctor.DoctorAvailability`.

    :param overrides: Column values to replace.
    :returns: A detached availability row suitable for unit tests.
    """
    now = datetime(2026, 7, 31, 9, 0, tzinfo=UTC)
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "hospital_id": uuid.uuid4(),
        "doctor_id": uuid.uuid4(),
        "day_of_week": 0,
        "start_time": time(9, 0),
        "end_time": time(12, 0),
        "slot_duration_minutes": 15,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    values.update(overrides)
    return DoctorAvailability(**values)


def build_leave_model(**overrides: Any) -> DoctorLeave:
    """Build an unattached :class:`~app.models.doctor.DoctorLeave`.

    :param overrides: Column values to replace.
    :returns: A detached leave row suitable for unit tests.
    """
    now = datetime(2026, 7, 31, 9, 0, tzinfo=UTC)
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "hospital_id": uuid.uuid4(),
        "doctor_id": uuid.uuid4(),
        "starts_at": datetime(2026, 8, 15, tzinfo=UTC),
        "ends_at": datetime(2026, 8, 18, tzinfo=UTC),
        "reason": "Conference",
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    values.update(overrides)
    return DoctorLeave(**values)
