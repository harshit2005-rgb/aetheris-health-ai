"""Regression tests for enum persistence on :class:`~app.models.user.User`.

``User.status`` maps a StrEnum to the ``user_status`` Postgres type. Without
``values_callable`` SQLAlchemy persists the member *name* ('ACTIVE') while the
type is defined with lowercase labels in migration 0001, so every insert failed
with ``InvalidTextRepresentationError`` and every read with ``LookupError``.

These run against a real database on purpose: the bug lives in the boundary
between the Python enum and the Postgres type, which no mock reproduces. That
also makes them repository-tier under ``docs/09-PROJECT_STRUCTURE.md`` rather
than unit tests.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.models.hospital import Hospital
from app.models.user import User, UserStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.database


async def _create_user(
    session: AsyncSession,
    hospital_id: uuid.UUID,
    status: UserStatus,
) -> User:
    """Insert a user through the ORM — the path that used to fail."""
    user = User(
        id=uuid.uuid4(),
        hospital_id=hospital_id,
        email=f"user-{uuid.uuid4().hex[:12]}@hospital.test",
        # Not a credential: the column is NOT NULL and nothing here reads it.
        password_hash="test-placeholder-not-a-hash",
        first_name="Test",
        last_name="User",
        status=status,
    )
    session.add(user)
    await session.flush()
    return user


class TestUserStatusPersistence:
    """Every UserStatus value survives a write/read round trip."""

    @pytest.mark.parametrize("status", list(UserStatus), ids=lambda s: s.value)
    async def test_user_status_round_trips_through_the_database(
        self,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        status: UserStatus,
    ) -> None:
        user = await _create_user(db_session, hospital_id, status)
        user_id = user.id

        # Detach everything so the SELECT builds a fresh instance from the
        # database row. Merely expiring would leave the identity-mapped object
        # in place and lazy-load the attribute on access, which proves nothing
        # about what Postgres actually stored.
        db_session.expunge_all()
        fetched = (
            (await db_session.execute(select(User).where(User.id == user_id))).unique().scalar_one()
        )

        assert fetched.status is status

    @pytest.mark.parametrize("status", list(UserStatus), ids=lambda s: s.value)
    async def test_the_stored_label_is_the_enum_value_not_the_member_name(
        self,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        status: UserStatus,
    ) -> None:
        # Asserted against the raw column text, not the ORM. A symmetric round
        # trip alone would not catch the two sides being wrong together.
        user = await _create_user(db_session, hospital_id, status)

        stored = (
            await db_session.execute(
                text("SELECT status::text FROM users WHERE id = :id"), {"id": user.id}
            )
        ).scalar_one()

        assert stored == status.value
        assert stored.islower()


class TestHospitalUsersEagerLoad:
    """Hospital.users is lazy="selectin", so a bad enum breaks hospital reads too."""

    async def test_loading_a_hospital_with_its_users_does_not_raise(
        self,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        for status in UserStatus:
            await _create_user(db_session, hospital_id, status)
        db_session.expunge_all()

        hospital = (
            (
                await db_session.execute(
                    select(Hospital)
                    .options(selectinload(Hospital.users))
                    .where(Hospital.id == hospital_id)
                )
            )
            .unique()
            .scalar_one()
        )

        assert {user.status for user in hospital.users} == set(UserStatus)
