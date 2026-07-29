"""Dependency injection wiring for every service.

One provider per service, each composing the repositories it needs. Routes
depend on these — never on repositories directly.

Usage::

    from typing import Annotated

    from fastapi import Depends

    from app.api.dependencies.services import get_auth_service
    from app.services.auth_service import AuthService

    async def handler(
        auth: Annotated[AuthService, Depends(get_auth_service)],
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
    get_password_reset_token_repository,
    get_permission_repository,
    get_refresh_token_repository,
    get_role_repository,
    get_user_repository,
)
from app.repositories import (
    PasswordResetTokenRepository,
    PermissionRepository,
    RefreshTokenRepository,
    RoleRepository,
    UserRepository,
)
from app.services.auth_service import AuthService
from app.services.user_service import UserService


# ── Dependency type aliases ──────────────────────────────────────────────────
_Session = Annotated[AsyncSession, Depends(get_db_session)]


# ── Auth service ────────────────────────────────────────────────────────────
def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    refresh_token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
    password_reset_repo: PasswordResetTokenRepository = Depends(get_password_reset_token_repository),
) -> AuthService:
    """Provide an :class:`AuthService` composed with its repository dependencies."""
    return AuthService(
        user_repo=user_repo,
        refresh_token_repo=refresh_token_repo,
        password_reset_repo=password_reset_repo,
    )


# ── User service ────────────────────────────────────────────────────────────
def get_user_service(
    user_repo: UserRepository = Depends(get_user_repository),
    role_repo: RoleRepository = Depends(get_role_repository),
    permission_repo: PermissionRepository = Depends(get_permission_repository),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserService:
    """Provide a :class:`UserService` composed with its repository dependencies."""
    return UserService(
        user_repo=user_repo,
        role_repo=role_repo,
        permission_repo=permission_repo,
        auth_service=auth_service,
    )


__all__ = [
    # Re-exports from repositories
    "DbSession",
    "get_hospital_repository",
    "get_password_reset_token_repository",
    "get_permission_repository",
    "get_refresh_token_repository",
    "get_role_repository",
    "get_user_repository",
    # Service providers
    "get_auth_service",
    "get_user_service",
]

