"""Integration tests for the Doctor Management module.

Real database, real repositories, real services — only the audit sink and the
appointments seam are doubles (``docs/11-TESTING_STRATEGY.md`` §2.4, §5).

Covers the workflow module spec §16 asks for — onboard → set availability →
request leave → read slots → deactivate — plus the cross-module assertion that
matters most in this PR: **the Department module's rule-13 guard is now live**,
because Doctor Management supplies the usage source it was written against.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from app.repositories.department_repository import DepartmentRepository
from app.repositories.doctor_repository import DoctorRepository
from app.repositories.hospital_repository import HospitalRepository
from app.repositories.user_repository import UserRepository
from app.schemas.department import CreateDepartmentRequest
from app.services.department_service import DepartmentInUseError, DepartmentService
from app.services.doctor_service import (
    BookedInterval,
    DoctorDepartmentUsageSource,
    DoctorHasAppointmentsError,
    DoctorService,
    NullBookedIntervalSource,
)
from app.tests.factories import (
    build_create_doctor_request,
    build_leave_request,
    build_set_availability_request,
    build_update_doctor_request,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.tests.conftest import RecordingAuditSink

pytestmark = pytest.mark.database


class _BusyBookedSource:
    """A booked-interval source reporting future appointments."""

    def __init__(self, count: int) -> None:
        self.count = count

    async def booked_intervals(self, *args: object, **kwargs: object) -> list[BookedInterval]:
        """No intervals needed for the deactivation guard."""
        return []

    async def has_future_appointments(self, *args: object, **kwargs: object) -> int:
        """Report the configured count."""
        return self.count


@pytest.fixture
def doctors_repo(db_session: AsyncSession) -> DoctorRepository:
    """Doctor repository on the transactional test session."""
    return DoctorRepository(db_session)


@pytest.fixture
def service(
    db_session: AsyncSession, doctors_repo: DoctorRepository, audit_sink: RecordingAuditSink
) -> DoctorService:
    """A fully wired :class:`DoctorService`."""
    return DoctorService(
        doctors_repo,
        UserRepository(db_session),
        DepartmentRepository(db_session),
        HospitalRepository(db_session),
        db_session,
        audit_sink,
        NullBookedIntervalSource(),
    )


@pytest.fixture
def department_service(
    db_session: AsyncSession, doctors_repo: DoctorRepository, audit_sink: RecordingAuditSink
) -> DepartmentService:
    """A :class:`DepartmentService` wired to the **real** usage source.

    This is the wiring that ships in ``app/api/dependencies/services.py`` now
    that Doctor Management exists.
    """
    return DepartmentService(
        DepartmentRepository(db_session),
        db_session,
        audit_sink,
        DoctorDepartmentUsageSource(doctors_repo),
    )


async def _make_user(session: AsyncSession, hospital_id: uuid.UUID) -> uuid.UUID:
    """Insert a user for a doctor profile to attach to."""
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        hospital_id=hospital_id,
        email=f"int-{uuid.uuid4().hex[:12]}@hospital.test",
        password_hash="test-placeholder-not-a-hash",
        first_name="Asha",
        last_name="Menon",
    )
    session.add(user)
    await session.flush()
    return user.id


async def test_full_lifecycle(
    service: DoctorService,
    db_session: AsyncSession,
    hospital_id: uuid.UUID,
    actor_id: uuid.UUID,
    audit_sink: RecordingAuditSink,
) -> None:
    """Onboard → availability → leave → slots → deactivate, end to end.

    One test because the value is in the *sequence*: each step depends on the
    previous one's persisted state, which per-step tests cannot cover.
    """
    user_id = await _make_user(db_session, hospital_id)

    # ── Onboard ─────────────────────────────────────────────────────────────
    doctor = await service.create_doctor(
        hospital_id,
        build_create_doctor_request(user_id=str(user_id), consultation_fee="800.00"),
        actor_id=actor_id,
    )
    assert doctor.full_name == "Asha Menon"
    assert doctor.consultation_fee == Decimal("800.00")
    assert doctor.status == "active"

    # ── Availability: Monday 09:00-10:00, 15-minute slots ───────────────────
    windows = await service.set_availability(
        hospital_id,
        doctor.id,
        build_set_availability_request(
            entries=[
                {
                    "day_of_week": 0,
                    "start_time": "09:00:00",
                    "end_time": "10:00:00",
                    "slot_duration_minutes": 15,
                }
            ]
        ),
        actor_id=actor_id,
    )
    assert [(w.day_of_week, w.slot_duration_minutes) for w in windows] == [(0, 15)]

    # ── Slots before any leave: four available ──────────────────────────────
    monday = date(2026, 8, 17)
    slots = await service.get_slots(hospital_id, doctor.id, monday)
    assert len(slots.slots) == 4
    assert {s.status for s in slots.slots} == {"available"}

    # ── Leave covering the second slot (09:15-09:30 IST = 03:45-04:00 UTC) ──
    leave, affected = await service.create_leave(
        hospital_id,
        doctor.id,
        build_leave_request(
            starts_at="2026-08-17T03:45:00+00:00", ends_at="2026-08-17T04:00:00+00:00"
        ),
        actor_id=actor_id,
    )
    assert affected == []  # no appointments module yet

    # ── Slots now show the leave (AC-2) ─────────────────────────────────────
    slots = await service.get_slots(hospital_id, doctor.id, monday)
    assert [s.status.value for s in slots.slots] == [
        "available",
        "on_leave",
        "available",
        "available",
    ]

    # ── Cancelling the leave frees the slot again ───────────────────────────
    await service.delete_leave(hospital_id, doctor.id, leave.id, actor_id=actor_id)
    slots = await service.get_slots(hospital_id, doctor.id, monday)
    assert {s.status for s in slots.slots} == {"available"}

    # ── Update, then deactivate ─────────────────────────────────────────────
    updated = await service.update_doctor(
        hospital_id,
        doctor.id,
        build_update_doctor_request(consultation_fee="950.00"),
        actor_id=actor_id,
    )
    assert updated.consultation_fee == Decimal("950.00")

    deactivated = await service.deactivate_doctor(hospital_id, doctor.id, actor_id=actor_id)
    assert deactivated.status == "inactive"

    listed = await service.list_doctors(hospital_id)
    assert listed.total_records == 0

    # ── The audit trail records the whole story, in order ───────────────────
    assert audit_sink.actions() == [
        "doctor.created",
        "doctor.availability_updated",
        "doctor.leave_created",
        "doctor.leave_deleted",
        "doctor.updated",
        "doctor.deactivated",
    ]
    assert all(event.hospital_id == hospital_id for event in audit_sink.events)


async def test_availability_across_all_seven_days(
    service: DoctorService, db_session: AsyncSession, hospital_id: uuid.UUID, actor_id: uuid.UUID
) -> None:
    """AC-1: a doctor can set availability across all seven days."""
    user_id = await _make_user(db_session, hospital_id)
    doctor = await service.create_doctor(
        hospital_id, build_create_doctor_request(user_id=str(user_id)), actor_id=actor_id
    )

    windows = await service.set_availability(
        hospital_id,
        doctor.id,
        build_set_availability_request(
            entries=[
                {
                    "day_of_week": day,
                    "start_time": "09:00:00",
                    "end_time": "10:00:00",
                    "slot_duration_minutes": 30,
                }
                for day in range(7)
            ]
        ),
        actor_id=actor_id,
    )

    assert [w.day_of_week for w in windows] == list(range(7))

    # Every weekday genuinely produces slots.
    for offset, expected_day in enumerate(range(7)):
        target = date(2026, 8, 17 + offset)  # 2026-08-17 is a Monday
        assert target.weekday() == expected_day
        slots = await service.get_slots(hospital_id, doctor.id, target)
        assert len(slots.slots) == 2


async def test_deactivation_blocked_by_future_appointments(
    db_session: AsyncSession,
    doctors_repo: DoctorRepository,
    audit_sink: RecordingAuditSink,
    hospital_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """AC-3 / FR-5 through the full stack, with a stand-in appointments source.

    This is the shape the Appointment Management adapter will have, so that PR
    swaps the source and leaves this test alone.
    """
    user_id = await _make_user(db_session, hospital_id)
    permissive = DoctorService(
        doctors_repo,
        UserRepository(db_session),
        DepartmentRepository(db_session),
        HospitalRepository(db_session),
        db_session,
        audit_sink,
        NullBookedIntervalSource(),
    )
    doctor = await permissive.create_doctor(
        hospital_id, build_create_doctor_request(user_id=str(user_id)), actor_id=actor_id
    )

    guarded = DoctorService(
        doctors_repo,
        UserRepository(db_session),
        DepartmentRepository(db_session),
        HospitalRepository(db_session),
        db_session,
        audit_sink,
        _BusyBookedSource(3),
    )

    with pytest.raises(DoctorHasAppointmentsError) as exc:
        await guarded.deactivate_doctor(hospital_id, doctor.id, actor_id=actor_id)

    assert exc.value.detail["future_appointments"] == 3
    # The refusal changed nothing.
    assert (await guarded.get_doctor_details(hospital_id, doctor.id)).status == "active"


async def test_tenant_isolation(
    service: DoctorService,
    db_session: AsyncSession,
    hospital_id: uuid.UUID,
    other_hospital_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """A doctor is invisible to another hospital through every read path."""
    from app.services.doctor_service import DoctorNotFoundError

    user_id = await _make_user(db_session, hospital_id)
    doctor = await service.create_doctor(
        hospital_id, build_create_doctor_request(user_id=str(user_id)), actor_id=actor_id
    )

    with pytest.raises(DoctorNotFoundError):
        await service.get_doctor_details(other_hospital_id, doctor.id)
    with pytest.raises(DoctorNotFoundError):
        await service.get_availability(other_hospital_id, doctor.id)
    with pytest.raises(DoctorNotFoundError):
        await service.get_slots(other_hospital_id, doctor.id, date(2026, 8, 17))
    assert (await service.list_doctors(other_hospital_id)).total_records == 0


class TestDepartmentGuardIsNowLive:
    """The cross-module payoff: Departments' rule 13 finally bites.

    The Department module shipped against ``NullDepartmentUsageSource`` and
    could never actually refuse a deactivation. Now that Doctor Management
    provides :class:`DoctorDepartmentUsageSource`, the same department code —
    untouched — enforces the rule.
    """

    async def test_department_with_an_assigned_doctor_cannot_be_deactivated(
        self,
        service: DoctorService,
        department_service: DepartmentService,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        department = await department_service.create_department(
            hospital_id,
            CreateDepartmentRequest.model_validate({"code": "CARD", "name": "Cardiology"}),
            actor_id=actor_id,
        )
        user_id = await _make_user(db_session, hospital_id)
        doctor = await service.create_doctor(
            hospital_id,
            build_create_doctor_request(user_id=str(user_id), department_id=str(department.id)),
            actor_id=actor_id,
        )
        assert doctor.department_id == department.id
        assert doctor.department_name == "Cardiology"

        with pytest.raises(DepartmentInUseError) as exc:
            await department_service.deactivate_department(
                hospital_id, department.id, actor_id=actor_id
            )

        assert exc.value.detail["assigned_doctors"] == 1
        assert exc.value.status_code == 409

    async def test_deactivating_the_doctor_releases_the_department(
        self,
        service: DoctorService,
        department_service: DepartmentService,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        """The guard's other branch, reached by clearing the assignment."""
        department = await department_service.create_department(
            hospital_id,
            CreateDepartmentRequest.model_validate({"code": "ORTH", "name": "Orthopaedics"}),
            actor_id=actor_id,
        )
        user_id = await _make_user(db_session, hospital_id)
        doctor = await service.create_doctor(
            hospital_id,
            build_create_doctor_request(user_id=str(user_id), department_id=str(department.id)),
            actor_id=actor_id,
        )

        await service.deactivate_doctor(hospital_id, doctor.id, actor_id=actor_id)

        result = await department_service.deactivate_department(
            hospital_id, department.id, actor_id=actor_id
        )
        assert result.status == "inactive"

    async def test_empty_department_still_deactivates(
        self,
        department_service: DepartmentService,
        hospital_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        """A department with no doctors is unaffected by the now-live guard."""
        department = await department_service.create_department(
            hospital_id,
            CreateDepartmentRequest.model_validate({"code": "EMPTY", "name": "Empty Unit"}),
            actor_id=actor_id,
        )

        result = await department_service.deactivate_department(
            hospital_id, department.id, actor_id=actor_id
        )
        assert result.status == "inactive"


async def test_leave_stored_in_utc_regardless_of_submitted_offset(
    service: DoctorService, db_session: AsyncSession, hospital_id: uuid.UUID, actor_id: uuid.UUID
) -> None:
    """CLAUDE.md rule 7: convert at the edge, store UTC."""
    user_id = await _make_user(db_session, hospital_id)
    doctor = await service.create_doctor(
        hospital_id, build_create_doctor_request(user_id=str(user_id)), actor_id=actor_id
    )

    leave, _ = await service.create_leave(
        hospital_id,
        doctor.id,
        build_leave_request(
            starts_at="2026-08-15T05:30:00+05:30", ends_at="2026-08-16T05:30:00+05:30"
        ),
        actor_id=actor_id,
    )

    assert leave.starts_at.astimezone(UTC) == datetime(2026, 8, 15, 0, 0, tzinfo=UTC)
    assert leave.ends_at.astimezone(UTC) == datetime(2026, 8, 16, 0, 0, tzinfo=UTC)
