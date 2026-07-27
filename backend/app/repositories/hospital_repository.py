"""Repository for the :class:`Hospital` model.

Hospitals are the multi-tenant root. They are deactivated via
:attr:`~Hospital.is_active` rather than soft-deleted.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for type hints
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.models.hospital import Hospital
from app.repositories.base import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class HospitalRepository(BaseRepository[Hospital]):
    """Repository for hospital CRUD operations.

    :param session: An active async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Hospital, session)

    async def create(  # type: ignore[override]
        self,
        name: str,
        slug: str,
        address: dict[str, Any],
        **kwargs: object,
    ) -> Hospital:
        """Create a new hospital.

        :param name: Full hospital name.
        :param slug: URL-friendly unique identifier.
        :param address: Structured address object.
        :param kwargs: Additional optional fields (phone, email, tax_id, etc.).
        :returns: The created hospital instance.
        """
        return await super().create(
            name=name,
            slug=slug,
            address=address,
            **kwargs,
        )

    async def get_by_slug(self, slug: str) -> Hospital | None:
        """Retrieve a hospital by its slug.

        :param slug: The unique URL-friendly identifier.
        :returns: The hospital instance, or ``None``.
        """
        stmt = select(Hospital).where(Hospital.slug == slug)
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_active_by_id(self, id: uuid.UUID) -> Hospital | None:
        """Retrieve an active hospital by ID.

        :param id: The hospital UUID.
        :returns: The hospital instance if active, or ``None``.
        """
        stmt = select(Hospital).where(Hospital.id == id, Hospital.is_active.is_(True))
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def deactivate(self, hospital: Hospital) -> Hospital:
        """Deactivate a hospital by setting ``is_active = False``.

        :param hospital: The hospital instance to deactivate.
        :returns: The updated hospital instance.
        """
        return await self.update(hospital, is_active=False)

    async def list_active(self, skip: int = 0, limit: int = 100) -> list[Hospital]:
        """List only active hospitals.

        :param skip: Number of records to skip.
        :param limit: Maximum records to return.
        :returns: List of active hospital instances.
        """
        stmt = select(Hospital).where(Hospital.is_active.is_(True))
        stmt = self._apply_pagination(stmt, skip=skip, limit=limit)
        result = await self._session.execute(stmt)
        return list(result.unique().scalars().all())

    async def count_active(self) -> int:
        """Count active hospitals."""
        stmt = select(Hospital).where(Hospital.is_active.is_(True))
        return await self.count(stmt)
