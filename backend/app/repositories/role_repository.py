"""Repository for the :class:`Role` model.

Roles are scoped to a hospital (or system-wide for system roles).
They support soft delete.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for type hints
from typing import TYPE_CHECKING

from sqlalchemy import Select, or_
from sqlalchemy.orm import selectinload

from app.models.role import Role, RolePermission
from app.repositories.base import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class RoleRepository(BaseRepository[Role]):
    """Repository for role CRUD operations.

    :param session: An active async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Role, session)

    # ── Query building ────────────────────────────────────────────────────────

    def _visible_to(
        self, hospital_id: uuid.UUID | None, *, include_system: bool = True
    ) -> Select[tuple[Role]]:
        """Return a base SELECT scoped to what one tenant can see.

        A tenant sees its own hospital-scoped roles **and** the global system
        roles (``hospital_id IS NULL``, ``is_system``) that every tenant
        shares (``docs/modules/02-user-management.md`` §4, rule 4). Never
        another tenant's roles.

        :param hospital_id: The tenant to scope to.
        :param include_system: When ``True``, include system roles.
        :returns: A statement filtered by tenant visibility.
        """
        stmt = self._query()
        if include_system:
            return stmt.where(
                or_(
                    Role.hospital_id == hospital_id,
                    Role.hospital_id.is_(None) & Role.is_system.is_(True),
                )
            )
        return stmt.where(Role.hospital_id == hospital_id)

    @staticmethod
    def _ordered(stmt: Select[tuple[Role]]) -> Select[tuple[Role]]:
        """Order by name with ``id`` as a tiebreaker.

        The ``id`` tiebreak makes pagination stable: without it two roles with
        identical names could swap places between page requests.
        """
        return stmt.order_by(Role.name.asc(), Role.id.asc())

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
        :returns: List of role instances, ordered by name.
        """
        stmt = self._apply_pagination(
            self._ordered(self._visible_to(hospital_id, include_system=include_system)),
            skip=skip,
            limit=limit,
        )
        result = await self._session.execute(stmt)
        return list(result.unique().scalars().all())

    async def count_by_hospital(
        self,
        hospital_id: uuid.UUID | None,
        *,
        include_system: bool = True,
    ) -> int:
        """Count roles visible to a hospital.

        Takes the identical visibility filter as :meth:`list_by_hospital` so
        the total in a paginated response can never disagree with the rows on
        the page.

        :param hospital_id: The hospital's UUID, or ``None`` for system roles.
        :param include_system: If ``True``, include system roles.
        :returns: The role count.
        """
        stmt = self._visible_to(hospital_id, include_system=include_system)
        return await self.count(stmt)

    async def get_with_permissions(
        self,
        role_id: uuid.UUID,
        *,
        hospital_id: uuid.UUID | None = None,
    ) -> Role | None:
        """Retrieve one role with its permission rows eager-loaded.

        The role's ``role_permissions`` collection is loaded in the same query
        (``selectinload``) so the service can read permission codes without
        triggering an async lazy load.

        :param role_id: The role's UUID.
        :param hospital_id: Optional tenant to scope by. When given, only
            roles belonging to that hospital or system roles are returned;
            when ``None``, any role (including another tenant's) can be read
            — used by the Super Admin path.
        :returns: The role with permissions loaded, or ``None``.
        """
        stmt = self._query().options(
            selectinload(Role.role_permissions).selectinload(RolePermission.permission)
        )
        if hospital_id is not None:
            stmt = stmt.where(
                or_(
                    Role.hospital_id == hospital_id,
                    Role.hospital_id.is_(None) & Role.is_system.is_(True),
                )
            )
        stmt = stmt.where(Role.id == role_id)
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()
