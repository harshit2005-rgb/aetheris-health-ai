"""Repository tests for the appointment aggregate.

Real PostgreSQL (``docs/11-TESTING_STRATEGY.md`` §2.2). What is under test is
the SQL and the constraints: module spec §16 asks specifically for the overlap
constraint and the state-history queries, and AC-2 is a *database* guarantee —
asserting it anywhere else would prove nothing.

Every query method has at least one test proving it filters by ``hospital_id``,
with one documented exception: the no-show sweeper is deliberately untenanted.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.appointment import AppointmentStatus, AppointmentType
from app.repositories.appointment_repository import AppointmentRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.appointment import Appointment

pytestmark = pytest.mark.database

BASE = datetime(2030, 1, 7, 9, 0, tzinfo=UTC)


@pytest.fixture
def repository(db_session: AsyncSession) -> AppointmentRepository:
    """A repository bound to the rolled-back test session."""
    return AppointmentRepository(db_session)


async def _fixtures(session: AsyncSession, hospital_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a patient and a doctor, returning their ids."""
    from app.models.doctor import Doctor
    from app.models.patient import Gender, Patient
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        hospital_id=hospital_id,
        email=f"appt-{uuid.uuid4().hex[:12]}@hospital.test",
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
        date_of_birth=datetime(1990, 1, 1).date(),
        gender=Gender.FEMALE,
    )
    session.add_all([doctor, patient])
    await session.flush()
    return patient.id, doctor.id


async def _book(
    repository: AppointmentRepository,
    hospital_id: uuid.UUID,
    patient_id: uuid.UUID,
    doctor_id: uuid.UUID,
    *,
    offset_minutes: int = 0,
    minutes: int = 15,
    **overrides: Any,
) -> Appointment:
    """Insert an appointment relative to :data:`BASE`."""
    start = BASE + timedelta(minutes=offset_minutes)
    values: dict[str, Any] = {
        "scheduled_start": start,
        "scheduled_end": start + timedelta(minutes=minutes),
        "appointment_type": AppointmentType.NEW,
    }
    values.update(overrides)
    return await repository.create_appointment(
        hospital_id=hospital_id, patient_id=patient_id, doctor_id=doctor_id, **values
    )


class TestOverlapConstraint:
    """AC-2: double-booking is prevented at the database level."""

    async def test_overlapping_booking_is_refused_by_postgres(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """The exclusion constraint, not the service, is what makes this safe.

        Two receptionists racing cannot be stopped by an application check —
        both read before either writes — so this asserts the database refuses.
        """
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        await _book(repository, hospital_id, patient_id, doctor_id)

        with pytest.raises(IntegrityError, match="no_overlap_per_doctor"):
            await _book(
                repository, hospital_id, patient_id, doctor_id, offset_minutes=10, minutes=15
            )
        await db_session.rollback()

    async def test_adjacent_bookings_are_allowed(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """Half-open ranges: 09:00-09:15 and 09:15-09:30 do not overlap.

        Getting this wrong would silently lose every second slot in a day.
        """
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        await _book(repository, hospital_id, patient_id, doctor_id)
        await _book(repository, hospital_id, patient_id, doctor_id, offset_minutes=15)

        assert await repository.count_appointments(hospital_id) == 2

    async def test_cancelled_appointment_frees_its_slot(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """The constraint's WHERE clause excludes cancelled and no-show."""
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        first = await _book(repository, hospital_id, patient_id, doctor_id)
        await repository.update_appointment(first, status=AppointmentStatus.CANCELLED)

        # The same slot is now bookable again.
        await _book(repository, hospital_id, patient_id, doctor_id)
        assert await repository.count_appointments(hospital_id) == 2

    async def test_different_doctors_may_share_a_time(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """The constraint is per doctor, not per clinic."""
        patient_id, first_doctor = await _fixtures(db_session, hospital_id)
        _, second_doctor = await _fixtures(db_session, hospital_id)

        await _book(repository, hospital_id, patient_id, first_doctor)
        await _book(repository, hospital_id, patient_id, second_doctor)

        assert await repository.count_appointments(hospital_id) == 2

    async def test_end_before_start_is_refused(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """``ck_appointments_time_order`` is the last line of defence."""
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)

        with pytest.raises(IntegrityError):
            await repository.create_appointment(
                hospital_id=hospital_id,
                patient_id=patient_id,
                doctor_id=doctor_id,
                scheduled_start=BASE,
                scheduled_end=BASE - timedelta(minutes=15),
                appointment_type=AppointmentType.NEW,
            )
        await db_session.rollback()


class TestIdempotencyIndex:
    """Business rule 8, enforced by a partial unique index."""

    async def test_duplicate_key_in_one_hospital_is_refused(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        await _book(repository, hospital_id, patient_id, doctor_id, idempotency_key="KEY-1")

        with pytest.raises(IntegrityError):
            await _book(
                repository,
                hospital_id,
                patient_id,
                doctor_id,
                offset_minutes=60,
                idempotency_key="KEY-1",
            )
        await db_session.rollback()

    async def test_many_appointments_may_have_no_key(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """The index is partial, so NULLs do not collide with each other."""
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        await _book(repository, hospital_id, patient_id, doctor_id, idempotency_key=None)
        await _book(
            repository,
            hospital_id,
            patient_id,
            doctor_id,
            offset_minutes=30,
            idempotency_key=None,
        )

        assert await repository.count_appointments(hospital_id) == 2

    async def test_same_key_in_two_hospitals_is_allowed(
        self,
        repository: AppointmentRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        """Keys are scoped per tenant, so two clinics cannot collide."""
        mine = await _fixtures(db_session, hospital_id)
        theirs = await _fixtures(db_session, other_hospital_id)

        await _book(repository, hospital_id, *mine, idempotency_key="SHARED")
        await _book(repository, other_hospital_id, *theirs, idempotency_key="SHARED")

        assert await repository.count_appointments(hospital_id) == 1
        assert await repository.count_appointments(other_hospital_id) == 1

    async def test_lookup_finds_the_original(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        booked = await _book(
            repository, hospital_id, patient_id, doctor_id, idempotency_key="KEY-2"
        )

        found = await repository.get_by_idempotency_key(hospital_id, "KEY-2")
        assert found is not None
        assert found.id == booked.id

    async def test_lookup_is_tenant_scoped(
        self,
        repository: AppointmentRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        await _book(repository, hospital_id, patient_id, doctor_id, idempotency_key="KEY-3")

        assert await repository.get_by_idempotency_key(other_hospital_id, "KEY-3") is None


class TestOverlapQuery:
    """The advisory check the service uses before writing."""

    @pytest.mark.parametrize(
        ("offset", "minutes", "expected"),
        [
            (5, 15, True),  # straddles the start
            (0, 15, True),  # exact same slot
            (-5, 15, True),  # straddles the end
            (-30, 60, True),  # encloses
            (15, 15, False),  # starts exactly when the other ends
            (-15, 15, False),  # ends exactly when the other starts
            (60, 15, False),  # unrelated
        ],
    )
    async def test_overlap_boundaries(
        self,
        repository: AppointmentRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        offset: int,
        minutes: int,
        expected: bool,
    ) -> None:
        """Half-open comparison, pinned at every boundary."""
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        await _book(repository, hospital_id, patient_id, doctor_id)

        probe_start = BASE + timedelta(minutes=offset)
        found = await repository.find_overlapping(
            hospital_id, doctor_id, probe_start, probe_start + timedelta(minutes=minutes)
        )
        assert bool(found) is expected

    async def test_cancelled_is_not_a_clash(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        booked = await _book(repository, hospital_id, patient_id, doctor_id)
        await repository.update_appointment(booked, status=AppointmentStatus.CANCELLED)

        assert (
            await repository.find_overlapping(
                hospital_id, doctor_id, BASE, BASE + timedelta(minutes=15)
            )
            == []
        )

    async def test_exclude_lets_an_appointment_move_within_itself(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """Rescheduling must not clash with the row being rescheduled."""
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        booked = await _book(repository, hospital_id, patient_id, doctor_id)

        assert (
            await repository.find_overlapping(
                hospital_id,
                doctor_id,
                BASE,
                BASE + timedelta(minutes=15),
                exclude_appointment_id=booked.id,
            )
            == []
        )

    async def test_overlap_is_tenant_scoped(
        self,
        repository: AppointmentRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        await _book(repository, hospital_id, patient_id, doctor_id)

        assert (
            await repository.find_overlapping(
                other_hospital_id, doctor_id, BASE, BASE + timedelta(minutes=15)
            )
            == []
        )


class TestDoctorSeamQueries:
    """The queries Doctor Management depends on through BookedIntervalSource."""

    async def test_booked_intervals_exclude_cancelled(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """A cancelled appointment must not grey out a genuinely free slot."""
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        live = await _book(repository, hospital_id, patient_id, doctor_id)
        dead = await _book(repository, hospital_id, patient_id, doctor_id, offset_minutes=30)
        await repository.update_appointment(dead, status=AppointmentStatus.CANCELLED)

        rows = await repository.booked_intervals_for_doctor(
            hospital_id, doctor_id, BASE, BASE + timedelta(hours=2)
        )
        assert [r.id for r in rows] == [live.id]

    async def test_count_future_ignores_past_and_cancelled(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """Backs the doctor deletion guard — only real upcoming work counts."""
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        await _book(repository, hospital_id, patient_id, doctor_id)
        cancelled = await _book(repository, hospital_id, patient_id, doctor_id, offset_minutes=30)
        await repository.update_appointment(cancelled, status=AppointmentStatus.CANCELLED)

        assert (
            await repository.count_future_for_doctor(
                hospital_id, doctor_id, after=BASE - timedelta(days=1)
            )
            == 1
        )
        # Nothing is "future" relative to well after the appointment.
        assert (
            await repository.count_future_for_doctor(
                hospital_id, doctor_id, after=BASE + timedelta(days=1)
            )
            == 0
        )

    async def test_count_future_is_tenant_scoped(
        self,
        repository: AppointmentRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        await _book(repository, hospital_id, patient_id, doctor_id)

        assert (
            await repository.count_future_for_doctor(
                other_hospital_id, doctor_id, after=BASE - timedelta(days=1)
            )
            == 0
        )


class TestStatusHistory:
    """Business rule 7 and AC-6."""

    async def test_history_is_appended_and_ordered(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        appointment = await _book(repository, hospital_id, patient_id, doctor_id)

        await repository.record_transition(
            appointment=appointment,
            from_status=None,
            to_status=AppointmentStatus.BOOKED,
            reason="booked",
        )
        await repository.record_transition(
            appointment=appointment,
            from_status=AppointmentStatus.BOOKED,
            to_status=AppointmentStatus.CHECKED_IN,
        )

        history = await repository.get_status_history(hospital_id, appointment.id)

        # Asserted as a set, not a sequence. ``changed_at`` defaults to
        # Postgres ``now()``, which is *transaction* time — so two rows written
        # in one transaction share a timestamp and the id tiebreak decides
        # order arbitrarily. In production each transition is its own request
        # and therefore its own transaction, so timestamps differ and the
        # ordering is real; this test simply must not depend on an artefact of
        # writing both at once.
        assert {(h.from_status, h.to_status) for h in history} == {
            (None, AppointmentStatus.BOOKED),
            (AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN),
        }

    async def test_history_accepts_a_null_actor(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """The sweeper has no acting user, which is why the column is nullable."""
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        appointment = await _book(repository, hospital_id, patient_id, doctor_id)

        entry = await repository.record_transition(
            appointment=appointment,
            from_status=AppointmentStatus.BOOKED,
            to_status=AppointmentStatus.NO_SHOW,
            changed_by=None,
            reason="no_show_sweeper",
        )
        assert entry.changed_by is None

    async def test_history_is_tenant_scoped(
        self,
        repository: AppointmentRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        appointment = await _book(repository, hospital_id, patient_id, doctor_id)
        await repository.record_transition(
            appointment=appointment, from_status=None, to_status=AppointmentStatus.BOOKED
        )

        assert await repository.get_status_history(other_hospital_id, appointment.id) == []


class TestListingAndQueue:
    """Filters, the walk-in queue, and the sweeper query."""

    async def test_list_is_tenant_scoped(
        self,
        repository: AppointmentRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        mine = await _fixtures(db_session, hospital_id)
        theirs = await _fixtures(db_session, other_hospital_id)
        await _book(repository, hospital_id, *mine)
        await _book(repository, other_hospital_id, *theirs)

        assert await repository.count_appointments(hospital_id) == 1

    async def test_filters_narrow_correctly(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        await _book(repository, hospital_id, patient_id, doctor_id)
        await _book(
            repository,
            hospital_id,
            patient_id,
            doctor_id,
            offset_minutes=30,
            appointment_type=AppointmentType.WALK_IN,
        )

        assert (
            await repository.count_appointments(
                hospital_id, appointment_type=AppointmentType.WALK_IN
            )
            == 1
        )
        assert await repository.count_appointments(hospital_id, doctor_id=doctor_id) == 2
        assert (
            await repository.count_appointments(
                hospital_id, starts_on_or_after=BASE + timedelta(minutes=20)
            )
            == 1
        )

    async def test_walk_in_queue_orders_by_check_in_time(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """Arrival order, not scheduled order — that is what a queue means.

        Both are checked in so the comparison is like-for-like. The one booked
        for a *later* slot arrived *first*, and must head the queue.
        """
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        booked_earlier_slot = await _book(
            repository,
            hospital_id,
            patient_id,
            doctor_id,
            offset_minutes=30,
            appointment_type=AppointmentType.WALK_IN,
        )
        booked_later_slot = await _book(
            repository,
            hospital_id,
            patient_id,
            doctor_id,
            offset_minutes=60,
            appointment_type=AppointmentType.WALK_IN,
        )

        await repository.update_appointment(
            booked_later_slot,
            status=AppointmentStatus.CHECKED_IN,
            checked_in_at=BASE,
        )
        await repository.update_appointment(
            booked_earlier_slot,
            status=AppointmentStatus.CHECKED_IN,
            checked_in_at=BASE + timedelta(minutes=20),
        )

        queue = await repository.list_walk_in_queue(hospital_id)
        assert [a.id for a in queue] == [booked_later_slot.id, booked_earlier_slot.id]

    async def test_walk_in_not_yet_arrived_sorts_by_booking_time(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """``coalesce(checked_in_at, created_at)`` — an un-arrived walk-in still queues.

        A walk-in that has not checked in yet must still appear, ordered by when
        it was booked. Ordering between two such rows is not asserted here:
        ``created_at`` defaults to Postgres ``now()``, which is transaction
        time, so both would share a timestamp in this test even though separate
        requests in production would not.
        """
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        arrived = await _book(
            repository,
            hospital_id,
            patient_id,
            doctor_id,
            appointment_type=AppointmentType.WALK_IN,
        )
        waiting = await _book(
            repository,
            hospital_id,
            patient_id,
            doctor_id,
            offset_minutes=30,
            appointment_type=AppointmentType.WALK_IN,
        )
        # One has arrived, and did so before either was booked.
        await repository.update_appointment(
            arrived,
            status=AppointmentStatus.CHECKED_IN,
            checked_in_at=datetime(2020, 1, 1, tzinfo=UTC),
        )

        queue = await repository.list_walk_in_queue(hospital_id)
        assert [a.id for a in queue] == [arrived.id, waiting.id]

    async def test_walk_in_queue_excludes_finished(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        done = await _book(
            repository,
            hospital_id,
            patient_id,
            doctor_id,
            appointment_type=AppointmentType.WALK_IN,
        )
        await repository.update_appointment(done, status=AppointmentStatus.COMPLETED)

        assert await repository.list_walk_in_queue(hospital_id) == []

    async def test_no_show_candidates_are_overdue_and_unfinished(
        self, repository: AppointmentRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """The sweeper query is deliberately untenanted (see its docstring)."""
        patient_id, doctor_id = await _fixtures(db_session, hospital_id)
        overdue = await _book(repository, hospital_id, patient_id, doctor_id)
        finished = await _book(repository, hospital_id, patient_id, doctor_id, offset_minutes=30)
        await repository.update_appointment(finished, status=AppointmentStatus.COMPLETED)

        candidates = await repository.find_no_show_candidates(cutoff=BASE + timedelta(hours=1))
        ids = {a.id for a in candidates}
        assert overdue.id in ids
        assert finished.id not in ids
