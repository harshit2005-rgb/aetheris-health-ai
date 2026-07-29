"""Dependency injection wiring for every service.

One provider per service, each composing the repositories it needs. Routes
depend on these — never on repositories directly.

Placement rule (``docs/09-PROJECT_STRUCTURE.md``): every new service added
under ``app/services/`` gets a provider in this module.

Usage::

    from typing import Annotated

    from fastapi import Depends

    from app.api.dependencies import get_patient_service
    from app.services import PatientService

    async def handler(
        patients: Annotated[PatientService, Depends(get_patient_service)],
    ):
        ...
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.db import get_db_session
from app.api.dependencies.repositories import (
    get_mrn_sequence_repository,
    get_patient_repository,
)
from app.core.audit import AuditSink, StructlogAuditSink
from app.repositories import MrnSequenceRepository, PatientRepository
from app.services import MRNService, PatientService

__all__ = [
    "get_audit_sink",
    "get_mrn_service",
    "get_patient_service",
]

#: Request-scoped database session. Services receive it to own the transaction
#: boundary (``docs/03-ARCHITECTURE.md`` §9), never to query through directly.
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_audit_sink() -> AuditSink:
    """Provide the audit sink every service records mutations to.

    Returns the interim structlog-backed sink. When
    ``docs/modules/12-audit-logs.md`` ships, this provider returns the
    database-backed ``AuditService`` instead and no service changes.
    """
    return StructlogAuditSink()


def get_mrn_service(
    sequences: Annotated[MrnSequenceRepository, Depends(get_mrn_sequence_repository)],
) -> MRNService:
    """Provide an :class:`MRNService` bound to the request session."""
    return MRNService(sequences)


def get_patient_service(
    patients: Annotated[PatientRepository, Depends(get_patient_repository)],
    mrn_service: Annotated[MRNService, Depends(get_mrn_service)],
    session: DbSession,
    audit: Annotated[AuditSink, Depends(get_audit_sink)],
) -> PatientService:
    """Provide a :class:`PatientService` bound to the request session.

    All four collaborators share the same request-scoped session, so the
    service's ``commit()`` covers every write made through them.
    """
    return PatientService(patients, mrn_service, session, audit)
