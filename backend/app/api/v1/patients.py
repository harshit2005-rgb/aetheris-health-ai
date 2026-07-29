"""Patient management API routes.

Implements the endpoint set in ``docs/modules/03-patient-management.md`` §9.
Routes parse input, delegate to :class:`~app.services.patient_service.PatientService`,
and wrap the result in the standard envelope. They contain no business logic
(``docs/03-ARCHITECTURE.md`` §15, rule 1) and never touch the database (rule 2).

**Tenancy.** ``hospital_id`` always comes from the authenticated user, never
from the request body or a query parameter. A caller cannot reach another
tenant's records by asking for them.

**Permissions.** Every endpoint declares one via ``require_permission``
(``docs/07-SECURITY.md``, rule 4). The codes are seeded in
``app/seeds/seed.py``.

Documents, timeline, and AI summary (module spec §9) are not implemented here:
they depend on object storage and the AI service, which are later sprints.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.dependencies.auth import require_permission
from app.api.dependencies.services import get_patient_service
from app.core.exceptions import BusinessRuleError
from app.models.patient import Gender
from app.models.user import User
from app.schemas.common import (
    MetadataWithPagination,
    PaginatedResponse,
    PaginationMeta,
    PaginationParams,
    SuccessResponse,
)
from app.schemas.patient import (
    CreatePatientRequest,
    PatientResponse,
    PatientSummaryResponse,
    SearchPatientRequest,
    UpdatePatientRequest,
)
from app.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["Patients"])

#: Responses every patient endpoint can return, for the OpenAPI schema
#: (``docs/06-API_STANDARDS.md`` §22).
_COMMON_RESPONSES: dict[int | str, dict[str, str]] = {
    401: {"description": "Missing or invalid access token."},
    403: {"description": "Authenticated but lacking the required permission."},
    422: {"description": "Request failed validation."},
}

_NOT_FOUND_RESPONSE: dict[int | str, dict[str, str]] = {
    404: {"description": "Patient not found in this hospital."},
}


def _tenant_of(current_user: User) -> uuid.UUID:
    """Return the hospital the request acts within.

    A Super Admin has no ``hospital_id`` (``docs/05-DATABASE_DESIGN.md`` §2.2),
    so there is no tenant to scope patient access to. Rather than silently
    querying across tenants — which would breach CLAUDE.md rule 5 — the request
    is rejected. Cross-tenant access is a separate, audited capability
    (``backend/CLAUDE.md``, "Multi-Tenancy Enforcement").

    :param current_user: The authenticated user.
    :returns: The hospital UUID to scope every query by.
    :raises BusinessRuleError: If the user belongs to no hospital.
    """
    if current_user.hospital_id is None:
        msg = "This account is not scoped to a hospital, so patient records cannot be accessed."
        raise BusinessRuleError(msg)
    return current_user.hospital_id


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[PatientResponse],
    summary="Register a patient",
    description=(
        "Register a new patient and generate their Medical Record Number.\n\n"
        "The MRN is generated server-side, is unique per hospital, and follows "
        "the hospital's configured format. It cannot be supplied by the client."
    ),
    responses={
        201: {"description": "Patient registered."},
        409: {"description": "Could not allocate a free Medical Record Number."},
        **_COMMON_RESPONSES,
    },
)
async def register_patient(
    payload: CreatePatientRequest,
    current_user: User = Depends(require_permission("patient.create")),
    service: PatientService = Depends(get_patient_service),
) -> SuccessResponse[PatientResponse]:
    """Register a patient (module spec §5.1)."""
    patient = await service.register_patient(
        _tenant_of(current_user),
        payload,
        actor_id=current_user.id,
    )
    return SuccessResponse[PatientResponse](
        message="Patient registered successfully.",
        data=patient,
    )


@router.get(
    "",
    response_model=PaginatedResponse[PatientSummaryResponse],
    summary="List and search patients",
    description=(
        "Return a page of patients in the caller's hospital.\n\n"
        "`q` matches a name prefix case-insensitively, or an exact Medical "
        "Record Number or phone number. Results are ordered by last name, then "
        "first name. Deactivated patients are excluded unless "
        "`include_inactive` is set."
    ),
    responses={200: {"description": "Page of patients returned."}, **_COMMON_RESPONSES},
)
async def list_patients(
    q: str | None = Query(
        None, max_length=100, description="Name prefix, exact MRN, or exact phone."
    ),
    gender: Gender | None = Query(None, description="Filter by gender."),
    date_of_birth: date | None = Query(None, description="Filter by exact date of birth."),
    age_gte: int | None = Query(None, ge=0, le=130, description="Minimum age in years."),
    age_lte: int | None = Query(None, ge=0, le=130, description="Maximum age in years."),
    include_inactive: bool = Query(False, description="Include deactivated patients."),
    page: int = Query(1, ge=1, description="1-based page number."),
    page_size: int = Query(25, ge=1, le=100, description="Records per page."),
    current_user: User = Depends(require_permission("patient.read")),
    service: PatientService = Depends(get_patient_service),
) -> PaginatedResponse[PatientSummaryResponse]:
    """List or search patients (module spec §5.5)."""
    hospital_id = _tenant_of(current_user)
    pagination = PaginationParams(page=page, page_size=page_size)

    filters = SearchPatientRequest(
        q=q,
        gender=gender,
        date_of_birth=date_of_birth,
        age_gte=age_gte,
        age_lte=age_lte,
        include_inactive=include_inactive,
    )

    # An unfiltered request is a list, not a search. Keeping them apart means
    # the audit trail does not record every page view as a patient search.
    is_search = any(
        value is not None for value in (filters.q, filters.gender, filters.date_of_birth)
    ) or any(value is not None for value in (filters.age_gte, filters.age_lte))

    if is_search:
        page_result = await service.search_patients(
            hospital_id,
            filters,
            pagination=pagination,
            actor_id=current_user.id,
        )
    else:
        page_result = await service.list_patients(
            hospital_id,
            pagination=pagination,
            include_inactive=include_inactive,
        )

    return PaginatedResponse[PatientSummaryResponse](
        message="Patients retrieved.",
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
    "/{patient_id}",
    response_model=SuccessResponse[PatientResponse],
    summary="Get a patient",
    description="Return one patient's full record, including medical history.",
    responses={
        200: {"description": "Patient returned."},
        **_NOT_FOUND_RESPONSE,
        **_COMMON_RESPONSES,
    },
)
async def get_patient(
    patient_id: uuid.UUID = Path(description="Patient UUID."),
    include_inactive: bool = Query(False, description="Return the record even if deactivated."),
    current_user: User = Depends(require_permission("patient.read")),
    service: PatientService = Depends(get_patient_service),
) -> SuccessResponse[PatientResponse]:
    """Retrieve one patient by UUID."""
    patient = await service.get_patient_details(
        _tenant_of(current_user),
        patient_id,
        include_inactive=include_inactive,
    )
    return SuccessResponse[PatientResponse](message="Patient retrieved.", data=patient)


@router.patch(
    "/{patient_id}",
    response_model=SuccessResponse[PatientResponse],
    summary="Update a patient",
    description=(
        "Apply a partial update. Only fields present in the request body are "
        "changed; omitting a field leaves it untouched.\n\n"
        "The Medical Record Number and owning hospital are immutable and are "
        "rejected if supplied."
    ),
    responses={
        200: {"description": "Patient updated."},
        **_NOT_FOUND_RESPONSE,
        **_COMMON_RESPONSES,
    },
)
async def update_patient(
    payload: UpdatePatientRequest,
    patient_id: uuid.UUID = Path(description="Patient UUID."),
    current_user: User = Depends(require_permission("patient.update")),
    service: PatientService = Depends(get_patient_service),
) -> SuccessResponse[PatientResponse]:
    """Partially update a patient (module spec §5.2)."""
    patient = await service.update_patient(
        _tenant_of(current_user),
        patient_id,
        payload,
        actor_id=current_user.id,
    )
    return SuccessResponse[PatientResponse](message="Patient updated.", data=patient)


@router.delete(
    "/{patient_id}",
    response_model=SuccessResponse[PatientResponse],
    summary="Deactivate a patient",
    description=(
        "Deactivate a patient by soft-deleting the record.\n\n"
        "The row is never removed: appointments, invoices, and lab reports keep "
        "referencing it. Deactivated patients are excluded from list and search "
        "results. Returns the updated record so the caller can see the new "
        "status without a second request."
    ),
    responses={
        200: {"description": "Patient deactivated."},
        400: {"description": "Patient is already deactivated."},
        **_NOT_FOUND_RESPONSE,
        **_COMMON_RESPONSES,
    },
)
async def deactivate_patient(
    patient_id: uuid.UUID = Path(description="Patient UUID."),
    current_user: User = Depends(require_permission("patient.delete")),
    service: PatientService = Depends(get_patient_service),
) -> SuccessResponse[PatientResponse]:
    """Soft-delete a patient (module spec §4, rule 4)."""
    patient = await service.deactivate_patient(
        _tenant_of(current_user),
        patient_id,
        actor_id=current_user.id,
    )
    return SuccessResponse[PatientResponse](message="Patient deactivated.", data=patient)
