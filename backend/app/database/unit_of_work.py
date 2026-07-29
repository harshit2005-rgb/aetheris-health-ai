"""Async Unit of Work — transaction context manager for the service layer.

Ownership of transactions belongs to the **service layer**, not repositories
(see ``docs/03-ARCHITECTURE.md`` §9). This module provides the
:class:`UnitOfWork` that services use to coordinate writes across multiple
repositories atomically.

Usage::

    class PatientService:
        def __init__(self, uow: UnitOfWork, patient_repo: PatientRepository):
            self._uow = uow
            self._patients = patient_repo

        async def create(self, data: PatientCreate) -> Patient:
            async with self._uow.transaction():
                patient = await self._patients.create(**data.model_dump())
                return patient

The :class:`UnitOfWork` does **not** create its own session — it receives one
from the caller (or from the DI system), keeping session lifecycle management
in the request scope.
"""

from contextlib import asynccontextmanager
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class UnitOfWork:
    """Transaction coordinator that wraps an async SQLAlchemy session.

    Every service that writes data receives a :class:`UnitOfWork` (not a bare
    session) so that cross-repository transactions are the natural default.

    :param session: An async SQLAlchemy session, typically injected via
        :func:`app.api.dependencies.db.get_db_session`.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Public API ──────────────────────────────────────────────────────────

    async def commit(self) -> None:
        """Commit the current transaction.

        :raises Exception: Delegated from :meth:`AsyncSession.commit` — caller
            is responsible for handling and rolling back.
        """
        await self._session.commit()
        logger.debug("unit_of_work_committed")

    async def rollback(self) -> None:
        """Roll back the current transaction.

        Safe to call even if no transaction is active (nested rollback in
        ``finally`` blocks).
        """
        await self._session.rollback()
        logger.debug("unit_of_work_rolled_back")

    async def flush(self) -> None:
        """Flush pending changes to the database without committing.

        Useful when a service needs the generated primary key of a newly
        created record before the transaction commits.
        """
        await self._session.flush()

    @property
    def session(self) -> AsyncSession:
        """Return the underlying async session.

        Repositories receive this directly. Services should generally not
        access it — use :meth:`transaction` instead.
        """
        return self._session

    # ── Transaction context manager ─────────────────────────────────────────

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[UnitOfWork, None]:
        """Async context manager that wraps work in a database transaction.

        Commits on success, rolls back on any exception.  Relies on
        SQLAlchemy 2.x autobegin (transactions start on the first execute)
        so no explicit ``begin()`` call is needed here.

        Usage (the documented pattern from ``docs/03-ARCHITECTURE.md`` §9)::

            async with self.uow.transaction():
                patient = await self._patients.create(...)
                await self._audit.log("patient.created", ...)

        :yields: This :class:`UnitOfWork` instance so the caller can access
            ``.session`` or call ``.flush()`` if needed.
        """
        try:
            yield self
            await self.commit()
        except Exception:
            logger.exception("unit_of_work_failed")
            await self.rollback()
            raise


__all__ = [
    "UnitOfWork",
]
