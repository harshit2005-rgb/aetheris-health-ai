"""Repository for consultations and their addenda.

Data access only: no business rules, ORM models out
(``docs/03-ARCHITECTURE.md`` §4.4). Every method takes ``hospital_id`` and
filters on it (CLAUDE.md rules 4 and 5). A consultation is the aggregate root:
addenda are only reached through it.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for type hints
from typing import TYPE_CHECKING, Any

from sqlalchemy import Select, func, select

from app.models.consultation import Consultation, ConsultationAddendum, ConsultationStatus
from app.repositories.base import BaseRepository

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession


class ConsultationRepository(BaseRepository[Consultation]):
    """Persistence for consultations.

    :param session: An active async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Consultation, session)

    def _scoped(self, hospital_id: uuid.UUID) -> Select[tuple[Consultation]]:
        """Return a base SELECT filtered to one hospital."""
        return self._query().where(Consultation.hospital_id == hospital_id)

    @staticmethod
    def _apply_filters(
        stmt: Select[Any],
        *,
        patient_id: uuid.UUID | None = None,
        doctor_id: uuid.UUID | None = None,
        appointment_id: uuid.UUID | None = None,
        status: ConsultationStatus | None = None,
    ) -> Select[Any]:
        if patient_id is not None:
            stmt = stmt.where(Consultation.patient_id == patient_id)
        if doctor_id is not None:
            stmt = stmt.where(Consultation.doctor_id == doctor_id)
        if appointment_id is not None:
            stmt = stmt.where(Consultation.appointment_id == appointment_id)
        if status is not None:
            stmt = stmt.where(Consultation.status == status)
        return stmt

    async def _reload(self, consultation: Consultation) -> Consultation:
        """Re-read a consultation with its addenda, after a flush.

        A flush leaves server-maintained columns expired; reading them would
        be lazy IO, which async SQLAlchemy refuses.
        """
        stmt = (
            select(Consultation)
            .where(
                Consultation.id == consultation.id,
                Consultation.hospital_id == consultation.hospital_id,
            )
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(stmt)
        return result.unique().scalar_one()

    # ── Queries ───────────────────────────────────────────────────────────────

    async def get_for_hospital(
        self, hospital_id: uuid.UUID, consultation_id: uuid.UUID, *, for_update: bool = False
    ) -> Consultation | None:
        """Fetch one consultation of this hospital, or ``None``.

        :param hospital_id: The tenant.
        :param consultation_id: The consultation.
        :param for_update: Lock the row for the rest of the transaction.
        """
        stmt = self._scoped(hospital_id).where(Consultation.id == consultation_id)
        if for_update:
            stmt = stmt.with_for_update(of=Consultation)
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_by_appointment(
        self, hospital_id: uuid.UUID, appointment_id: uuid.UUID
    ) -> Consultation | None:
        """Fetch the consultation of one visit, or ``None`` if not started."""
        stmt = self._scoped(hospital_id).where(Consultation.appointment_id == appointment_id)
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def list_page(
        self,
        hospital_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        **filters: Any,
    ) -> tuple[Sequence[Consultation], int]:
        """A page of consultations, newest first, and the total that match.

        :param hospital_id: The tenant.
        :param offset: Rows to skip.
        :param limit: Rows to return.
        :param filters: ``patient_id``, ``doctor_id``, ``appointment_id``, ``status``.
        :returns: ``(rows, total)``.
        """
        stmt = self._apply_filters(self._scoped(hospital_id), **filters)
        stmt = stmt.order_by(Consultation.created_at.desc(), Consultation.id).offset(offset)
        rows = (await self._session.execute(stmt.limit(limit))).unique().scalars().all()
        count_stmt = self._apply_filters(
            select(func.count())
            .select_from(Consultation)
            .where(Consultation.hospital_id == hospital_id, Consultation.deleted_at.is_(None)),
            **filters,
        )
        total = int((await self._session.execute(count_stmt)).scalar_one())
        return rows, total

    # ── Commands ──────────────────────────────────────────────────────────────

    async def create_consultation(
        self,
        *,
        hospital_id: uuid.UUID,
        appointment_id: uuid.UUID,
        patient_id: uuid.UUID,
        doctor_id: uuid.UUID,
        created_by: uuid.UUID | None = None,
        **fields: Any,
    ) -> Consultation:
        """Insert a draft consultation. Does not commit.

        A second note for the same visit violates the unique index and raises
        ``IntegrityError`` at the flush.
        """
        consultation = Consultation(
            hospital_id=hospital_id,
            appointment_id=appointment_id,
            patient_id=patient_id,
            doctor_id=doctor_id,
            status=ConsultationStatus.DRAFT,
            diagnoses=fields.pop("diagnoses", []),
            created_by=created_by,
            updated_by=created_by,
            **fields,
        )
        self._session.add(consultation)
        await self._session.flush()
        return await self._reload(consultation)

    async def update_consultation(
        self, consultation: Consultation, *, updated_by: uuid.UUID | None = None, **fields: Any
    ) -> Consultation:
        """Apply field updates and return the row fully loaded. Does not commit."""
        for name, value in fields.items():
            setattr(consultation, name, value)
        consultation.updated_by = updated_by
        await self._session.flush()
        return await self._reload(consultation)

    async def add_addendum(
        self,
        consultation: Consultation,
        *,
        text: str,
        added_by: uuid.UUID,
        added_at: datetime,
    ) -> Consultation:
        """Append an addendum and return the consultation with all its addenda."""
        self._session.add(
            ConsultationAddendum(
                hospital_id=consultation.hospital_id,
                consultation_id=consultation.id,
                text=text,
                added_by=added_by,
                added_at=added_at,
                created_by=added_by,
                updated_by=added_by,
            )
        )
        await self._session.flush()
        return await self._reload(consultation)
