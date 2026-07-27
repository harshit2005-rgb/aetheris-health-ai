"""Repository for the :class:`Role` model.

Roles are scoped to a hospital (or system-wide for system roles).
They support soft delete.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for type hints
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.models.role import Role
from app.repositories.base import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class RoleRepository(BaseRepository[Role]):
    """Repository for role CRUD operations.

    :param session: An active async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Role, session)

    async def create(  # type: ignore[override]
        self,
        hospital_id: uuid.UUID | None,
        name: str,
        **kwargs: object,
    ) -> Role:
        """Create a new role.

        :param hospital_id: UUID of the parent hospital, or ``None`` for system roles.
        :param name: Display name (e.g. 'Doctor', 'Receptionist').
        :param kwargs: Additional optional fields (description, is_system).
        :returns: The created role instance.
        """
        return await super().create(
            hospital_id=hospital_id,
            name=name,
            **kwargs,
        )

    async def get_by_name(self, hospital_id: uuid.UUID | None, name: str) -> Role | None:
        """Retrieve a role by name within a hospital.

        :param hospital_id: The hospital's UUID, or ``None`` for system roles.
        :param name: The role name.
        :returns: The role instance, or ``None``.
        """
        stmt = self._query().where(Role.hospital_id == hospital_id, Role.name == name)
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def list_by_hospital(
        self,
        hospital_id: uuid.UUID | None,
        *,
        skip: int = 0,
        limit: int = 100,
        include_system: bool = True,
    ) -> list[Role]:
        """List roles for a hospital, optionally including system roles.

        :param hospital_id: The hospital's UUID, or ``None`` for system roles only.
        :param skip: Number of records to skip.
        :param limit: Maximum records to return.
        :param include_system: If ``True``, include system roles (``is_system=True``).
        :returns: List of role instances.
        """
        stmt = self._query()
        if include_system:
            stmt = stmt.where(
                (Role.hospital_id == hospital_id)
                | (Role.hospital_id.is_(None) & Role.is_system.is_(True))
            )
        else:
            stmt = stmt.where(Role.hospital_id == hospital_id)
        stmt = self._apply_pagination(stmt, skip=skip, limit=limit)
        result = await self._session.execute(stmt)
        return list(result.unique().scalars().all())

    async def count_by_hospital(self, hospital_id: uuid.UUID | None) -> int:
        """Count roles in a hospital.

        :param hospital_id: The hospital's UUID, or ``None`` for system roles.
        :returns: The role count.
        """
        stmt = select(Role).where(Role.hospital_id == hospital_id)
        return await self.count(stmt)
