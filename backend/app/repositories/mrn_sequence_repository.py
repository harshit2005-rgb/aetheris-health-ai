"""Repository for the per-hospital MRN counter.

Owns exactly one thing: advancing ``mrn_sequences.current_value`` for a
hospital under a row lock, so that two concurrent registrations cannot be
handed the same sequence number
(``docs/modules/03-patient-management.md`` §8).

Data access only — the rendered MRN string is assembled by
:class:`~app.services.mrn_service.MRNService`.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for type hints
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.patient import MrnSequence
from app.repositories.base import BaseRepository
from app.utils.mrn import DEFAULT_MRN_TEMPLATE

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class MrnSequenceRepository(BaseRepository[MrnSequence]):
    """Repository for the ``mrn_sequences`` counter table.

    :param session: An active async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(MrnSequence, session)

    async def get_for_hospital(self, hospital_id: uuid.UUID) -> MrnSequence | None:
        """Read a hospital's counter row without locking it.

        Use this for reads that do not advance the counter (e.g. showing the
        configured template in hospital settings). Registration must use
        :meth:`advance`.

        :param hospital_id: The hospital's UUID.
        :returns: The counter row, or ``None`` if the hospital has never
            registered a patient.
        """
        stmt = select(MrnSequence).where(MrnSequence.hospital_id == hospital_id)
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def advance(self, hospital_id: uuid.UUID) -> tuple[int, str]:
        """Reserve the next sequence value for a hospital.

        Runs in three steps, all inside the caller's transaction:

        1. ``INSERT ... ON CONFLICT DO NOTHING`` creates the counter row the
           first time a hospital registers a patient. Doing this before the
           lock means the "first ever patient" path has no read-then-insert
           race — a concurrent inserter either loses the conflict or blocks
           until the winner commits.
        2. ``SELECT ... FOR UPDATE`` takes a row lock. A second transaction
           reaching this line waits here rather than reading a stale counter.
        3. The counter is incremented and flushed. The lock is held until the
           caller commits, so the value cannot be reused.

        The caller **must** be inside a transaction; the lock is meaningless
        otherwise.

        :param hospital_id: The hospital whose counter to advance.
        :returns: A ``(sequence_value, format_template)`` pair, where
            ``sequence_value`` is the newly reserved number.
        """
        # 1. Ensure the row exists.
        ensure_stmt = (
            pg_insert(MrnSequence)
            .values(
                hospital_id=hospital_id,
                current_value=0,
                format_template=DEFAULT_MRN_TEMPLATE,
            )
            .on_conflict_do_nothing(index_elements=["hospital_id"])
        )
        await self._session.execute(ensure_stmt)

        # 2. Lock the row for the rest of this transaction.
        lock_stmt = (
            select(MrnSequence).where(MrnSequence.hospital_id == hospital_id).with_for_update()
        )
        result = await self._session.execute(lock_stmt)
        sequence = result.unique().scalar_one()

        # 3. Reserve the next value.
        sequence.current_value += 1
        await self._session.flush()

        return sequence.current_value, sequence.format_template
