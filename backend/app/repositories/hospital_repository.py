"""Repository for the :class:`Hospital` model.

Hospitals are the multi-tenant root. They are deactivated via
:attr:`~Hospital.is_active` rather than soft-deleted.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for type hints
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.models.hospital import Hospital
from app.repositories.base import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class HospitalSummary:
    """What identifies a hospital, without its users, roles or contact details.

    :param id: The hospital UUID.
    :param name: Display name.
    :param slug: Unique URL-friendly identifier.
    :param settings: The hospital's settings object (feature flags live here).
    """

    id: uuid.UUID
    name: str
    slug: str
    settings: dict[str, Any]


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

    async def get_active_summary(
        self, *, id: uuid.UUID | None = None, slug: str | None = None
    ) -> HospitalSummary | None:
        """Read the few columns that identify one active hospital.

        Selects columns, not the entity: loading a :class:`Hospital` also
        loads every user and role it has (``lazy="selectin"``), which a caller
        that only needs the name and the feature flags must not pay for — and
        which the Patient App must not pull into a patient's request at all.

        :param id: The hospital UUID. Exactly one of ``id`` and ``slug`` is given.
        :param slug: The hospital's unique slug.
        :returns: The summary, or ``None`` if there is no such active hospital.
        :raises ValueError: If neither or both of ``id`` and ``slug`` are given.
        """
        if (id is None) == (slug is None):
            msg = "get_active_summary() needs exactly one of id and slug."
            raise ValueError(msg)
        stmt = select(Hospital.id, Hospital.name, Hospital.slug, Hospital.settings).where(
            Hospital.is_active.is_(True)
        )
        stmt = (
            stmt.where(Hospital.id == id) if id is not None else stmt.where(Hospital.slug == slug)
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return HospitalSummary(
            id=row.id, name=row.name, slug=row.slug, settings=dict(row.settings or {})
        )

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
