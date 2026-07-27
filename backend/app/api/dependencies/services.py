"""Dependency injection wiring for every service.

One provider per service, each composing the repositories it needs. Routes
depend on these — never on repositories directly.

Placement rule (``docs/09-PROJECT_STRUCTURE.md``): every new service added
under ``app/services/`` gets a provider in this module.

Pattern::

    from typing import Annotated

    async def handler(
        patient_service: Annotated[PatientService, Depends(get_patient_service)],
    ):
        ...
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.db import get_db_session

# ── Repository DI ────────────────────────────────────────────────────────────
# Re-exported here so routes and services import from a single dependencies
# module rather than picking between ``dependencies/`` sub-modules.
from app.api.dependencies.repositories import (  # noqa: F401
    DbSession,
    get_hospital_repository,
    get_permission_repository,
    get_refresh_token_repository,
    get_role_repository,
    get_user_repository,
)

# ── Dependency type aliases ──────────────────────────────────────────────────
_Session = Annotated[AsyncSession, Depends(get_db_session)]

# ── Service providers ───────────────────────────────────────────────────────
# These are populated as services are implemented. Each function creates a
# service instance composed with its required repositories.
#
# Example:
#
#     def get_hospital_service(
#         session: _Session,
#         hospital_repo: Annotated[HospitalRepository, Depends(get_hospital_repository)],
#         user_repo: Annotated[UserRepository, Depends(get_user_repository)],
#     ) -> HospitalService:
#         return HospitalService(
#             hospital_repo=hospital_repo,
#             user_repo=user_repo,
#         )


__all__ = [
    # Re-exports from repositories
    "DbSession",
    "get_hospital_repository",
    "get_permission_repository",
    "get_refresh_token_repository",
    "get_role_repository",
    "get_user_repository",
]
