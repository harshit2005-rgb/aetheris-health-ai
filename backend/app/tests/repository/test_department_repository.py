"""Repository tests for :class:`~app.repositories.department_repository.DepartmentRepository`.

Run against a real PostgreSQL (``docs/11-TESTING_STRATEGY.md`` §2.2) because
what is under test is the SQL: the tenant filter, the soft-delete filter, the
two unique constraints, case-insensitive matching, and ordering. None of that
is observable through a mock.

Every query method has at least one test proving it filters by ``hospital_id``
(backend/CLAUDE.md, "Testing").
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy.exc import IntegrityError

from app.repositories.department_repository import DepartmentRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.department import Department

pytestmark = pytest.mark.database


@pytest.fixture
def repository(db_session: AsyncSession) -> DepartmentRepository:
    """A repository bound to the rolled-back test session."""
    return DepartmentRepository(db_session)


async def _create(
    repository: DepartmentRepository,
    hospital_id: uuid.UUID,
    **overrides: Any,
) -> Department:
    """Insert a department with sensible defaults, overridable per test."""
    values: dict[str, Any] = {
        "code": f"D{uuid.uuid4().hex[:6].upper()}",
        "name": f"Department {uuid.uuid4().hex[:8]}",
    }
    values.update(overrides)
    return await repository.create_department(hospital_id=hospital_id, **values)


class TestCreateAndRead:
    """Insertion and single-record retrieval."""

    async def test_create_persists_all_columns(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID
    ) -> None:
        """Every column the API accepts round-trips through the database."""
        department = await _create(
            repository,
            hospital_id,
            code="CARD",
            name="Cardiology",
            description="Heart care.",
            phone_extension="204",
            email="cardio@hospital.test",
            location="Block B",
        )

        assert department.id is not None
        assert department.code == "CARD"
        assert department.name == "Cardiology"
        assert department.description == "Heart care."
        assert department.phone_extension == "204"
        assert department.email == "cardio@hospital.test"
        assert department.location == "Block B"
        assert department.deleted_at is None
        assert department.status == "active"

    async def test_get_by_id_finds_own_tenant(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID
    ) -> None:
        """A department is visible within its own hospital."""
        created = await _create(repository, hospital_id)
        found = await repository.get_department_by_id(hospital_id, created.id)
        assert found is not None
        assert found.id == created.id

    async def test_get_by_id_is_tenant_scoped(
        self,
        repository: DepartmentRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        """A department in another hospital is invisible, even by exact id."""
        created = await _create(repository, hospital_id)
        assert await repository.get_department_by_id(other_hospital_id, created.id) is None

    async def test_get_by_id_excludes_soft_deleted_by_default(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID
    ) -> None:
        """A deactivated department is hidden unless explicitly requested."""
        created = await _create(repository, hospital_id)
        await repository.delete_department(created)

        assert await repository.get_department_by_id(hospital_id, created.id) is None
        assert (
            await repository.get_department_by_id(hospital_id, created.id, include_deleted=True)
            is not None
        )


class TestUniqueness:
    """The two per-hospital unique constraints."""

    async def test_duplicate_code_in_same_hospital_is_rejected(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID, db_session: AsyncSession
    ) -> None:
        """``uq_departments_hospital_code`` blocks a second identical code."""
        await _create(repository, hospital_id, code="CARD", name="Cardiology")

        with pytest.raises(IntegrityError):
            await _create(repository, hospital_id, code="CARD", name="Cardiac Sciences")
        await db_session.rollback()

    async def test_duplicate_name_is_rejected_case_insensitively(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID, db_session: AsyncSession
    ) -> None:
        """``uq_departments_hospital_name_lower`` treats casing as identical.

        This is the constraint that makes "Cardiology" and "cardiology" one
        department rather than two.
        """
        await _create(repository, hospital_id, code="CARD", name="Cardiology")

        with pytest.raises(IntegrityError):
            await _create(repository, hospital_id, code="CARD2", name="cardiology")
        await db_session.rollback()

    async def test_same_code_in_different_hospitals_is_allowed(
        self,
        repository: DepartmentRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        """Uniqueness is per hospital — two tenants may both have CARD."""
        first = await _create(repository, hospital_id, code="CARD", name="Cardiology")
        second = await _create(repository, other_hospital_id, code="CARD", name="Cardiology")
        assert first.id != second.id

    async def test_code_check_constraint_rejects_bad_format(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID, db_session: AsyncSession
    ) -> None:
        """``ck_departments_code_format`` is the last line of defence.

        The schema normally catches this. The constraint matters because the
        repository is also reachable from seed scripts and migrations.
        """
        with pytest.raises(IntegrityError):
            await _create(repository, hospital_id, code="bad code")
        await db_session.rollback()


class TestLookupByCodeAndName:
    """Duplicate-check helpers used by the service."""

    async def test_get_by_code_finds_soft_deleted_by_default(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID
    ) -> None:
        """A deactivated department still occupies its code.

        The unique constraint applies regardless of soft-delete state, so the
        duplicate check must see deactivated rows or it would report a code as
        free that the database will reject.
        """
        created = await _create(repository, hospital_id, code="CARD")
        await repository.delete_department(created)

        assert await repository.get_department_by_code(hospital_id, "CARD") is not None

    async def test_get_by_code_is_tenant_scoped(
        self,
        repository: DepartmentRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        """Another tenant's code does not count as taken."""
        await _create(repository, hospital_id, code="CARD")
        assert await repository.get_department_by_code(other_hospital_id, "CARD") is None

    async def test_get_by_name_matches_case_insensitively(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID
    ) -> None:
        """The lookup agrees with the functional unique index on ``lower(name)``."""
        await _create(repository, hospital_id, name="Cardiology")

        for probe in ("Cardiology", "cardiology", "CARDIOLOGY"):
            assert await repository.get_department_by_name(hospital_id, probe) is not None

    async def test_get_by_name_is_tenant_scoped(
        self,
        repository: DepartmentRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        """Another tenant's name does not count as taken."""
        await _create(repository, hospital_id, name="Cardiology")
        assert await repository.get_department_by_name(other_hospital_id, "Cardiology") is None


class TestListAndSearch:
    """Listing, searching, ordering, and counting."""

    async def test_list_is_tenant_scoped(
        self,
        repository: DepartmentRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        """A list never leaks rows from another hospital."""
        await _create(repository, hospital_id, code="AAA", name="Alpha")
        await _create(repository, other_hospital_id, code="BBB", name="Beta")

        rows = await repository.list_departments(hospital_id)
        assert [r.name for r in rows] == ["Alpha"]

    async def test_list_orders_by_name(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID
    ) -> None:
        """Ordering is by name so the UI does not have to sort."""
        await _create(repository, hospital_id, code="C3", name="Cardiology")
        await _create(repository, hospital_id, code="A1", name="Anaesthesia")
        await _create(repository, hospital_id, code="B2", name="Biochemistry")

        rows = await repository.list_departments(hospital_id)
        assert [r.name for r in rows] == ["Anaesthesia", "Biochemistry", "Cardiology"]

    async def test_list_excludes_soft_deleted_by_default(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID
    ) -> None:
        """Deactivated departments drop out of the default list."""
        keep = await _create(repository, hospital_id, code="KEEP", name="Kept")
        drop = await _create(repository, hospital_id, code="DROP", name="Dropped")
        await repository.delete_department(drop)

        active = await repository.list_departments(hospital_id)
        assert [r.id for r in active] == [keep.id]

        both = await repository.list_departments(hospital_id, include_deleted=True)
        assert {r.id for r in both} == {keep.id, drop.id}

    async def test_list_paginates(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID
    ) -> None:
        """Offset and limit slice the ordered result."""
        for index in range(5):
            await _create(repository, hospital_id, code=f"P{index}", name=f"Dept {index}")

        first = await repository.list_departments(hospital_id, skip=0, limit=2)
        second = await repository.list_departments(hospital_id, skip=2, limit=2)

        assert [r.name for r in first] == ["Dept 0", "Dept 1"]
        assert [r.name for r in second] == ["Dept 2", "Dept 3"]

    async def test_search_matches_name_prefix_case_insensitively(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID
    ) -> None:
        """``q`` prefix-matches the name regardless of casing."""
        await _create(repository, hospital_id, code="CARD", name="Cardiology")
        await _create(repository, hospital_id, code="ORTH", name="Orthopaedics")

        rows = await repository.search_departments(hospital_id, term="cardi")
        assert [r.name for r in rows] == ["Cardiology"]

    async def test_search_matches_exact_code_case_insensitively(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID
    ) -> None:
        """A lowercase code query still finds the uppercase stored code."""
        await _create(repository, hospital_id, code="ICU", name="Intensive Care")

        rows = await repository.search_departments(hospital_id, term="icu")
        assert [r.code for r in rows] == ["ICU"]

    async def test_search_does_not_match_name_substring(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID
    ) -> None:
        """Matching is prefix-only, which is what keeps the index usable."""
        await _create(repository, hospital_id, code="CARD", name="Cardiology")
        assert await repository.search_departments(hospital_id, term="ology") == []

    async def test_search_treats_wildcards_literally(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID
    ) -> None:
        """A ``%`` in the term must not turn into a match-everything wildcard."""
        await _create(repository, hospital_id, code="CARD", name="Cardiology")
        assert await repository.search_departments(hospital_id, term="%") == []

    async def test_search_is_tenant_scoped(
        self,
        repository: DepartmentRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        """Search never crosses a tenant boundary."""
        await _create(repository, other_hospital_id, code="CARD", name="Cardiology")
        assert await repository.search_departments(hospital_id, term="cardi") == []

    async def test_count_agrees_with_search(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID
    ) -> None:
        """The count uses the same predicates as the page, so totals cannot lie."""
        await _create(repository, hospital_id, code="CARD", name="Cardiology")
        await _create(repository, hospital_id, code="CARE", name="Cardiac Surgery")
        await _create(repository, hospital_id, code="ORTH", name="Orthopaedics")

        rows = await repository.search_departments(hospital_id, term="cardi")
        total = await repository.count_departments(hospital_id, term="cardi")
        assert total == len(rows) == 2

    async def test_count_is_tenant_scoped(
        self,
        repository: DepartmentRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        """A count never includes another hospital's rows."""
        await _create(repository, hospital_id)
        await _create(repository, other_hospital_id)
        await _create(repository, other_hospital_id)

        assert await repository.count_departments(hospital_id) == 1


class TestLifecycle:
    """Soft delete and restore."""

    async def test_delete_sets_deleted_at_and_by(
        self,
        repository: DepartmentRepository,
        hospital_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        """Soft delete records both when and who, in one flush."""
        created = await _create(repository, hospital_id)
        deleted = await repository.delete_department(created, deleted_by=actor_id)

        assert deleted.deleted_at is not None
        assert deleted.deleted_by == actor_id
        assert deleted.status == "inactive"

    async def test_restore_clears_soft_delete(
        self,
        repository: DepartmentRepository,
        hospital_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        """Restore returns the row to the default list."""
        created = await _create(repository, hospital_id)
        await repository.delete_department(created, deleted_by=actor_id)
        restored = await repository.restore_department(created, updated_by=actor_id)

        assert restored.deleted_at is None
        assert restored.deleted_by is None
        assert restored.status == "active"
        assert await repository.get_department_by_id(hospital_id, created.id) is not None

    async def test_update_changes_fields_and_actor(
        self,
        repository: DepartmentRepository,
        hospital_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        """An update writes the new values and stamps the acting user."""
        created = await _create(repository, hospital_id, location="Block A")
        updated = await repository.update_department(
            created, updated_by=actor_id, location="Block C"
        )

        assert updated.location == "Block C"
        assert updated.updated_by == actor_id


class TestExists:
    """The existence probe."""

    async def test_exists_within_tenant(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID
    ) -> None:
        """A live department in this hospital exists."""
        created = await _create(repository, hospital_id)
        assert await repository.department_exists(hospital_id, created.id) is True

    async def test_exists_is_tenant_scoped(
        self,
        repository: DepartmentRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        """A department in another hospital does not exist as far as this one knows."""
        created = await _create(repository, hospital_id)
        assert await repository.department_exists(other_hospital_id, created.id) is False

    async def test_exists_excludes_soft_deleted_by_default(
        self, repository: DepartmentRepository, hospital_id: uuid.UUID
    ) -> None:
        """A deactivated department does not exist unless asked for."""
        created = await _create(repository, hospital_id)
        await repository.delete_department(created)

        assert await repository.department_exists(hospital_id, created.id) is False
        assert (
            await repository.department_exists(hospital_id, created.id, include_deleted=True)
            is True
        )
