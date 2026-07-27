"""Base class for all business-logic services.

Every service inherits from :class:`BaseService` to receive:

- A structured logger bound to the service name.
- A :class:`~app.database.unit_of_work.UnitOfWork` for transaction management.

Services implement business rules, orchestrate across repositories, and own
transactions. They never write SQL, never call other repositories directly,
and never depend on HTTP concerns.

Usage::

    from app.services.base import BaseService

    class PatientService(BaseService):

        def __init__(self, uow: UnitOfWork, patient_repo: PatientRepository):
            super().__init__(uow)
            self._patients = patient_repo

        async def get(self, patient_id: uuid.UUID) -> PatientDTO | None:
            self.logger.info("fetching_patient", patient_id=str(patient_id))
            patient = await self._patients.get_by_id(patient_id)
            return PatientDTO.from_orm(patient) if patient else None
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.database.unit_of_work import UnitOfWork


class BaseService:
    """Abstract base class for all business-logic services.

    :param uow: A :class:`~app.database.unit_of_work.UnitOfWork` bound to the
        request-scoped session. Services use ``uow.transaction()`` to wrap
        multi-repository writes atomically.

    Subclasses **must** call ``super().__init__(uow)`` and should avoid
    overriding :attr:`logger`.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    # ── Public API ──────────────────────────────────────────────────────────

    @property
    def uow(self) -> UnitOfWork:
        """Return the UnitOfWork bound to this service.

        Usage::

            async with self.uow.transaction():
                patient = await self._patients.create(...)
                await self._audit.log("patient.created", ...)
        """
        return self._uow

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Return a structured logger bound to the service's module path.

        The logger name is inferred from the subclass module, so log entries
        are automatically attributed to the correct service.
        """
        return structlog.get_logger(type(self).__module__)  # type: ignore[no-any-return]


__all__ = [
    "BaseService",
]
