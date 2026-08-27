"""Repository tests for :class:`~app.repositories.doctor_repository.DoctorRepository`.

Real PostgreSQL (``docs/11-TESTING_STRATEGY.md`` §2.2), because what is under
test is the SQL: the tenant filter, the soft-delete filter, the unique
constraint on ``user_id``, the check constraints, the leave-overlap predicate,
and the atomic availability replace. None of that is observable through a mock.

Every query method has at least one test proving it filters by ``hospital_id``
(backend/CLAUDE.md, "Testing").
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.repositories.doctor_repository import DoctorRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.doctor import Doctor

pytestmark = pytest.mark.database


@pytest.fixture
def repository(db_session: AsyncSession) -> DoctorRepository:
    """A repository bound to the rolled-back test session."""
    return DoctorRepository(db_session)


async def _make_user(
    session: AsyncSession, hospital_id: uuid.UUID, *, first: str = "Asha", last: str = "Menon"
) -> uuid.UUID:
    """Insert a user to attach a doctor profile to."""
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        hospital_id=hospital_id,
        email=f"doc-{uuid.uuid4().hex[:12]}@hospital.test",
        password_hash="test-placeholder-not-a-hash",
        first_name=first,
        last_name=last,
    )
    session.add(user)
    await session.flush()
    return user.id


async def _make_department(
    session: AsyncSession, hospital_id: uuid.UUID, *, code: str | None = None
) -> uuid.UUID:
    """Insert a department to assign doctors to."""
    from app.models.department import Department

    department = Department(
        id=uuid.uuid4(),
        hospital_id=hospital_id,
        code=code or f"D{uuid.uuid4().hex[:6].upper()}",
        name=f"Dept {uuid.uuid4().hex[:8]}",
    )
    session.add(department)
    await session.flush()
    return department.id


async def _create(
    repository: DoctorRepository,
    session: AsyncSession,
    hospital_id: uuid.UUID,
    **overrides: Any,
) -> Doctor:
    """Insert a doctor with sensible defaults, overridable per test."""
    values: dict[str, Any] = {
        "specialization": "Cardiology",
        "license_number": f"LIC-{uuid.uuid4().hex[:8]}",
        "consultation_fee": Decimal("800.00"),
    }
    values.update(overrides)
    if "user_id" not in values:
        values["user_id"] = await _make_user(session, hospital_id)
    return await repository.create_doctor(hospital_id=hospital_id, **values)


class TestCreateAndRead:
    """Insertion and single-record retrieval."""

    async def test_create_persists_all_columns(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        department_id = await _make_department(db_session, hospital_id)
        doctor = await _create(
            repository,
            db_session,
            hospital_id,
            department_id=department_id,
            bio="Interventional cardiologist.",
            qualifications=[{"degree": "MBBS", "year": 2011}],
            languages=["English", "Telugu"],
        )

        assert doctor.id is not None
        assert doctor.specialization == "Cardiology"
        assert doctor.consultation_fee == Decimal("800.00")
        assert doctor.department_id == department_id
        assert doctor.qualifications == [{"degree": "MBBS", "year": 2011}]
        assert doctor.languages == ["English", "Telugu"]
        assert doctor.status == "active"

    async def test_consultation_fee_round_trips_as_decimal(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """NUMERIC(15,2), never float — money must not drift (CLAUDE.md rule 6)."""
        doctor = await _create(
            repository, db_session, hospital_id, consultation_fee=Decimal("1234.56")
        )
        assert isinstance(doctor.consultation_fee, Decimal)
        assert doctor.consultation_fee == Decimal("1234.56")

    async def test_get_by_id_is_tenant_scoped(
        self,
        repository: DoctorRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        doctor = await _create(repository, db_session, hospital_id)
        assert await repository.get_doctor_by_id(hospital_id, doctor.id) is not None
        assert await repository.get_doctor_by_id(other_hospital_id, doctor.id) is None

    async def test_get_by_id_excludes_soft_deleted_by_default(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        doctor = await _create(repository, db_session, hospital_id)
        await repository.delete_doctor(doctor)

        assert await repository.get_doctor_by_id(hospital_id, doctor.id) is None
        assert (
            await repository.get_doctor_by_id(hospital_id, doctor.id, include_deleted=True)
            is not None
        )


class TestConstraints:
    """Database-level guarantees."""

    async def test_one_doctor_row_per_user(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """``uq_doctors_user_id`` enforces module spec §4 rule 1."""
        user_id = await _make_user(db_session, hospital_id)
        await _create(repository, db_session, hospital_id, user_id=user_id)

        with pytest.raises(IntegrityError):
            await _create(repository, db_session, hospital_id, user_id=user_id)
        await db_session.rollback()

    async def test_get_by_user_id_sees_soft_deleted(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """A deactivated doctor still occupies their user.

        The unique constraint ignores soft-delete state, so a duplicate check
        that skipped deactivated rows would report the user as free and then
        hit a 500 from the database.
        """
        user_id = await _make_user(db_session, hospital_id)
        doctor = await _create(repository, db_session, hospital_id, user_id=user_id)
        await repository.delete_doctor(doctor)

        assert await repository.get_doctor_by_user_id(hospital_id, user_id) is not None

    async def test_availability_rejects_inverted_times(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """``ck_doctor_availability_time_order`` is the last line of defence."""
        doctor = await _create(repository, db_session, hospital_id)

        with pytest.raises((IntegrityError, DBAPIError)):
            await repository.replace_availability(
                hospital_id,
                doctor.id,
                [
                    {
                        "day_of_week": 0,
                        "start_time": time(12),
                        "end_time": time(9),
                        "slot_duration_minutes": 15,
                    }
                ],
            )
        await db_session.rollback()

    async def test_availability_rejects_unsupported_slot_duration(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """``ck_doctor_availability_slot_duration`` pins the allowed set."""
        doctor = await _create(repository, db_session, hospital_id)

        with pytest.raises((IntegrityError, DBAPIError)):
            await repository.replace_availability(
                hospital_id,
                doctor.id,
                [
                    {
                        "day_of_week": 0,
                        "start_time": time(9),
                        "end_time": time(12),
                        "slot_duration_minutes": 7,
                    }
                ],
            )
        await db_session.rollback()

    async def test_leave_rejects_inverted_range(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """``ck_doctor_leaves_range_order`` enforces ends_at > starts_at."""
        doctor = await _create(repository, db_session, hospital_id)

        with pytest.raises((IntegrityError, DBAPIError)):
            await repository.create_leave(
                hospital_id=hospital_id,
                doctor_id=doctor.id,
                starts_at=datetime(2026, 8, 18, tzinfo=UTC),
                ends_at=datetime(2026, 8, 15, tzinfo=UTC),
            )
        await db_session.rollback()


class TestListAndSearch:
    """Filtering, ordering, counting."""

    async def test_list_is_tenant_scoped(
        self,
        repository: DoctorRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        await _create(repository, db_session, hospital_id, specialization="Mine")
        await _create(repository, db_session, other_hospital_id, specialization="Theirs")

        rows = await repository.list_doctors(hospital_id)
        assert [r.specialization for r in rows] == ["Mine"]

    async def test_count_is_tenant_scoped(
        self,
        repository: DoctorRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        await _create(repository, db_session, hospital_id)
        await _create(repository, db_session, other_hospital_id)
        await _create(repository, db_session, other_hospital_id)

        assert await repository.count_doctors(hospital_id) == 1

    async def test_filter_by_specialization_is_case_insensitive(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        await _create(repository, db_session, hospital_id, specialization="Cardiology")
        await _create(repository, db_session, hospital_id, specialization="Orthopaedics")

        rows = await repository.list_doctors(hospital_id, specialization="cardiology")
        assert [r.specialization for r in rows] == ["Cardiology"]

    async def test_filter_by_department(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """The department filter module spec §9 asks for."""
        cardiology = await _make_department(db_session, hospital_id, code="CARD")
        ortho = await _make_department(db_session, hospital_id, code="ORTH")
        await _create(repository, db_session, hospital_id, department_id=cardiology)
        await _create(repository, db_session, hospital_id, department_id=ortho)
        await _create(repository, db_session, hospital_id)

        rows = await repository.list_doctors(hospital_id, department_id=cardiology)
        assert [r.department_id for r in rows] == [cardiology]

    async def test_search_by_name_prefix_joins_users(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """``q`` matches the doctor's name, which lives on ``users``."""
        asha = await _make_user(db_session, hospital_id, first="Asha", last="Menon")
        ravi = await _make_user(db_session, hospital_id, first="Ravi", last="Kumar")
        await _create(repository, db_session, hospital_id, user_id=asha)
        await _create(repository, db_session, hospital_id, user_id=ravi)

        rows = await repository.list_doctors(hospital_id, term="ash")
        assert [r.user_id for r in rows] == [asha]

        by_surname = await repository.list_doctors(hospital_id, term="kum")
        assert [r.user_id for r in by_surname] == [ravi]

    async def test_search_by_exact_license(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        doctor = await _create(repository, db_session, hospital_id, license_number="LIC-EXACT-1")
        await _create(repository, db_session, hospital_id)

        rows = await repository.list_doctors(hospital_id, term="LIC-EXACT-1")
        assert [r.id for r in rows] == [doctor.id]

    async def test_search_does_not_match_name_substring(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """Prefix-only, which is what keeps the index usable."""
        user_id = await _make_user(db_session, hospital_id, first="Asha", last="Menon")
        await _create(repository, db_session, hospital_id, user_id=user_id)

        assert await repository.list_doctors(hospital_id, term="sha") == []

    async def test_search_treats_wildcards_literally(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        await _create(repository, db_session, hospital_id)
        assert await repository.list_doctors(hospital_id, term="%") == []

    async def test_count_agrees_with_list(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """Identical filters, so a page total can never contradict its rows."""
        await _create(repository, db_session, hospital_id, specialization="Cardiology")
        await _create(repository, db_session, hospital_id, specialization="Cardiology")
        await _create(repository, db_session, hospital_id, specialization="Orthopaedics")

        rows = await repository.list_doctors(hospital_id, specialization="Cardiology")
        total = await repository.count_doctors(hospital_id, specialization="Cardiology")
        assert total == len(rows) == 2

    async def test_list_excludes_soft_deleted_by_default(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        keep = await _create(repository, db_session, hospital_id)
        drop = await _create(repository, db_session, hospital_id)
        await repository.delete_doctor(drop)

        assert [r.id for r in await repository.list_doctors(hospital_id)] == [keep.id]
        assert len(await repository.list_doctors(hospital_id, include_deleted=True)) == 2


class TestDepartmentUsageCount:
    """The query the Department module's guard depends on."""

    async def test_counts_only_active_doctors_in_the_department(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        department_id = await _make_department(db_session, hospital_id)
        await _create(repository, db_session, hospital_id, department_id=department_id)
        second = await _create(repository, db_session, hospital_id, department_id=department_id)
        await _create(repository, db_session, hospital_id)  # unassigned

        assert await repository.count_active_by_department(hospital_id, department_id) == 2

        # A deactivated doctor no longer blocks the department.
        await repository.delete_doctor(second)
        assert await repository.count_active_by_department(hospital_id, department_id) == 1

    async def test_count_is_tenant_scoped(
        self,
        repository: DoctorRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        department_id = await _make_department(db_session, hospital_id)
        await _create(repository, db_session, hospital_id, department_id=department_id)

        assert await repository.count_active_by_department(other_hospital_id, department_id) == 0


class TestAvailability:
    """Weekly schedule storage and atomic replacement."""

    async def test_replace_is_a_full_swap(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """Module spec §5.2: old rows go, new rows land, in one transaction."""
        doctor = await _create(repository, db_session, hospital_id)

        await repository.replace_availability(
            hospital_id,
            doctor.id,
            [
                {
                    "day_of_week": 0,
                    "start_time": time(9),
                    "end_time": time(12),
                    "slot_duration_minutes": 15,
                }
            ],
        )
        rows = await repository.replace_availability(
            hospital_id,
            doctor.id,
            [
                {
                    "day_of_week": 3,
                    "start_time": time(14),
                    "end_time": time(17),
                    "slot_duration_minutes": 30,
                }
            ],
        )

        assert [(r.day_of_week, r.slot_duration_minutes) for r in rows] == [(3, 30)]

    async def test_replace_with_empty_clears_everything(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        doctor = await _create(repository, db_session, hospital_id)
        await repository.replace_availability(
            hospital_id,
            doctor.id,
            [
                {
                    "day_of_week": 0,
                    "start_time": time(9),
                    "end_time": time(12),
                    "slot_duration_minutes": 15,
                }
            ],
        )

        assert await repository.replace_availability(hospital_id, doctor.id, []) == []

    async def test_availability_is_ordered_by_day_then_start(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        doctor = await _create(repository, db_session, hospital_id)
        await repository.replace_availability(
            hospital_id,
            doctor.id,
            [
                {
                    "day_of_week": 2,
                    "start_time": time(9),
                    "end_time": time(10),
                    "slot_duration_minutes": 15,
                },
                {
                    "day_of_week": 0,
                    "start_time": time(14),
                    "end_time": time(15),
                    "slot_duration_minutes": 15,
                },
                {
                    "day_of_week": 0,
                    "start_time": time(9),
                    "end_time": time(10),
                    "slot_duration_minutes": 15,
                },
            ],
        )

        rows = await repository.get_availability(hospital_id, doctor.id)
        assert [(r.day_of_week, r.start_time.hour) for r in rows] == [(0, 9), (0, 14), (2, 9)]

    async def test_availability_is_tenant_scoped(
        self,
        repository: DoctorRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        doctor = await _create(repository, db_session, hospital_id)
        await repository.replace_availability(
            hospital_id,
            doctor.id,
            [
                {
                    "day_of_week": 0,
                    "start_time": time(9),
                    "end_time": time(12),
                    "slot_duration_minutes": 15,
                }
            ],
        )

        assert await repository.get_availability(other_hospital_id, doctor.id) == []


class TestLeaves:
    """Leave storage and the overlap predicate."""

    async def test_create_and_list(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        doctor = await _create(repository, db_session, hospital_id)
        await repository.create_leave(
            hospital_id=hospital_id,
            doctor_id=doctor.id,
            starts_at=datetime(2026, 8, 15, tzinfo=UTC),
            ends_at=datetime(2026, 8, 18, tzinfo=UTC),
            reason="Conference",
        )

        rows = await repository.list_leaves(hospital_id, doctor.id)
        assert [r.reason for r in rows] == ["Conference"]

    async def test_list_leaves_is_tenant_scoped(
        self,
        repository: DoctorRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        doctor = await _create(repository, db_session, hospital_id)
        await repository.create_leave(
            hospital_id=hospital_id,
            doctor_id=doctor.id,
            starts_at=datetime(2026, 8, 15, tzinfo=UTC),
            ends_at=datetime(2026, 8, 18, tzinfo=UTC),
        )

        assert await repository.list_leaves(other_hospital_id, doctor.id) == []

    @pytest.mark.parametrize(
        ("start_day", "end_day", "expected"),
        [
            (16, 17, True),  # fully inside
            (14, 16, True),  # straddles the start
            (17, 20, True),  # straddles the end
            (10, 25, True),  # encloses
            (10, 15, False),  # ends exactly when the leave starts
            (18, 20, False),  # starts exactly when the leave ends
            (1, 5, False),  # entirely before
        ],
    )
    async def test_overlap_detection(
        self,
        repository: DoctorRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        start_day: int,
        end_day: int,
        expected: bool,
    ) -> None:
        """Half-open intervals: touching leaves do not overlap.

        Getting the boundary wrong either blocks legitimate back-to-back leave
        or lets a genuine double-booking through, so every case is pinned.
        """
        doctor = await _create(repository, db_session, hospital_id)
        await repository.create_leave(
            hospital_id=hospital_id,
            doctor_id=doctor.id,
            starts_at=datetime(2026, 8, 15, tzinfo=UTC),
            ends_at=datetime(2026, 8, 18, tzinfo=UTC),
        )

        found = await repository.find_overlapping_leaves(
            hospital_id,
            doctor.id,
            datetime(2026, 8, start_day, tzinfo=UTC),
            datetime(2026, 8, end_day, tzinfo=UTC),
        )
        assert bool(found) is expected

    async def test_overlap_can_exclude_a_leave(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """Re-checking an edit must not find the row being edited."""
        doctor = await _create(repository, db_session, hospital_id)
        leave = await repository.create_leave(
            hospital_id=hospital_id,
            doctor_id=doctor.id,
            starts_at=datetime(2026, 8, 15, tzinfo=UTC),
            ends_at=datetime(2026, 8, 18, tzinfo=UTC),
        )

        found = await repository.find_overlapping_leaves(
            hospital_id,
            doctor.id,
            datetime(2026, 8, 16, tzinfo=UTC),
            datetime(2026, 8, 17, tzinfo=UTC),
            exclude_leave_id=leave.id,
        )
        assert found == []

    async def test_deleted_leave_stops_overlapping(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """A cancelled leave must free its window up again."""
        doctor = await _create(repository, db_session, hospital_id)
        leave = await repository.create_leave(
            hospital_id=hospital_id,
            doctor_id=doctor.id,
            starts_at=datetime(2026, 8, 15, tzinfo=UTC),
            ends_at=datetime(2026, 8, 18, tzinfo=UTC),
        )
        await repository.delete_leave(leave)

        found = await repository.find_overlapping_leaves(
            hospital_id,
            doctor.id,
            datetime(2026, 8, 16, tzinfo=UTC),
            datetime(2026, 8, 17, tzinfo=UTC),
        )
        assert found == []

    async def test_get_leave_is_scoped_to_its_doctor(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """A leave id from another doctor must not be reachable."""
        first = await _create(repository, db_session, hospital_id)
        second = await _create(repository, db_session, hospital_id)
        leave = await repository.create_leave(
            hospital_id=hospital_id,
            doctor_id=first.id,
            starts_at=datetime(2026, 8, 15, tzinfo=UTC),
            ends_at=datetime(2026, 8, 18, tzinfo=UTC),
        )

        assert await repository.get_leave_by_id(hospital_id, first.id, leave.id) is not None
        assert await repository.get_leave_by_id(hospital_id, second.id, leave.id) is None

    async def test_list_leaves_window_filter(
        self, repository: DoctorRepository, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """Slot generation asks for leaves overlapping one day."""
        doctor = await _create(repository, db_session, hospital_id)
        await repository.create_leave(
            hospital_id=hospital_id,
            doctor_id=doctor.id,
            starts_at=datetime(2026, 8, 10, tzinfo=UTC),
            ends_at=datetime(2026, 8, 20, tzinfo=UTC),
        )

        # A leave spanning the day is returned even though it starts earlier.
        overlapping = await repository.list_leaves(
            hospital_id,
            doctor.id,
            starts_before=datetime(2026, 8, 16, tzinfo=UTC),
            ends_after=datetime(2026, 8, 15, tzinfo=UTC),
        )
        assert len(overlapping) == 1

        # A day outside the leave returns nothing.
        outside = await repository.list_leaves(
            hospital_id,
            doctor.id,
            starts_before=datetime(2026, 9, 2, tzinfo=UTC),
            ends_after=datetime(2026, 9, 1, tzinfo=UTC),
        )
        assert outside == []


class TestLifecycle:
    """Soft delete and restore."""

    async def test_delete_then_restore(
        self,
        repository: DoctorRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        doctor = await _create(repository, db_session, hospital_id)

        deleted = await repository.delete_doctor(doctor, deleted_by=actor_id)
        assert deleted.deleted_at is not None
        assert deleted.deleted_by == actor_id
        assert deleted.status == "inactive"

        restored = await repository.restore_doctor(doctor, updated_by=actor_id)
        assert restored.deleted_at is None
        assert restored.status == "active"
        assert await repository.get_doctor_by_id(hospital_id, doctor.id) is not None

    async def test_doctor_exists_is_tenant_scoped(
        self,
        repository: DoctorRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        doctor = await _create(repository, db_session, hospital_id)
        assert await repository.doctor_exists(hospital_id, doctor.id) is True
        assert await repository.doctor_exists(other_hospital_id, doctor.id) is False
