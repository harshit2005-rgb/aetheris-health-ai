"""Repository for :class:`HospitalWorkingHours` (``docs/modules/14-hospital-settings.md`` §8)."""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for type hints
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select

from app.models.hospital_working_hours import HospitalWorkingHours
from app.repositories.base import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ["HospitalWorkingHoursRepository"]


class HospitalWorkingHoursRepository(BaseRepository[HospitalWorkingHours]):
    """Reads and replaces one hospital's week of opening hours."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(HospitalWorkingHours, session)

    async def list_for_hospital(self, hospital_id: uuid.UUID) -> list[HospitalWorkingHours]:
        """The hospital's days with an entry, Monday first.

        :param hospital_id: The tenant.
        :returns: At most seven rows, ordered by day.
        """
        result = await self._session.execute(
            select(HospitalWorkingHours)
            .where(HospitalWorkingHours.hospital_id == hospital_id)
            .order_by(HospitalWorkingHours.day_of_week)
        )
        return list(result.scalars().all())

    async def replace_for_hospital(
        self,
        hospital_id: uuid.UUID,
        days: list[dict[str, Any]],
        *,
        actor_id: uuid.UUID | None = None,
    ) -> list[HospitalWorkingHours]:
        """Replace the hospital's whole week in the caller's transaction.

        A hard ``DELETE``, as for doctor availability: opening hours are
        configuration, and soft-deleted rows would only pile up per edit.

        :param hospital_id: The tenant.
        :param days: One column dict per day: ``day_of_week``, ``open_time``,
            ``close_time``, ``is_24h``.
        :param actor_id: The user making the change.
        :returns: The new rows, Monday first.
        """
        await self._session.execute(
            delete(HospitalWorkingHours).where(HospitalWorkingHours.hospital_id == hospital_id)
        )
        rows = [
            HospitalWorkingHours(
                hospital_id=hospital_id, created_by=actor_id, updated_by=actor_id, **day
            )
            for day in days
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return sorted(rows, key=lambda row: row.day_of_week)
