"""Unit tests for the Consultation service and DTOs (repositories mocked).

The rules (``docs/modules/16-consultation.md`` §4) are tested here without a
database; the API tests prove the same paths end to end.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import (
    BusinessRuleError,
    ConflictError,
    PermissionDeniedError,
    ValidationError,
)
from app.models.appointment import AppointmentStatus
from app.models.consultation import ConsultationStatus
from app.schemas.consultation import (
    AddAddendumRequest,
    CreateConsultationRequest,
    UpdateConsultationRequest,
    Vitals,
    bmi,
)
from app.services.consultation_service import ConsultationNotFoundError, ConsultationService
from app.tests.conftest import RecordingAuditSink

HOSPITAL = uuid.uuid4()
DOCTOR_USER = uuid.uuid4()
OTHER_USER = uuid.uuid4()


def _appointment(status: AppointmentStatus = AppointmentStatus.IN_PROGRESS) -> Any:
    return SimpleNamespace(
        id=uuid.uuid4(),
        hospital_id=HOSPITAL,
        patient_id=uuid.uuid4(),
        doctor_id=uuid.uuid4(),
        status=status,
        doctor=SimpleNamespace(user_id=DOCTOR_USER),
    )


def _note(**overrides: Any) -> Any:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "hospital_id": HOSPITAL,
        "appointment_id": uuid.uuid4(),
        "status": ConsultationStatus.DRAFT,
        "chief_complaint": "Fever",
        "diagnoses": [{"code": None, "description": "Viral fever"}],
        "doctor": SimpleNamespace(user_id=DOCTOR_USER),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _Harness:
    def __init__(self, *, appointment: Any = None, note: Any = None) -> None:
        self.consultations = AsyncMock()
        self.consultations.get_for_hospital.return_value = note
        self.consultations.get_by_appointment.return_value = None
        self.consultations.create_consultation.side_effect = lambda **kw: _note(
            **{k: v for k, v in kw.items() if k in {"appointment_id"}}
        )
        self.consultations.update_consultation.side_effect = lambda c, **kw: c
        self.consultations.add_addendum.side_effect = lambda c, **kw: c
        self.appointments = AsyncMock()
        self.appointments.get_appointment_by_id.return_value = appointment
        self.session = AsyncMock()
        self.audit = RecordingAuditSink()
        self.service = ConsultationService(
            self.consultations,
            self.appointments,
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            self.session,
            self.audit,
        )
        # The response build reads ORM relationships; the rules are what is tested.
        self.respond = patch.object(ConsultationService, "_respond", AsyncMock(return_value="ok"))

    def __enter__(self) -> _Harness:
        self.respond.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.respond.stop()


class TestCreate:
    async def test_the_visits_doctor_starts_the_note(self) -> None:
        appointment = _appointment()
        with _Harness(appointment=appointment) as h:
            await h.service.create(
                HOSPITAL,
                CreateConsultationRequest(appointment_id=appointment.id, chief_complaint="Fever"),
                actor_id=DOCTOR_USER,
            )

        kwargs = h.consultations.create_consultation.call_args.kwargs
        assert kwargs["patient_id"] == appointment.patient_id
        assert kwargs["doctor_id"] == appointment.doctor_id
        assert kwargs["chief_complaint"] == "Fever"
        assert [e.action for e in h.audit.events] == ["consultation.created"]
        h.session.commit.assert_awaited_once()

    async def test_another_doctor_is_refused(self) -> None:
        appointment = _appointment()
        with _Harness(appointment=appointment) as h, pytest.raises(PermissionDeniedError):
            await h.service.create(
                HOSPITAL,
                CreateConsultationRequest(appointment_id=appointment.id),
                actor_id=OTHER_USER,
            )
        h.consultations.create_consultation.assert_not_called()

    @pytest.mark.parametrize(
        "status",
        [AppointmentStatus.BOOKED, AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW],
    )
    async def test_a_visit_not_under_way_is_refused(self, status: AppointmentStatus) -> None:
        appointment = _appointment(status)
        with _Harness(appointment=appointment) as h, pytest.raises(BusinessRuleError):
            await h.service.create(
                HOSPITAL,
                CreateConsultationRequest(appointment_id=appointment.id),
                actor_id=DOCTOR_USER,
            )

    async def test_a_second_note_is_a_conflict(self) -> None:
        appointment = _appointment()
        with _Harness(appointment=appointment) as h:
            h.consultations.get_by_appointment.return_value = _note()
            with pytest.raises(ConflictError):
                await h.service.create(
                    HOSPITAL,
                    CreateConsultationRequest(appointment_id=appointment.id),
                    actor_id=DOCTOR_USER,
                )


class TestEditing:
    async def test_a_finalized_note_is_not_edited(self) -> None:
        note = _note(status=ConsultationStatus.FINALIZED)
        with _Harness(note=note) as h, pytest.raises(BusinessRuleError, match="addendum"):
            await h.service.update(
                HOSPITAL, note.id, UpdateConsultationRequest(plan="x"), actor_id=DOCTOR_USER
            )

    async def test_only_sent_sections_change(self) -> None:
        note = _note()
        with _Harness(note=note) as h:
            await h.service.update(
                HOSPITAL,
                note.id,
                UpdateConsultationRequest(plan="  Rest  ", history=""),
                actor_id=DOCTOR_USER,
            )

        kwargs = h.consultations.update_consultation.call_args.kwargs
        assert kwargs == {"updated_by": DOCTOR_USER, "plan": "Rest", "history": None}

    async def test_unknown_note_is_not_found(self) -> None:
        with _Harness(note=None) as h, pytest.raises(ConsultationNotFoundError):
            await h.service.update(
                HOSPITAL, uuid.uuid4(), UpdateConsultationRequest(plan="x"), actor_id=DOCTOR_USER
            )


class TestFinalize:
    async def test_needs_a_complaint_and_a_diagnosis(self) -> None:
        note = _note(chief_complaint=" ", diagnoses=[])
        with _Harness(note=note) as h, pytest.raises(ValidationError) as caught:
            await h.service.finalize(HOSPITAL, note.id, actor_id=DOCTOR_USER)

        fields = {e["field"] for e in caught.value.detail["errors"]}
        assert fields == {"chief_complaint", "diagnoses"}

    async def test_finalizing_records_who_and_when(self) -> None:
        note = _note()
        with _Harness(note=note) as h:
            await h.service.finalize(HOSPITAL, note.id, actor_id=DOCTOR_USER)

        kwargs = h.consultations.update_consultation.call_args.kwargs
        assert kwargs["status"] is ConsultationStatus.FINALIZED
        assert kwargs["finalized_by"] == DOCTOR_USER
        assert kwargs["finalized_at"].tzinfo is UTC
        assert [e.action for e in h.audit.events] == ["consultation.finalized"]

    async def test_addenda_only_after_finalizing(self) -> None:
        note = _note()
        with _Harness(note=note) as h, pytest.raises(BusinessRuleError, match="draft"):
            await h.service.add_addendum(
                HOSPITAL, note.id, AddAddendumRequest(text="x"), actor_id=DOCTOR_USER
            )


class TestVitals:
    def test_bmi(self) -> None:
        assert bmi({"weight_kg": "70.0", "height_cm": "175.0"}) == Decimal("22.9")
        assert bmi({"weight_kg": "70.0"}) is None
        assert bmi(None) is None

    def test_stored_without_empty_fields(self) -> None:
        vitals = Vitals(pulse=80, temperature_c=Decimal("37.2"))

        assert vitals.to_json() == {"pulse": 80, "temperature_c": "37.2"}

    @pytest.mark.parametrize(
        "values",
        [
            {},
            {"bp_systolic": 120},
            {"bp_systolic": 90, "bp_diastolic": 95},
            {"temperature_c": "50"},
        ],
    )
    def test_implausible_vitals(self, values: dict[str, Any]) -> None:
        with pytest.raises(PydanticValidationError):
            Vitals.model_validate(values)

    async def test_vitals_on_a_finalized_note_are_refused(self) -> None:
        note = _note(status=ConsultationStatus.FINALIZED)
        with _Harness(note=note) as h, pytest.raises(BusinessRuleError):
            await h.service.record_vitals(HOSPITAL, note.id, Vitals(pulse=80), actor_id=OTHER_USER)


class TestRequests:
    def test_an_empty_update_is_refused(self) -> None:
        with pytest.raises(PydanticValidationError):
            UpdateConsultationRequest()

    def test_diagnoses_are_capped(self) -> None:
        many = [{"description": f"d{i}"} for i in range(21)]
        with pytest.raises(PydanticValidationError):
            UpdateConsultationRequest.model_validate({"diagnoses": many})

    def test_follow_up_date_parses(self) -> None:
        assert UpdateConsultationRequest.model_validate(
            {"follow_up_date": "2030-01-01"}
        ).follow_up_date == date(2030, 1, 1)

    def test_create_refuses_unknown_fields(self) -> None:
        with pytest.raises(PydanticValidationError):
            CreateConsultationRequest.model_validate(
                {"appointment_id": str(uuid.uuid4()), "doctor_id": str(uuid.uuid4())}
            )
