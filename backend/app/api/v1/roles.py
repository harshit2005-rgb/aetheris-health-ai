"""Roles & Permissions API routes.

Implements the endpoint set in ``docs/modules/02-user-management.md`` §9 for
the MVP's read-only scope: list roles, get one role with its permissions, and
read the global permissions catalog. Custom role CRUD is v2.2 (handoff
conflict C1), so there is deliberately no write side here.

Routes parse input, delegate to
:class:`~app.services.role_service.RoleService`, and wrap the result in the
standard envelope. They contain no business logic
(``docs/03-ARCHITECTURE.md`` §15, rule 1) and never touch the database (rule 2).

**Tenancy.** ``hospital_id`` always comes from the authenticated user. System
roles are visible to every tenant; another tenant's hospital roles are a 404.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.api.dependencies.auth import require_permission
from app.api.dependencies.services import get_role_service
from app.core.exceptions import BusinessRuleError
from app.models.user import User
from app.schemas.common import (
    MetadataWithPagination,
    PaginatedResponse,
    PaginationMeta,
    SuccessResponse,
)
from app.schemas.role import (
    PermissionListQuery,
    PermissionResponse,
    RoleDetailResponse,
    RoleListQuery,
    RoleResponse,
)
from app.services.role_service import RoleService

router = APIRouter(prefix="/roles", tags=["Roles & Permissions"])
permission_router = APIRouter(prefix="/permissions", tags=["Roles & Permissions"])

#: Responses every role endpoint can return, for the OpenAPI schema
#: (``docs/06-API_STANDARDS.md`` §22).
_COMMON_RESPONSES: dict[int | str, dict[str, str]] = {
    401: {"description": "Missing or invalid access token."},
    403: {"description": "Authenticated but lacking the required permission."},
    422: {"description": "Request failed validation."},
}

_NOT_FOUND_RESPONSE: dict[int | str, dict[str, str]] = {
    404: {"description": "Role not found in this hospital's scope."},
}


def _tenant_of(current_user: User) -> uuid.UUID:
    """Return the hospital the request acts within.

    A Super Admin has no ``hospital_id``, so there is no tenant to scope role
    access to. Rather than silently querying across tenants — which would
    breach CLAUDE.md rule 5 — the request is rejected. Cross-tenant access is
    a separate, audited capability (``backend/CLAUDE.md``, "Multi-Tenancy
    Enforcement").

    :param current_user: The authenticated user.
    :returns: The hospital UUID to scope every query by.
    :raises BusinessRuleError: If the user belongs to no hospital.
    """
    if current_user.hospital_id is None:
        msg = "This account is not scoped to a hospital, so roles cannot be accessed."
        raise BusinessRuleError(msg)
    return current_user.hospital_id


@router.get(
    "",
    response_model=PaginatedResponse[RoleResponse],
    summary="List roles",
    description=(
        "Return a page of roles visible to the caller's hospital: the global "
        "system roles plus this hospital's own roles, ordered by name. Never "
        "another tenant's roles."
    ),
    responses={200: {"description": "Page of roles returned."}, **_COMMON_RESPONSES},
)
async def list_roles(
    query: Annotated[RoleListQuery, Query()],
    current_user: User = Depends(require_permission("role.read")),
    service: RoleService = Depends(get_role_service),
) -> PaginatedResponse[RoleResponse]:
    """List the roles visible to the caller (module spec §9)."""
    hospital_id = _tenant_of(current_user)
    page_result = await service.list_roles(hospital_id, pagination=query)

    return PaginatedResponse[RoleResponse](
        message="Roles retrieved.",
        data=page_result.items,
        metadata=MetadataWithPagination(
            pagination=PaginationMeta(
                page=page_result.page,
                page_size=page_result.page_size,
                total_records=page_result.total_records,
                total_pages=page_result.total_pages,
            ),
        ),
    )


@router.get(
    "/{role_id}",
    response_model=SuccessResponse[RoleDetailResponse],
    summary="Get a role",
    description=(
        "Return one role's full record, including the permission codes it "
        "grants. System roles are visible to every tenant; a role belonging to "
        "another hospital is indistinguishable from a missing one (404)."
    ),
    responses={
        200: {"description": "Role returned."},
        **_NOT_FOUND_RESPONSE,
        **_COMMON_RESPONSES,
    },
)
async def get_role(
    role_id: uuid.UUID = Path(description="Role UUID."),
    current_user: User = Depends(require_permission("role.read")),
    service: RoleService = Depends(get_role_service),
) -> SuccessResponse[RoleDetailResponse]:
    """Retrieve one role by UUID (module spec §9)."""
    role = await service.get_role(_tenant_of(current_user), role_id)
    return SuccessResponse[RoleDetailResponse](message="Role retrieved.", data=role)


@permission_router.get(
    "",
    response_model=PaginatedResponse[PermissionResponse],
    summary="List permissions",
    description=(
        "Return a page of the global, read-only permissions catalog. "
        "Optionally filter to one module, e.g. ``?module=patient``. "
        "Permissions are seeded and never modified through the application."
    ),
    responses={200: {"description": "Page of permissions returned."}, **_COMMON_RESPONSES},
)
async def list_permissions(
    query: Annotated[PermissionListQuery, Query()],
    current_user: User = Depends(require_permission("role.read")),
    service: RoleService = Depends(get_role_service),
) -> PaginatedResponse[PermissionResponse]:
    """List the permissions catalog (module spec §9)."""
    page_result = await service.list_permissions(
        pagination=query,
        module=query.module,
    )

    return PaginatedResponse[PermissionResponse](
        message="Permissions retrieved.",
        data=page_result.items,
        metadata=MetadataWithPagination(
            pagination=PaginationMeta(
                page=page_result.page,
                page_size=page_result.page_size,
                total_records=page_result.total_records,
                total_pages=page_result.total_pages,
            ),
        ),
    )
