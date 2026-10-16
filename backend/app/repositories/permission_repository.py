"""Repository for the :class:`Permission` model.

Permissions are global — they are not scoped to any hospital.
They are seeded once and never deleted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.models.permission import Permission
from app.repositories.base import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class PermissionRepository(BaseRepository[Permission]):
    """Repository for permission lookups.

    Permissions do not support soft delete or tenant scoping.

    :param session: An active async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Permission, session)

    async def get_by_code(self, code: str) -> Permission | None:
        """Retrieve a permission by its unique code.

        :param code: The permission code (e.g. ``'patient.create'``).
        :returns: The permission instance, or ``None``.
        """
        stmt = select(Permission).where(Permission.code == code)
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def list_by_module(self, module: str) -> list[Permission]:
        """List all permissions belonging to a module.

        :param module: The module name (e.g. ``'patient'``, ``'billing'``).
        :returns: List of permission instances.
        """
        stmt = select(Permission).where(Permission.module == module).order_by(Permission.code)
        result = await self._session.execute(stmt)
        return list(result.unique().scalars().all())

    async def list_all(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        module: str | None = None,
    ) -> list[Permission]:
        """List permissions with optional module filter and pagination.

        :param skip: Number of records to skip.
        :param limit: Maximum records to return.
        :param module: Optional module filter.
        :returns: List of permission instances.
        """
        stmt = select(Permission)
        if module is not None:
            stmt = stmt.where(Permission.module == module)
        stmt = stmt.order_by(Permission.module, Permission.code)
        stmt = self._apply_pagination(stmt, skip=skip, limit=limit)
        result = await self._session.execute(stmt)
        return list(result.unique().scalars().all())

    async def list_codes(self) -> list[str]:
        """Return a flat list of all permission codes.

        Useful for permission registry construction.

        :returns: List of permission code strings.
        """
        stmt = select(Permission.code).order_by(Permission.code)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_all(self, *, module: str | None = None) -> int:
        """Count permissions, optionally filtered by module.

        Takes the identical filter as :meth:`list_all` so the total in a
        paginated response can never disagree with the rows on the page.

        :param module: Optional module filter.
        :returns: The permission count.
        """
        stmt = select(Permission)
        if module is not None:
            stmt = stmt.where(Permission.module == module)
        return await self.count(stmt)
