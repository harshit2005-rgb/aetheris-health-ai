"""Repository for the :class:`User` model.

Users belong to a hospital and support soft delete. All queries
automatically filter out soft-deleted records.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for type hints
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.identity.models import User, UserStatus
from app.shared.repositories import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class UserRepository(BaseRepository[User]):
    """Repository for user CRUD operations.

    :param session: An active async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    async def create(  # type: ignore[override]
        self,
        hospital_id: uuid.UUID,
        email: str,
        password_hash: str,
        first_name: str,
        last_name: str,
        **kwargs: object,
    ) -> User:
        """Create a new user.

        :param hospital_id: UUID of the parent hospital.
        :param email: Login email address (unique per hospital).
        :param password_hash: Argon2id hash of the user's password.
        :param first_name: User's given name.
        :param last_name: User's family name.
        :param kwargs: Additional optional fields (phone, status, etc.).
        :returns: The created user instance.
        """
        return await super().create(
            hospital_id=hospital_id,
            email=email,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            **kwargs,
        )

    async def get_by_email(self, hospital_id: uuid.UUID, email: str) -> User | None:
        """Retrieve a user by email within a specific hospital.

        :param hospital_id: The hospital's UUID.
        :param email: The user's email address.
        :returns: The user instance, or ``None``.
        """
        stmt = (
            self._query()
            .where(User.hospital_id == hospital_id, User.email == email)
        )
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def list_by_hospital(
        self,
        hospital_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        status: UserStatus | None = None,
    ) -> list[User]:
        """List users belonging to a hospital, with optional status filter.

        :param hospital_id: The hospital's UUID.
        :param skip: Number of records to skip.
        :param limit: Maximum records to return.
        :param status: Optional status filter.
        :returns: List of user instances.
        """
        stmt = self._query().where(User.hospital_id == hospital_id)
        if status is not None:
            stmt = stmt.where(User.status == status)
        stmt = self._apply_pagination(stmt, skip=skip, limit=limit)
        result = await self._session.execute(stmt)
        return list(result.unique().scalars().all())

    async def count_by_hospital(
        self,
        hospital_id: uuid.UUID,
        status: UserStatus | None = None,
    ) -> int:
        """Count users in a hospital, optionally filtered by status.

        :param hospital_id: The hospital's UUID.
        :param status: Optional status filter.
        :returns: The user count.
        """
        stmt = select(User).where(User.hospital_id == hospital_id)
        if status is not None:
            stmt = stmt.where(User.status == status)
        return await self.count(stmt)

    async def record_login(self, user: User) -> User:
        """Update a user's last_login_at timestamp.

        :param user: The user instance to update.
        :returns: The updated user instance.
        """
        return await self.update(user, last_login_at=datetime.now(UTC))

    async def increment_failed_logins(self, user: User) -> User:
        """Increment the failed login attempt counter.

        :param user: The user instance to update.
        :returns: The updated user instance.
        """
        return await self.update(
            user,
            failed_login_attempts=user.failed_login_attempts + 1,
        )

    async def reset_failed_logins(self, user: User) -> User:
        """Reset the failed login attempt counter to zero.

        :param user: The user instance to update.
        :returns: The updated user instance.
        """
        return await self.update(user, failed_login_attempts=0, locked_until=None)

    async def lock_account(self, user: User, until: datetime) -> User:
        """Lock a user's account until the specified time.

        :param user: The user instance to lock.
        :param until: Timestamp until which the account is locked.
        :returns: The updated user instance.
        """
        return await self.update(user, locked_until=until)
