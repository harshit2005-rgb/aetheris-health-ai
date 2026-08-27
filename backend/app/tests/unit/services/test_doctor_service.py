"""Unit tests for :class:`~app.services.doctor_service.DoctorService`.

Repositories are mocked; no database (``docs/11-TESTING_STRATEGY.md`` §2.1).
Every service method gets a happy path and an error path, and every mutation
asserts its audit event fired — both required by the backend Definition of Done.

The appointments seam is driven through a stub
:class:`~app.services.doctor_service.BookedIntervalSource` in both directions,
so the FR-5 deletion guard is proven now rather than when Appointments ships.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ValidationError
from app.services.doctor_service import (
    BookedInterval,
    DoctorAlreadyActiveError,
    DoctorDepartmentUsageSource,
    DoctorHasAppointmentsError,
    DoctorNotDeactivatedError,
    DoctorNotFoundError,
    DoctorService,
    DuplicateDoctorProfileError,
    LeaveNotFoundError,
    NullBookedIntervalSource,
    OverlappingLeaveError,
)
from app.tests.conftest import FakeSession, RecordingAuditSink
from app.tests.factories import (
    build_create_doctor_request,
    build_doctor_model,
    build_leave_model,
    build_leave_request,
    build_set_availability_request,
    build_update_doctor_request,
)

if TYPE_CHECKING:
    from app.models.doctor import Doctor

HOSPITAL_ID = uuid.uuid4()
ACTOR_ID = uuid.uuid4()


class StubBookedSource:
    """A :class:`BookedIntervalSource` with a fixed calendar.

    Stands in for the Appointment Management adapter that does not exist yet,
    which is what makes both branches of the FR-5 guard reachable today.
    """

    def __init__(self, *, future_count: int = 0, intervals: list[BookedInterval] | None = None):
        self.future_count = future_count
        self.intervals = intervals or []

    async def booked_intervals(
        self,
        hospital_id: uuid.UUID,
        doctor_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> list[BookedInterval]:
        """Return the configured intervals."""
        return self.intervals

    async def has_future_appointments(
        self, hospital_id: uuid.UUID, doctor_id: uuid.UUID, *, after: datetime
    ) -> int:
        """Return the configured future count."""
        return self.future_count


def _user(**overrides: object) -> AsyncMock:
    """Build a stand-in user object with the attributes the service reads."""
    user = AsyncMock()
    user.hospital_id = overrides.get("hospital_id", HOSPITAL_ID)
    user.first_name = "Asha"
    user.last_name = "Menon"
    user.email = "asha@hospital.test"
    return user


def _make_service(
    doctors: AsyncMock,
    *,
    users: AsyncMock | None = None,
    departments: AsyncMock | None = None,
    hospitals: AsyncMock | None = None,
    booked: StubBookedSource | None = None,
) -> tuple[DoctorService, FakeSession, RecordingAuditSink]:
    """Assemble a service over mocked collaborators."""
    session = FakeSession()
    audit = RecordingAuditSink()

    # Only supply a default user when the caller did not pass a repository at
    # all. Inspecting `return_value` to decide would clobber a caller that
    # deliberately set it to None (the "unknown user" case) or to a user in
    # another tenant — both of which are exactly what some tests are asserting.
    if users is None:
        users = AsyncMock()
        users.get_by_id.return_value = _user()

    departments = departments or AsyncMock()
    hospitals = hospitals or AsyncMock()

    service = DoctorService(
        doctors,
        users,
        departments,
        hospitals,
        session,  # type: ignore[arg-type]
        audit,
        booked or StubBookedSource(),
    )
    return service, session, audit


@pytest.fixture
def doctors() -> AsyncMock:
    """A mocked doctor repository with no-collision defaults."""
    repo = AsyncMock()
    repo.get_doctor_by_user_id.return_value = None
    repo.find_overlapping_leaves.return_value = []
    return repo


def _attach_user(doctor: Doctor) -> Doctor:
    """Give a detached Doctor the ``user``/``department`` a DTO reads.

    ``DoctorResponse.from_model`` reads both relationships; on an instance that
    was never loaded from the database they are unset, so tests populate them.
    """
    doctor.user = _user()
    doctor.department = None
    return doctor


# ── create_doctor ───────────────────────────────────────────────────────────


async def test_create_doctor_persists_and_audits(doctors: AsyncMock) -> None:
    """Happy path: written, committed, audited."""
    created = _attach_user(build_doctor_model(hospital_id=HOSPITAL_ID))
    doctors.create_doctor.return_value = created
    service, session, audit = _make_service(doctors)

    result = await service.create_doctor(
        HOSPITAL_ID, build_create_doctor_request(), actor_id=ACTOR_ID
    )

    assert result.specialization == "Cardiology"
    assert session.commits == 1
    assert audit.actions() == ["doctor.created"]
    assert audit.last().actor_id == ACTOR_ID


async def test_create_doctor_rejects_user_from_another_tenant(doctors: AsyncMock) -> None:
    """A user in another hospital is 'not found', never confirmed to exist."""
    users = AsyncMock()
    users.get_by_id.return_value = _user(hospital_id=uuid.uuid4())
    service, session, _ = _make_service(doctors, users=users)

    with pytest.raises(ValidationError):
        await service.create_doctor(HOSPITAL_ID, build_create_doctor_request())

    doctors.create_doctor.assert_not_awaited()
    assert session.commits == 0


async def test_create_doctor_rejects_unknown_user(doctors: AsyncMock) -> None:
    """A user that does not exist fails validation, not the database."""
    users = AsyncMock()
    users.get_by_id.return_value = None
    service, _, _ = _make_service(doctors, users=users)

    with pytest.raises(ValidationError):
        await service.create_doctor(HOSPITAL_ID, build_create_doctor_request())


async def test_create_doctor_rejects_second_profile_for_a_user(doctors: AsyncMock) -> None:
    """Module spec §4 rule 1: one doctor row per user."""
    doctors.get_doctor_by_user_id.return_value = build_doctor_model()
    service, session, audit = _make_service(doctors)

    with pytest.raises(DuplicateDoctorProfileError):
        await service.create_doctor(HOSPITAL_ID, build_create_doctor_request())

    doctors.create_doctor.assert_not_awaited()
    assert session.commits == 0
    assert audit.events == []


async def test_create_doctor_rejects_department_from_another_tenant(
    doctors: AsyncMock,
) -> None:
    """A department id must resolve inside the caller's hospital."""
    departments = AsyncMock()
    departments.get_department_by_id.return_value = None
    service, session, _ = _make_service(doctors, departments=departments)

    with pytest.raises(ValidationError) as exc:
        await service.create_doctor(
            HOSPITAL_ID, build_create_doctor_request(department_id=str(uuid.uuid4()))
        )

    assert exc.value.detail["errors"][0]["field"] == "department_id"
    assert session.commits == 0


async def test_create_doctor_preserves_decimal_fee(doctors: AsyncMock) -> None:
    """The fee reaches the repository as Decimal, never float or str."""
    doctors.create_doctor.return_value = _attach_user(build_doctor_model())
    service, _, _ = _make_service(doctors)

    await service.create_doctor(
        HOSPITAL_ID, build_create_doctor_request(consultation_fee="1234.56")
    )

    fee = doctors.create_doctor.await_args.kwargs["consultation_fee"]
    assert isinstance(fee, Decimal)
    assert fee == Decimal("1234.56")


# ── update_doctor ───────────────────────────────────────────────────────────


async def test_update_doctor_applies_only_sent_fields(doctors: AsyncMock) -> None:
    existing = _attach_user(build_doctor_model(hospital_id=HOSPITAL_ID))
    doctors.get_doctor_by_id.return_value = existing
    doctors.update_doctor.return_value = existing
    service, session, audit = _make_service(doctors)

    await service.update_doctor(
        HOSPITAL_ID, existing.id, build_update_doctor_request(bio="Updated bio"), actor_id=ACTOR_ID
    )

    assert set(doctors.update_doctor.await_args.kwargs) == {"bio", "updated_by"}
    assert session.commits == 1
    assert audit.actions() == ["doctor.updated"]


async def test_update_doctor_noop_does_not_write(doctors: AsyncMock) -> None:
    """Re-sending an unchanged value is not an edit."""
    existing = _attach_user(build_doctor_model(hospital_id=HOSPITAL_ID, bio="Same"))
    doctors.get_doctor_by_id.return_value = existing
    service, session, audit = _make_service(doctors)

    await service.update_doctor(HOSPITAL_ID, existing.id, build_update_doctor_request(bio="Same"))

    doctors.update_doctor.assert_not_awaited()
    assert session.commits == 0
    assert audit.events == []


async def test_update_doctor_missing_raises_not_found(doctors: AsyncMock) -> None:
    doctors.get_doctor_by_id.return_value = None
    service, _, _ = _make_service(doctors)

    with pytest.raises(DoctorNotFoundError):
        await service.update_doctor(HOSPITAL_ID, uuid.uuid4(), build_update_doctor_request(bio="x"))


# ── deactivate: the FR-5 guard, both branches ───────────────────────────────


async def test_deactivate_doctor_succeeds_with_no_future_appointments(
    doctors: AsyncMock,
) -> None:
    """Guard clears: nothing booked ahead, so the soft delete proceeds."""
    existing = _attach_user(build_doctor_model(hospital_id=HOSPITAL_ID))
    doctors.get_doctor_by_id.return_value = existing
    doctors.delete_doctor.return_value = existing
    service, session, audit = _make_service(doctors, booked=StubBookedSource(future_count=0))

    await service.deactivate_doctor(HOSPITAL_ID, existing.id, actor_id=ACTOR_ID)

    doctors.delete_doctor.assert_awaited_once()
    assert session.commits == 1
    assert audit.actions() == ["doctor.deactivated"]


async def test_deactivate_doctor_blocked_by_future_appointments(doctors: AsyncMock) -> None:
    """Guard triggers: FR-5 refuses with 409 and changes nothing."""
    existing = _attach_user(build_doctor_model(hospital_id=HOSPITAL_ID))
    doctors.get_doctor_by_id.return_value = existing
    service, session, audit = _make_service(doctors, booked=StubBookedSource(future_count=4))

    with pytest.raises(DoctorHasAppointmentsError) as exc:
        await service.deactivate_doctor(HOSPITAL_ID, existing.id, actor_id=ACTOR_ID)

    assert exc.value.status_code == 409
    assert exc.value.detail["future_appointments"] == 4
    doctors.delete_doctor.assert_not_awaited()
    assert session.commits == 0
    assert audit.events == []


async def test_deactivate_doctor_twice_is_rejected(doctors: AsyncMock) -> None:
    existing = build_doctor_model(
        hospital_id=HOSPITAL_ID, deleted_at=datetime(2026, 7, 30, tzinfo=UTC)
    )
    doctors.get_doctor_by_id.return_value = _attach_user(existing)
    service, session, _ = _make_service(doctors)

    with pytest.raises(DoctorNotDeactivatedError):
        await service.deactivate_doctor(HOSPITAL_ID, existing.id)

    assert session.commits == 0


async def test_activate_doctor_restores(doctors: AsyncMock) -> None:
    existing = build_doctor_model(
        hospital_id=HOSPITAL_ID, deleted_at=datetime(2026, 7, 30, tzinfo=UTC)
    )
    doctors.get_doctor_by_id.return_value = _attach_user(existing)
    doctors.restore_doctor.return_value = _attach_user(build_doctor_model(hospital_id=HOSPITAL_ID))
    service, session, audit = _make_service(doctors)

    await service.activate_doctor(HOSPITAL_ID, existing.id, actor_id=ACTOR_ID)

    assert session.commits == 1
    assert audit.actions() == ["doctor.activated"]


async def test_activate_an_active_doctor_is_rejected(doctors: AsyncMock) -> None:
    doctors.get_doctor_by_id.return_value = _attach_user(
        build_doctor_model(hospital_id=HOSPITAL_ID)
    )
    service, session, _ = _make_service(doctors)

    with pytest.raises(DoctorAlreadyActiveError):
        await service.activate_doctor(HOSPITAL_ID, uuid.uuid4())

    assert session.commits == 0


async def test_null_booked_source_reports_empty_calendar() -> None:
    """The interim source is what makes the guard inert today."""
    source = NullBookedIntervalSource()
    assert (
        await source.has_future_appointments(HOSPITAL_ID, uuid.uuid4(), after=datetime.now(UTC))
        == 0
    )
    assert (
        await source.booked_intervals(
            HOSPITAL_ID, uuid.uuid4(), datetime.now(UTC), datetime.now(UTC)
        )
        == []
    )


# ── Availability ────────────────────────────────────────────────────────────


async def test_set_availability_replaces_and_audits(doctors: AsyncMock) -> None:
    doctors.get_doctor_by_id.return_value = _attach_user(
        build_doctor_model(hospital_id=HOSPITAL_ID)
    )
    doctors.replace_availability.return_value = []
    service, session, audit = _make_service(doctors)

    await service.set_availability(
        HOSPITAL_ID, uuid.uuid4(), build_set_availability_request(), actor_id=ACTOR_ID
    )

    doctors.replace_availability.assert_awaited_once()
    assert session.commits == 1
    assert audit.actions() == ["doctor.availability_updated"]


async def test_set_availability_rejects_overlap_at_service_layer(doctors: AsyncMock) -> None:
    """The service re-asserts the overlap rule for non-HTTP callers.

    The schema would normally catch this, so a valid request is built and then
    mutated — simulating a seed script constructing the object directly.
    """
    doctors.get_doctor_by_id.return_value = _attach_user(
        build_doctor_model(hospital_id=HOSPITAL_ID)
    )
    payload = build_set_availability_request()
    # Two overlapping windows on the same day, bypassing schema validation.
    payload.entries[1].day_of_week = payload.entries[0].day_of_week
    payload.entries[1].start_time = payload.entries[0].start_time
    payload.entries[1].end_time = payload.entries[0].end_time

    service, session, _ = _make_service(doctors)

    with pytest.raises(ValidationError):
        await service.set_availability(HOSPITAL_ID, uuid.uuid4(), payload)

    doctors.replace_availability.assert_not_awaited()
    assert session.commits == 0


async def test_set_availability_for_missing_doctor_is_not_found(doctors: AsyncMock) -> None:
    doctors.get_doctor_by_id.return_value = None
    service, _, _ = _make_service(doctors)

    with pytest.raises(DoctorNotFoundError):
        await service.set_availability(HOSPITAL_ID, uuid.uuid4(), build_set_availability_request())


async def test_set_empty_availability_is_allowed(doctors: AsyncMock) -> None:
    """Clearing a schedule is a legitimate operation, not an empty-payload bug."""
    doctors.get_doctor_by_id.return_value = _attach_user(
        build_doctor_model(hospital_id=HOSPITAL_ID)
    )
    doctors.replace_availability.return_value = []
    service, session, _ = _make_service(doctors)

    result = await service.set_availability(
        HOSPITAL_ID, uuid.uuid4(), build_set_availability_request(entries=[])
    )

    assert result == []
    assert session.commits == 1


# ── Leaves ──────────────────────────────────────────────────────────────────


async def test_create_leave_persists_and_audits(doctors: AsyncMock) -> None:
    doctors.get_doctor_by_id.return_value = _attach_user(
        build_doctor_model(hospital_id=HOSPITAL_ID)
    )
    doctors.create_leave.return_value = build_leave_model(hospital_id=HOSPITAL_ID)
    service, session, audit = _make_service(doctors)

    leave, affected = await service.create_leave(
        HOSPITAL_ID, uuid.uuid4(), build_leave_request(), actor_id=ACTOR_ID
    )

    assert leave.reason == "Conference"
    assert affected == []
    assert session.commits == 1
    assert audit.actions() == ["doctor.leave_created"]


async def test_create_leave_rejects_overlap(doctors: AsyncMock) -> None:
    """Module spec §14 MVP branch: overlapping leaves are rejected, not merged."""
    doctors.get_doctor_by_id.return_value = _attach_user(
        build_doctor_model(hospital_id=HOSPITAL_ID)
    )
    doctors.find_overlapping_leaves.return_value = [build_leave_model()]
    service, session, audit = _make_service(doctors)

    with pytest.raises(OverlappingLeaveError) as exc:
        await service.create_leave(HOSPITAL_ID, uuid.uuid4(), build_leave_request())

    assert exc.value.status_code == 409
    assert len(exc.value.detail["conflicting_leaves"]) == 1
    doctors.create_leave.assert_not_awaited()
    assert session.commits == 0
    assert audit.events == []


async def test_create_leave_reports_affected_appointments(doctors: AsyncMock) -> None:
    """Module spec §5.3 step 3: the caller learns what needs reassigning."""
    doctors.get_doctor_by_id.return_value = _attach_user(
        build_doctor_model(hospital_id=HOSPITAL_ID)
    )
    doctors.create_leave.return_value = build_leave_model(hospital_id=HOSPITAL_ID)
    appointment_id = uuid.uuid4()
    booked = StubBookedSource(
        intervals=[
            BookedInterval(
                datetime(2026, 8, 16, 9, tzinfo=UTC),
                datetime(2026, 8, 16, 9, 30, tzinfo=UTC),
                appointment_id,
            )
        ]
    )
    service, _, audit = _make_service(doctors, booked=booked)

    _, affected = await service.create_leave(
        HOSPITAL_ID, uuid.uuid4(), build_leave_request(), actor_id=ACTOR_ID
    )

    assert [a["appointment_id"] for a in affected] == [str(appointment_id)]
    assert audit.last().context["affected_appointments"] == 1


async def test_create_leave_normalises_to_utc(doctors: AsyncMock) -> None:
    """An offset-carrying timestamp is stored as the equivalent UTC instant."""
    doctors.get_doctor_by_id.return_value = _attach_user(
        build_doctor_model(hospital_id=HOSPITAL_ID)
    )
    doctors.create_leave.return_value = build_leave_model(hospital_id=HOSPITAL_ID)
    service, _, _ = _make_service(doctors)

    await service.create_leave(
        HOSPITAL_ID,
        uuid.uuid4(),
        build_leave_request(
            starts_at="2026-08-15T05:30:00+05:30", ends_at="2026-08-16T05:30:00+05:30"
        ),
    )

    stored_start = doctors.create_leave.await_args.kwargs["starts_at"]
    assert stored_start == datetime(2026, 8, 15, 0, 0, tzinfo=UTC)


async def test_delete_leave_soft_deletes_and_audits(doctors: AsyncMock) -> None:
    doctors.get_doctor_by_id.return_value = _attach_user(
        build_doctor_model(hospital_id=HOSPITAL_ID)
    )
    doctors.get_leave_by_id.return_value = build_leave_model(hospital_id=HOSPITAL_ID)
    service, session, audit = _make_service(doctors)

    await service.delete_leave(HOSPITAL_ID, uuid.uuid4(), uuid.uuid4(), actor_id=ACTOR_ID)

    doctors.delete_leave.assert_awaited_once()
    assert session.commits == 1
    assert audit.actions() == ["doctor.leave_deleted"]


async def test_delete_unknown_leave_is_not_found(doctors: AsyncMock) -> None:
    doctors.get_doctor_by_id.return_value = _attach_user(
        build_doctor_model(hospital_id=HOSPITAL_ID)
    )
    doctors.get_leave_by_id.return_value = None
    service, session, _ = _make_service(doctors)

    with pytest.raises(LeaveNotFoundError):
        await service.delete_leave(HOSPITAL_ID, uuid.uuid4(), uuid.uuid4())

    assert session.commits == 0


# ── The departments seam, now implemented ───────────────────────────────────


async def test_doctor_department_usage_source_delegates_to_the_count_query() -> None:
    """The adapter Departments has been waiting for since it shipped.

    It satisfies ``DepartmentUsageSource`` structurally — no import from the
    department module, no inheritance — which is what lets the department guard
    activate by swapping one DI provider.
    """
    from app.services.department_service import DepartmentUsageSource

    repo = AsyncMock()
    repo.count_active_by_department.return_value = 3
    source = DoctorDepartmentUsageSource(repo)

    assert isinstance(source, DepartmentUsageSource)

    department_id = uuid.uuid4()
    assert await source.active_doctor_count(HOSPITAL_ID, department_id) == 3
    repo.count_active_by_department.assert_awaited_once_with(HOSPITAL_ID, department_id)
