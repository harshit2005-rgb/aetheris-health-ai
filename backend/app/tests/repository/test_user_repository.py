"""Repository tests for :class:`~app.repositories.user_repository.UserRepository`.

Run against a real PostgreSQL (``docs/11-TESTING_STRATEGY.md`` §2.2) because
what is under test is the SQL: tenant scoping, the search predicates, and the
``user_roles`` join writes. None of that is observable through a mock.

The Week 1 handoff (A3) calls these out explicitly: the identity module had
repository coverage for only the user-status enum.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest

from app.models.role import Role
from app.models.user import User, UserRole, UserStatus
from app.repositories.user_repository import UserRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.database


@pytest.fixture
def repository(db_session: AsyncSession) -> UserRepository:
    """A repository bound to the rolled-back test session."""
    return UserRepository(db_session)


async def _create_user(
    repository: UserRepository,
    *,
    hospital_id: uuid.UUID,
    first_name: str = "Test",
    last_name: str = "User",
    email: str | None = None,
    **overrides: Any,
) -> User:
    """Insert a user with sensible defaults, overridable per test."""
    values: dict[str, Any] = {
        "email": email or f"user-{uuid.uuid4().hex[:12]}@hospital.test",
        "password_hash": "test-placeholder-not-a-hash",
        "first_name": first_name,
        "last_name": last_name,
    }
    values.update(overrides)
    return await repository.create(hospital_id=hospital_id, **values)


class TestTenantScoping:
    """Every query is filtered by hospital_id (CLAUDE.md rule 5)."""

    async def test_get_by_email_is_tenant_scoped(
        self,
        repository: UserRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        """The same email in another hospital is a different user."""
        email = f"shared-{uuid.uuid4().hex[:12]}@hospital.test"
        await _create_user(repository, hospital_id=hospital_id, email=email)

        assert await repository.get_by_email(hospital_id, email) is not None
        assert await repository.get_by_email(other_hospital_id, email) is None

    async def test_list_is_tenant_scoped(
        self,
        repository: UserRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        """A list never leaks users from another hospital."""
        await _create_user(repository, hospital_id=hospital_id, last_name="Mine")
        await _create_user(repository, hospital_id=other_hospital_id, last_name="Theirs")

        rows = await repository.list_by_hospital(hospital_id)

        assert [r.last_name for r in rows] == ["Mine"]

    async def test_count_is_tenant_scoped(
        self,
        repository: UserRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        """A count never includes another hospital's rows."""
        await _create_user(repository, hospital_id=hospital_id)
        await _create_user(repository, hospital_id=other_hospital_id)
        await _create_user(repository, hospital_id=other_hospital_id)

        assert await repository.count_by_hospital(hospital_id) == 1


class TestSearch:
    """The directory-search predicates shared by list and count."""

    async def test_search_matches_name_or_email_case_insensitively(
        self, repository: UserRepository, hospital_id: uuid.UUID
    ) -> None:
        """``search`` matches first name, last name, or email."""
        await _create_user(
            repository, hospital_id=hospital_id, first_name="Priya", last_name="Sharma"
        )
        await _create_user(
            repository, hospital_id=hospital_id, first_name="Ananya", last_name="Rao"
        )

        rows = await repository.list_by_hospital(hospital_id, search="sharma")
        assert [r.last_name for r in rows] == ["Sharma"]

        rows = await repository.list_by_hospital(hospital_id, search="ANANYA")
        assert [r.last_name for r in rows] == ["Rao"]

    async def test_search_is_tenant_scoped(
        self,
        repository: UserRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        """Search never crosses a tenant boundary."""
        await _create_user(
            repository, hospital_id=other_hospital_id, first_name="Priya", last_name="Sharma"
        )

        rows = await repository.list_by_hospital(hospital_id, search="sharma")

        assert rows == []

    async def test_search_filters_by_status(
        self, repository: UserRepository, hospital_id: uuid.UUID
    ) -> None:
        """``status`` narrows the result set."""
        await _create_user(
            repository, hospital_id=hospital_id, status=UserStatus.ACTIVE, last_name="Active"
        )
        await _create_user(
            repository,
            hospital_id=hospital_id,
            status=UserStatus.SUSPENDED,
            last_name="Suspended",
        )

        rows = await repository.list_by_hospital(hospital_id, status=UserStatus.SUSPENDED)
        assert [r.last_name for r in rows] == ["Suspended"]

    async def test_search_filters_the_list_rows(
        self, repository: UserRepository, hospital_id: uuid.UUID
    ) -> None:
        """Search narrows the returned rows."""
        for last in ("Sharma", "Sharma", "Rao"):
            await _create_user(repository, hospital_id=hospital_id, last_name=last)

        rows = await repository.list_by_hospital(hospital_id, search="sharma")

        assert len(rows) == 2

    async def test_count_honors_the_same_search_predicate(
        self, repository: UserRepository, hospital_id: uuid.UUID
    ) -> None:
        """B4 regression: ``count_by_hospital`` applies the identical search.

        The filtered total must agree with the filtered rows, or pagination
        renders empty pages (Week 1 handoff B4).
        """
        for last in ("Sharma", "Sharma", "Rao", "Das", "Iyer"):
            await _create_user(repository, hospital_id=hospital_id, last_name=last)

        rows = await repository.list_by_hospital(hospital_id, search="sharma")
        total = await repository.count_by_hospital(hospital_id, search="sharma")

        assert len(rows) == 2
        assert total == 2

        # Without the search argument the count stays the tenant-wide total.
        assert await repository.count_by_hospital(hospital_id) == 5


class TestUserRoleManagement:
    """The ``user_roles`` join writes used by role assignment."""

    async def test_add_role_then_has_role(
        self,
        repository: UserRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        """Adding a role makes ``has_role`` true."""
        user = await _create_user(repository, hospital_id=hospital_id)
        role = Role(
            id=uuid.uuid4(), hospital_id=hospital_id, name=f"Role {uuid.uuid4().hex[:8]}"
        )
        db_session.add(role)
        await db_session.flush()

        assert await repository.has_role(user.id, role.id) is False

        await repository.add_role(user.id, role.id)
        assert await repository.has_role(user.id, role.id) is True

    async def test_remove_role(
        self,
        repository: UserRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        """Removing a role returns True and clears ``has_role``."""
        user = await _create_user(repository, hospital_id=hospital_id)
        role = Role(
            id=uuid.uuid4(), hospital_id=hospital_id, name=f"Role {uuid.uuid4().hex[:8]}"
        )
        db_session.add(role)
        await db_session.flush()
        await repository.add_role(user.id, role.id)

        assert await repository.remove_role(user.id, role.id) is True
        assert await repository.has_role(user.id, role.id) is False

    async def test_remove_unassigned_role_returns_false(
        self,
        repository: UserRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        """Removing a role the user never had is a no-op returning False."""
        user = await _create_user(repository, hospital_id=hospital_id)

        assert await repository.remove_role(user.id, uuid.uuid4()) is False

    async def test_add_role_records_the_assigner(
        self,
        repository: UserRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        """``assigned_by`` is stamped per module spec §4 rule 9."""
        user = await _create_user(repository, hospital_id=hospital_id)
        role = Role(
            id=uuid.uuid4(), hospital_id=hospital_id, name=f"Role {uuid.uuid4().hex[:8]}"
        )
        db_session.add(role)
        await db_session.flush()

        await repository.add_role(user.id, role.id, assigned_by=actor_id)

        from sqlalchemy import select

        row = (
            await db_session.execute(
                select(UserRole).where(
                    UserRole.user_id == user.id, UserRole.role_id == role.id
                )
            )
        ).unique().scalar_one()
        assert row.assigned_by == actor_id
