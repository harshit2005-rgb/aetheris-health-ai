"""Integration tests for the Appointment Management module.

Real database, real repositories, real services — only the audit sink and the
Billing seam are doubles (``docs/11-TESTING_STRATEGY.md`` §2.4).

Covers the workflow module spec §16 asks for — book → check in → start →
complete, with the invoice draft handed off — plus the cross-module payoff of
this PR: **Doctor Management's slot feed and deletion guard now work**, because
Appointments supplies the ``BookedIntervalSource`` they were written against.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

from app.models.appointment import AppointmentStatus
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.doctor_repository import DoctorRepository
from app.repositories.hospital_repository import HospitalRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.user_repository import UserRepository
from app.services.appointment_service import (
    AppointmentBookedIntervalSource,
    AppointmentService,
    InvalidTransitionError,
)
from app.services.doctor_service import DoctorHasAppointmentsError, DoctorService
from app.tests.factories import build_book_request, build_cancel_request

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.tests.conftest import RecordingAuditSink

pytestmark = pytest.mark.database

#: Monday 09:00 UTC, far enough out that "not in the past" always holds.
BASE = datetime(2030, 1, 7, 9, 0, tzinfo=UTC)


class _RecordingInvoiceSink:
    """Captures the invoice drafts Billing would receive (§5.6 step 6)."""

    def __init__(self) -> None:
        self.drafted: list[uuid.UUID] = []

    async def draft_invoice_for(
        self, hospital_id: uuid.UUID, appointment_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> None:
        """Record the request rather than drafting anything."""
        self.drafted.append(appointment_id)


@pytest.fixture
def appointments_repo(db_session: AsyncSession) -> AppointmentRepository:
    """Appointment repository on the transactional test session."""
    return AppointmentRepository(db_session)


@pytest.fixture
def invoices() -> _RecordingInvoiceSink:
    """A recording stand-in for Billing."""
    return _RecordingInvoiceSink()


@pytest.fixture
def service(
    db_session: AsyncSession,
    appointments_repo: AppointmentRepository,
    audit_sink: RecordingAuditSink,
    invoices: _RecordingInvoiceSink,
) -> AppointmentService:
    """A fully wired :class:`AppointmentService`."""
    return AppointmentService(
        appointments_repo,
        PatientRepository(db_session),
        DoctorRepository(db_session),
        HospitalRepository(db_session),
        db_session,
        audit_sink,
        invoices,
    )


@pytest.fixture
def doctor_service(
    db_session: AsyncSession,
    appointments_repo: AppointmentRepository,
    audit_sink: RecordingAuditSink,
) -> DoctorService:
    """A :class:`DoctorService` wired to the **real** booked-interval source.

    This is the wiring that ships in ``app/api/dependencies/services.py`` now
    that Appointment Management exists.
    """
    return DoctorService(
        DoctorRepository(db_session),
        UserRepository(db_session),
        DepartmentRepository(db_session),
        HospitalRepository(db_session),
        db_session,
        audit_sink,
        AppointmentBookedIntervalSource(appointments_repo),
    )


async def _clinical(session: AsyncSession, hospital_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a patient and a doctor, returning their ids."""
    from app.models.doctor import Doctor
    from app.models.patient import Gender, Patient
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        hospital_id=hospital_id,
        email=f"int-appt-{uuid.uuid4().hex[:12]}@hospital.test",
        password_hash="test-placeholder-not-a-hash",
        first_name="Asha",
        last_name="Menon",
    )
    session.add(user)
    await session.flush()

    doctor = Doctor(
        id=uuid.uuid4(),
        hospital_id=hospital_id,
        user_id=user.id,
        specialization="Cardiology",
        license_number=f"LIC-{uuid.uuid4().hex[:8]}",
    )
    patient = Patient(
        id=uuid.uuid4(),
        hospital_id=hospital_id,
        mrn=f"MRN-{uuid.uuid4().hex[:8]}",
        first_name="Ananya",
        last_name="Rao",
        date_of_birth=date(1990, 1, 1),
        gender=Gender.FEMALE,
    )
    session.add_all([doctor, patient])
    await session.flush()
    return patient.id, doctor.id


def _request(patient_id: uuid.UUID, doctor_id: uuid.UUID, **overrides: Any) -> Any:
    """Build a booking request against the fixed base time."""
    start = BASE + timedelta(minutes=overrides.pop("offset_minutes", 0))
    return build_book_request(
        patient_id=str(patient_id),
        doctor_id=str(doctor_id),
        scheduled_start=start.isoformat(),
        scheduled_end=(start + timedelta(minutes=15)).isoformat(),
        **overrides,
    )


async def test_full_lifecycle(
    service: AppointmentService,
    db_session: AsyncSession,
    hospital_id: uuid.UUID,
    actor_id: uuid.UUID,
    audit_sink: RecordingAuditSink,
    invoices: _RecordingInvoiceSink,
) -> None:
    """Book → check in → start → complete → invoice draft, end to end."""
    patient_id, doctor_id = await _clinical(db_session, hospital_id)

    appointment, created = await service.book_appointment(
        hospital_id,
        _request(patient_id, doctor_id),
        idempotency_key="lifecycle-key-1",
        actor_id=actor_id,
        allow_override=True,
    )
    assert created is True
    assert appointment.status is AppointmentStatus.BOOKED

    checked_in = await service.check_in(hospital_id, appointment.id, actor_id=actor_id)
    assert checked_in.checked_in_at is not None

    started = await service.start(hospital_id, appointment.id, actor_id=actor_id)
    assert started.started_at is not None

    completed = await service.complete(hospital_id, appointment.id, actor_id=actor_id)
    assert completed.status is AppointmentStatus.COMPLETED

    # §5.6 step 6: Billing is asked to draft an invoice.
    assert invoices.drafted == [appointment.id]

    # AC-6: every transition recorded, booking included.
    history = await service.get_status_history(hospital_id, appointment.id)
    assert {(h.from_status, h.to_status) for h in history} == {
        (None, AppointmentStatus.BOOKED),
        (AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN),
        (AppointmentStatus.CHECKED_IN, AppointmentStatus.IN_PROGRESS),
        (AppointmentStatus.IN_PROGRESS, AppointmentStatus.COMPLETED),
    }

    assert audit_sink.actions() == [
        "appointment.booked",
        "appointment.checked_in",
        "appointment.started",
        "appointment.completed",
    ]


async def test_idempotent_booking_across_the_full_stack(
    service: AppointmentService,
    db_session: AsyncSession,
    hospital_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """FR-8: the same key never produces a second appointment."""
    patient_id, doctor_id = await _clinical(db_session, hospital_id)

    first, created_first = await service.book_appointment(
        hospital_id,
        _request(patient_id, doctor_id),
        idempotency_key="same-key",
        actor_id=actor_id,
        allow_override=True,
    )
    second, created_second = await service.book_appointment(
        hospital_id,
        _request(patient_id, doctor_id),
        idempotency_key="same-key",
        actor_id=actor_id,
        allow_override=True,
    )

    assert created_first is True
    assert created_second is False
    assert first.id == second.id
    assert (await service.list_appointments(hospital_id)).total_records == 1


async def test_cancelled_appointment_cannot_be_reactivated(
    service: AppointmentService,
    db_session: AsyncSession,
    hospital_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Business rule 5 through the full stack."""
    patient_id, doctor_id = await _clinical(db_session, hospital_id)
    appointment, _ = await service.book_appointment(
        hospital_id,
        _request(patient_id, doctor_id),
        idempotency_key="cancel-key",
        actor_id=actor_id,
        allow_override=True,
    )

    await service.cancel(hospital_id, appointment.id, build_cancel_request(), actor_id=actor_id)

    with pytest.raises(InvalidTransitionError):
        await service.check_in(hospital_id, appointment.id, actor_id=actor_id)


async def test_no_show_sweeper_marks_overdue_appointments(
    service: AppointmentService,
    db_session: AsyncSession,
    hospital_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """AC-5, against the real query and a real row."""
    patient_id, doctor_id = await _clinical(db_session, hospital_id)
    appointment, _ = await service.book_appointment(
        hospital_id,
        _request(patient_id, doctor_id),
        idempotency_key="sweep-key",
        actor_id=actor_id,
        allow_override=True,
    )

    # An hour after the appointment ended — past the 30-minute default grace.
    swept = await service.sweep_no_shows(now=BASE + timedelta(minutes=75))

    assert swept == 1
    refreshed = await service.get_appointment(hospital_id, appointment.id)
    assert refreshed.status is AppointmentStatus.NO_SHOW

    history = await service.get_status_history(hospital_id, appointment.id)
    sweeper_row = next(h for h in history if h.to_status is AppointmentStatus.NO_SHOW)
    # The system acted, so there is no acting user.
    assert sweeper_row.changed_by is None
    assert sweeper_row.reason == "no_show_sweeper"


async def test_tenant_isolation(
    service: AppointmentService,
    db_session: AsyncSession,
    hospital_id: uuid.UUID,
    other_hospital_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """An appointment is invisible to another hospital through every path."""
    from app.services.appointment_service import AppointmentNotFoundError

    patient_id, doctor_id = await _clinical(db_session, hospital_id)
    appointment, _ = await service.book_appointment(
        hospital_id,
        _request(patient_id, doctor_id),
        idempotency_key="tenant-key",
        actor_id=actor_id,
        allow_override=True,
    )

    with pytest.raises(AppointmentNotFoundError):
        await service.get_appointment(other_hospital_id, appointment.id)
    with pytest.raises(AppointmentNotFoundError):
        await service.check_in(other_hospital_id, appointment.id)
    assert (await service.list_appointments(other_hospital_id)).total_records == 0


async def _use_utc_timezone(session: AsyncSession, hospital_id: uuid.UUID) -> None:
    """Pin the test hospital to UTC.

    Availability is stored as wall-clock and resolved in the hospital's
    timezone, which defaults to ``Asia/Kolkata``. These tests are about the
    appointments-to-doctors seam, not about timezone conversion — which the
    doctor slot suite already covers exhaustively, DST included. Pinning UTC
    makes "book at 09:15" and "the 09:15 slot" mean the same instant, so a
    failure here is a seam failure and nothing else.
    """
    from app.models.hospital import Hospital

    hospital = await session.get(Hospital, hospital_id)
    assert hospital is not None
    hospital.timezone = "UTC"
    await session.flush()


class TestDoctorSeamIsNowLive:
    """The cross-module payoff: Doctor Management's two stubs finally work.

    Doctors shipped against ``NullBookedIntervalSource``, so its slot feed could
    never report ``booked`` and its FR-5 deletion guard could never fire. Now
    that Appointments provides the real source, the same doctor code —
    untouched — does both.
    """

    async def test_a_booked_appointment_shows_in_the_doctor_slot_feed(
        self,
        service: AppointmentService,
        doctor_service: DoctorService,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        """AC-2 of the *doctor* module: booked slots show correctly."""
        from app.schemas.doctor import SetAvailabilityRequest

        await _use_utc_timezone(db_session, hospital_id)
        patient_id, doctor_id = await _clinical(db_session, hospital_id)

        # Monday 09:00-10:00, four 15-minute slots.
        await doctor_service.set_availability(
            hospital_id,
            doctor_id,
            SetAvailabilityRequest.model_validate(
                {
                    "entries": [
                        {
                            "day_of_week": 0,
                            "start_time": "09:00:00",
                            "end_time": "10:00:00",
                            "slot_duration_minutes": 15,
                        }
                    ]
                }
            ),
            actor_id=actor_id,
        )

        before = await doctor_service.get_slots(hospital_id, doctor_id, BASE.date())
        assert [s.status.value for s in before.slots] == ["available"] * 4

        appointment, _ = await service.book_appointment(
            hospital_id,
            _request(patient_id, doctor_id, offset_minutes=15),
            idempotency_key="slot-feed-key",
            actor_id=actor_id,
            allow_override=True,
        )

        after = await doctor_service.get_slots(hospital_id, doctor_id, BASE.date())
        statuses = [s.status.value for s in after.slots]
        assert statuses == ["available", "booked", "available", "available"]

        # The booked slot carries its appointment, so the UI can link to it.
        booked_slot = next(s for s in after.slots if s.status.value == "booked")
        assert booked_slot.appointment_id == appointment.id

    async def test_cancelling_frees_the_slot_in_the_doctor_feed(
        self,
        service: AppointmentService,
        doctor_service: DoctorService,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        """A cancelled appointment must not keep a slot greyed out."""
        from app.schemas.doctor import SetAvailabilityRequest

        await _use_utc_timezone(db_session, hospital_id)
        patient_id, doctor_id = await _clinical(db_session, hospital_id)
        await doctor_service.set_availability(
            hospital_id,
            doctor_id,
            SetAvailabilityRequest.model_validate(
                {
                    "entries": [
                        {
                            "day_of_week": 0,
                            "start_time": "09:00:00",
                            "end_time": "09:15:00",
                            "slot_duration_minutes": 15,
                        }
                    ]
                }
            ),
            actor_id=actor_id,
        )
        appointment, _ = await service.book_appointment(
            hospital_id,
            _request(patient_id, doctor_id),
            idempotency_key="free-slot-key",
            actor_id=actor_id,
            allow_override=True,
        )
        assert (await doctor_service.get_slots(hospital_id, doctor_id, BASE.date())).slots[
            0
        ].status.value == "booked"

        await service.cancel(hospital_id, appointment.id, build_cancel_request(), actor_id=actor_id)

        assert (await doctor_service.get_slots(hospital_id, doctor_id, BASE.date())).slots[
            0
        ].status.value == "available"

    async def test_doctor_with_future_appointments_cannot_be_deactivated(
        self,
        service: AppointmentService,
        doctor_service: DoctorService,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        """FR-5 and AC-3 of the *doctor* module, finally enforceable."""
        patient_id, doctor_id = await _clinical(db_session, hospital_id)
        await service.book_appointment(
            hospital_id,
            _request(patient_id, doctor_id),
            idempotency_key="guard-key",
            actor_id=actor_id,
            allow_override=True,
        )

        with pytest.raises(DoctorHasAppointmentsError) as exc:
            await doctor_service.deactivate_doctor(hospital_id, doctor_id, actor_id=actor_id)

        assert exc.value.status_code == 409
        assert exc.value.detail["future_appointments"] == 1

    async def test_cancelling_releases_the_doctor_for_deactivation(
        self,
        service: AppointmentService,
        doctor_service: DoctorService,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        """The guard's other branch: nothing outstanding, so deactivation proceeds."""
        patient_id, doctor_id = await _clinical(db_session, hospital_id)
        appointment, _ = await service.book_appointment(
            hospital_id,
            _request(patient_id, doctor_id),
            idempotency_key="release-key",
            actor_id=actor_id,
            allow_override=True,
        )
        await service.cancel(hospital_id, appointment.id, build_cancel_request(), actor_id=actor_id)

        result = await doctor_service.deactivate_doctor(hospital_id, doctor_id, actor_id=actor_id)
        assert result.status == "inactive"
