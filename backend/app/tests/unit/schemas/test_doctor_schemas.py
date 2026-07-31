"""Unit tests for the doctor Pydantic DTOs.

Covers every validation rule in ``docs/modules/04-doctor-management.md`` §11.
No database, no service — these assert that a malformed payload never reaches
the service layer (``docs/07-SECURITY.md``, rule 5).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.models.doctor import SLOT_DURATION_CHOICES
from app.schemas.doctor import (
    MAX_CONSULTATION_FEE,
    AvailabilityEntry,
    CreateDoctorRequest,
    CreateLeaveRequest,
    SetAvailabilityRequest,
    UpdateDoctorRequest,
)
from app.tests.factories import build_doctor_payload, build_leave_payload

# ── Consultation fee (module spec §11) ──────────────────────────────────────


@pytest.mark.parametrize("fee", ["0", "0.00", "800.00", "999999.99"])
def test_fee_within_bounds_accepted(fee: str) -> None:
    request = CreateDoctorRequest.model_validate(build_doctor_payload(consultation_fee=fee))
    assert request.consultation_fee == Decimal(fee)


@pytest.mark.parametrize("fee", ["-0.01", "-1", "1000000.00"])
def test_fee_outside_bounds_rejected(fee: str) -> None:
    """0 to 999999.99 — anything else is a data-entry error, not a real fee."""
    with pytest.raises(PydanticValidationError):
        CreateDoctorRequest.model_validate(build_doctor_payload(consultation_fee=fee))


def test_fee_defaults_to_zero() -> None:
    payload = build_doctor_payload()
    payload.pop("consultation_fee")
    assert CreateDoctorRequest.model_validate(payload).consultation_fee == Decimal("0.00")


def test_max_fee_constant_matches_column_precision() -> None:
    """NUMERIC(15,2) with the documented bound."""
    assert Decimal("999999.99") == MAX_CONSULTATION_FEE


# ── Licence and specialization ──────────────────────────────────────────────


@pytest.mark.parametrize("bad", ["", " ", "   "])
def test_blank_license_rejected(bad: str) -> None:
    with pytest.raises(PydanticValidationError):
        CreateDoctorRequest.model_validate(build_doctor_payload(license_number=bad))


def test_license_over_fifty_chars_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        CreateDoctorRequest.model_validate(build_doctor_payload(license_number="L" * 51))


def test_specialization_is_trimmed() -> None:
    request = CreateDoctorRequest.model_validate(
        build_doctor_payload(specialization="  Cardiology  ")
    )
    assert request.specialization == "Cardiology"


@pytest.mark.parametrize("bad", ["", "  "])
def test_blank_specialization_rejected(bad: str) -> None:
    with pytest.raises(PydanticValidationError):
        CreateDoctorRequest.model_validate(build_doctor_payload(specialization=bad))


def test_languages_are_trimmed_and_blanks_dropped() -> None:
    request = CreateDoctorRequest.model_validate(
        build_doctor_payload(languages=[" English ", "", "  ", "Telugu"])
    )
    assert request.languages == ["English", "Telugu"]


def test_unknown_field_rejected() -> None:
    """``extra="forbid"`` turns a smuggled column into a 422."""
    with pytest.raises(PydanticValidationError):
        CreateDoctorRequest.model_validate(build_doctor_payload(hospital_id=str(uuid.uuid4())))


# ── Update semantics ────────────────────────────────────────────────────────


def test_empty_patch_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        UpdateDoctorRequest.model_validate({})


@pytest.mark.parametrize("field", ["specialization", "license_number", "consultation_fee"])
def test_explicit_null_on_required_column_rejected(field: str) -> None:
    with pytest.raises(PydanticValidationError) as exc:
        UpdateDoctorRequest.model_validate({field: None})
    assert field in str(exc.value)


def test_explicit_null_department_is_allowed() -> None:
    """``department_id`` is genuinely nullable, so null means 'unassign'.

    Guarding it like the NOT NULL columns would make unassigning impossible.
    """
    request = UpdateDoctorRequest.model_validate({"department_id": None})
    assert request.changed_fields() == {"department_id": None}


def test_changed_fields_returns_only_sent_fields() -> None:
    request = UpdateDoctorRequest.model_validate({"bio": "Updated"})
    assert request.changed_fields() == {"bio": "Updated"}


# ── Availability entries (module spec §11) ──────────────────────────────────


@pytest.mark.parametrize("day", [0, 3, 6])
def test_valid_day_of_week_accepted(day: int) -> None:
    entry = AvailabilityEntry.model_validate(
        {"day_of_week": day, "start_time": "09:00", "end_time": "10:00"}
    )
    assert entry.day_of_week == day


@pytest.mark.parametrize("day", [-1, 7, 100])
def test_day_of_week_outside_range_rejected(day: int) -> None:
    with pytest.raises(PydanticValidationError):
        AvailabilityEntry.model_validate(
            {"day_of_week": day, "start_time": "09:00", "end_time": "10:00"}
        )


@pytest.mark.parametrize("duration", SLOT_DURATION_CHOICES)
def test_supported_slot_durations_accepted(duration: int) -> None:
    entry = AvailabilityEntry.model_validate(
        {
            "day_of_week": 0,
            "start_time": "09:00",
            "end_time": "12:00",
            "slot_duration_minutes": duration,
        }
    )
    assert entry.slot_duration_minutes == duration


@pytest.mark.parametrize("duration", [0, 7, 25, 90, -15])
def test_unsupported_slot_duration_rejected(duration: int) -> None:
    with pytest.raises(PydanticValidationError):
        AvailabilityEntry.model_validate(
            {
                "day_of_week": 0,
                "start_time": "09:00",
                "end_time": "12:00",
                "slot_duration_minutes": duration,
            }
        )


def test_end_before_start_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        AvailabilityEntry.model_validate(
            {"day_of_week": 0, "start_time": "12:00", "end_time": "09:00"}
        )


def test_zero_length_window_rejected() -> None:
    """A window that starts and ends together generates no slots."""
    with pytest.raises(PydanticValidationError):
        AvailabilityEntry.model_validate(
            {"day_of_week": 0, "start_time": "09:00", "end_time": "09:00"}
        )


# ── Availability sets (overlap is a property of the set) ────────────────────


def test_overlapping_windows_on_the_same_day_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        SetAvailabilityRequest.model_validate(
            {
                "entries": [
                    {"day_of_week": 0, "start_time": "09:00", "end_time": "12:00"},
                    {"day_of_week": 0, "start_time": "11:00", "end_time": "13:00"},
                ]
            }
        )


def test_touching_windows_allowed() -> None:
    """One window ending exactly when the next starts is how a mid-day
    duration change is expressed — it must not be treated as an overlap."""
    request = SetAvailabilityRequest.model_validate(
        {
            "entries": [
                {"day_of_week": 0, "start_time": "09:00", "end_time": "12:00"},
                {
                    "day_of_week": 0,
                    "start_time": "12:00",
                    "end_time": "17:00",
                    "slot_duration_minutes": 30,
                },
            ]
        }
    )
    assert len(request.entries) == 2


def test_same_times_on_different_days_allowed() -> None:
    request = SetAvailabilityRequest.model_validate(
        {
            "entries": [
                {"day_of_week": 0, "start_time": "09:00", "end_time": "12:00"},
                {"day_of_week": 1, "start_time": "09:00", "end_time": "12:00"},
            ]
        }
    )
    assert len(request.entries) == 2


def test_empty_schedule_allowed() -> None:
    """Clearing availability is legitimate, not an empty-payload bug."""
    assert SetAvailabilityRequest.model_validate({"entries": []}).entries == []


def test_overlap_detected_regardless_of_input_order() -> None:
    """Entries arrive unsorted; the check sorts before comparing."""
    with pytest.raises(PydanticValidationError):
        SetAvailabilityRequest.model_validate(
            {
                "entries": [
                    {"day_of_week": 2, "start_time": "14:00", "end_time": "16:00"},
                    {"day_of_week": 2, "start_time": "09:00", "end_time": "15:00"},
                ]
            }
        )


# ── Leaves (module spec §11) ────────────────────────────────────────────────


def test_leave_requires_timezone_aware_timestamps() -> None:
    """A naive timestamp is ambiguous; guessing would shift the leave."""
    with pytest.raises(PydanticValidationError):
        CreateLeaveRequest.model_validate(
            {"starts_at": "2026-08-15T00:00:00", "ends_at": "2026-08-18T00:00:00"}
        )


def test_leave_end_must_follow_start() -> None:
    with pytest.raises(PydanticValidationError):
        CreateLeaveRequest.model_validate(
            build_leave_payload(
                starts_at="2026-08-18T00:00:00+00:00", ends_at="2026-08-15T00:00:00+00:00"
            )
        )


def test_zero_length_leave_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        CreateLeaveRequest.model_validate(
            build_leave_payload(
                starts_at="2026-08-15T00:00:00+00:00", ends_at="2026-08-15T00:00:00+00:00"
            )
        )


def test_leave_accepts_any_offset() -> None:
    """Offsets other than UTC are fine — the service normalises them."""
    request = CreateLeaveRequest.model_validate(
        build_leave_payload(
            starts_at="2026-08-15T05:30:00+05:30", ends_at="2026-08-16T05:30:00+05:30"
        )
    )
    assert request.starts_at.utcoffset() is not None


def test_leave_reason_is_optional() -> None:
    payload = build_leave_payload()
    payload.pop("reason")
    assert CreateLeaveRequest.model_validate(payload).reason is None
