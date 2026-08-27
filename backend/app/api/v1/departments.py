"""Department API routes.

Implements the endpoint set in ``docs/modules/14-hospital-settings.md`` §9.
Routes parse input, delegate to
:class:`~app.services.department_service.DepartmentService`, and wrap the
result in the standard envelope. They contain no business logic
(``docs/03-ARCHITECTURE.md`` §15, rule 1) and never touch the database (rule 2).

**Tenancy.** ``hospital_id`` always comes from the authenticated user, never
from the request body or a query parameter. A caller cannot reach another
tenant's records by asking for them.

**Permissions.** Every endpoint declares one via ``require_permission``
(``docs/07-SECURITY.md``, rule 4). The codes are seeded in
``app/seeds/seed.py``.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.dependencies.auth import require_permission
from app.api.dependencies.services import get_department_service
from app.core.exceptions import BusinessRuleError
from app.models.user import User
from app.schemas.common import (
    MetadataWithPagination,
    PaginatedResponse,
    PaginationMeta,
    PaginationParams,
    SuccessResponse,
)
from app.schemas.department import (
    CreateDepartmentRequest,
    DepartmentResponse,
    DepartmentSummaryResponse,
    SearchDepartmentRequest,
    UpdateDepartmentRequest,
)
from app.services.department_service import DepartmentService

router = APIRouter(prefix="/departments", tags=["Departments"])

#: Responses every department endpoint can return, for the OpenAPI schema
#: (``docs/06-API_STANDARDS.md`` §22).
_COMMON_RESPONSES: dict[int | str, dict[str, str]] = {
    401: {"description": "Missing or invalid access token."},
    403: {"description": "Authenticated but lacking the required permission."},
    422: {"description": "Request failed validation."},
}

_NOT_FOUND_RESPONSE: dict[int | str, dict[str, str]] = {
    404: {"description": "Department not found in this hospital."},
}


def _tenant_of(current_user: User) -> uuid.UUID:
    """Return the hospital the request acts within.

    A Super Admin has no ``hospital_id`` (``docs/05-DATABASE_DESIGN.md`` §2.2),
    so there is no tenant to scope department access to. Rather than silently
    querying across tenants — which would breach CLAUDE.md rule 5 — the request
    is rejected. Cross-tenant access is a separate, audited capability
    (``backend/CLAUDE.md``, "Multi-Tenancy Enforcement").

    :param current_user: The authenticated user.
    :returns: The hospital UUID to scope every query by.
    :raises BusinessRuleError: If the user belongs to no hospital.
    """
    if current_user.hospital_id is None:
        msg = "This account is not scoped to a hospital, so departments cannot be accessed."
        raise BusinessRuleError(msg)
    return current_user.hospital_id


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[DepartmentResponse],
    summary="Create a department",
    description=(
        "Create a department in the caller's hospital.\n\n"
        "`code` is uppercased automatically, so `card` and `CARD` are the same "
        "code. Both `code` and `name` must be unique within the hospital; "
        "`name` is compared case-insensitively."
    ),
    responses={
        201: {"description": "Department created."},
        409: {"description": "A department with this code or name already exists."},
        **_COMMON_RESPONSES,
    },
)
async def create_department(
    payload: CreateDepartmentRequest,
    current_user: User = Depends(require_permission("department.create")),
    service: DepartmentService = Depends(get_department_service),
) -> SuccessResponse[DepartmentResponse]:
    """Create a department (module spec §9)."""
    department = await service.create_department(
        _tenant_of(current_user),
        payload,
        actor_id=current_user.id,
    )
    return SuccessResponse[DepartmentResponse](
        message="Department created successfully.",
        data=department,
    )


@router.get(
    "",
    response_model=PaginatedResponse[DepartmentSummaryResponse],
    summary="List and search departments",
    description=(
        "Return a page of departments in the caller's hospital.\n\n"
        "`q` matches a name prefix case-insensitively, or an exact code. "
        "Results are ordered by name. Deactivated departments are excluded "
        "unless `include_inactive` is set."
    ),
    responses={200: {"description": "Page of departments returned."}, **_COMMON_RESPONSES},
)
async def list_departments(
    q: str | None = Query(None, max_length=150, description="Name prefix or exact code."),
    include_inactive: bool = Query(False, description="Include deactivated departments."),
    page: int = Query(1, ge=1, description="1-based page number."),
    page_size: int = Query(25, ge=1, le=100, description="Records per page."),
    current_user: User = Depends(require_permission("department.read")),
    service: DepartmentService = Depends(get_department_service),
) -> PaginatedResponse[DepartmentSummaryResponse]:
    """List or search departments (module spec §9)."""
    hospital_id = _tenant_of(current_user)
    pagination = PaginationParams(page=page, page_size=page_size)

    filters = SearchDepartmentRequest(q=q, include_inactive=include_inactive)

    # An unfiltered request is a list, not a search. Keeping them apart means
    # the audit trail does not record every page view as a department search.
    if filters.q is not None:
        page_result = await service.search_departments(
            hospital_id,
            filters,
            pagination=pagination,
            actor_id=current_user.id,
        )
    else:
        page_result = await service.list_departments(
            hospital_id,
            pagination=pagination,
            include_inactive=include_inactive,
        )

    return PaginatedResponse[DepartmentSummaryResponse](
        message="Departments retrieved.",
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
    "/{department_id}",
    response_model=SuccessResponse[DepartmentResponse],
    summary="Get a department",
    description="Return one department's full record.",
    responses={
        200: {"description": "Department returned."},
        **_NOT_FOUND_RESPONSE,
        **_COMMON_RESPONSES,
    },
)
async def get_department(
    department_id: uuid.UUID = Path(description="Department UUID."),
    include_inactive: bool = Query(False, description="Return the record even if deactivated."),
    current_user: User = Depends(require_permission("department.read")),
    service: DepartmentService = Depends(get_department_service),
) -> SuccessResponse[DepartmentResponse]:
    """Retrieve one department by UUID."""
    department = await service.get_department_details(
        _tenant_of(current_user),
        department_id,
        include_inactive=include_inactive,
    )
    return SuccessResponse[DepartmentResponse](message="Department retrieved.", data=department)


@router.patch(
    "/{department_id}",
    response_model=SuccessResponse[DepartmentResponse],
    summary="Update a department",
    description=(
        "Apply a partial update. Only fields present in the request body are "
        "changed; omitting a field leaves it untouched.\n\n"
        "The owning hospital is immutable and is rejected if supplied. "
        "Changing `code` or `name` re-checks uniqueness within the hospital."
    ),
    responses={
        200: {"description": "Department updated."},
        409: {"description": "A department with this code or name already exists."},
        **_NOT_FOUND_RESPONSE,
        **_COMMON_RESPONSES,
    },
)
async def update_department(
    payload: UpdateDepartmentRequest,
    department_id: uuid.UUID = Path(description="Department UUID."),
    current_user: User = Depends(require_permission("department.update")),
    service: DepartmentService = Depends(get_department_service),
) -> SuccessResponse[DepartmentResponse]:
    """Partially update a department (module spec §9)."""
    department = await service.update_department(
        _tenant_of(current_user),
        department_id,
        payload,
        actor_id=current_user.id,
    )
    return SuccessResponse[DepartmentResponse](message="Department updated.", data=department)


@router.delete(
    "/{department_id}",
    response_model=SuccessResponse[DepartmentResponse],
    summary="Deactivate a department",
    description=(
        "Deactivate a department by soft-deleting the record.\n\n"
        "The row is never removed: doctors and appointments keep referencing "
        "it. Deactivated departments are excluded from list and search results "
        "unless `include_inactive` is set.\n\n"
        "Refused with 409 while active doctors are still assigned to the "
        "department — reassign or deactivate them first."
    ),
    responses={
        200: {"description": "Department deactivated."},
        400: {"description": "Department is already deactivated."},
        409: {"description": "Active doctors are still assigned to this department."},
        **_NOT_FOUND_RESPONSE,
        **_COMMON_RESPONSES,
    },
)
async def deactivate_department(
    department_id: uuid.UUID = Path(description="Department UUID."),
    current_user: User = Depends(require_permission("department.delete")),
    service: DepartmentService = Depends(get_department_service),
) -> SuccessResponse[DepartmentResponse]:
    """Soft-delete a department (module spec §4, rules 12 and 13)."""
    department = await service.deactivate_department(
        _tenant_of(current_user),
        department_id,
        actor_id=current_user.id,
    )
    return SuccessResponse[DepartmentResponse](message="Department deactivated.", data=department)


@router.post(
    "/{department_id}/activate",
    response_model=SuccessResponse[DepartmentResponse],
    summary="Reactivate a department",
    description=(
        "Reactivate a previously deactivated department by clearing its soft "
        "delete. The department reappears in list and search results."
    ),
    responses={
        200: {"description": "Department reactivated."},
        400: {"description": "Department is already active."},
        **_NOT_FOUND_RESPONSE,
        **_COMMON_RESPONSES,
    },
)
async def activate_department(
    department_id: uuid.UUID = Path(description="Department UUID."),
    current_user: User = Depends(require_permission("department.update")),
    service: DepartmentService = Depends(get_department_service),
) -> SuccessResponse[DepartmentResponse]:
    """Clear the soft delete on a department."""
    department = await service.activate_department(
        _tenant_of(current_user),
        department_id,
        actor_id=current_user.id,
    )
    return SuccessResponse[DepartmentResponse](message="Department reactivated.", data=department)
