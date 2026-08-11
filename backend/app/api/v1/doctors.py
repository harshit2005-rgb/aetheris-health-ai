"""Doctor Management API routes.

Implements the endpoint set in ``docs/modules/04-doctor-management.md`` §9.
Routes parse input, delegate to
:class:`~app.services.doctor_service.DoctorService`, and wrap the result in the
standard envelope. They contain no business logic
(``docs/03-ARCHITECTURE.md`` §15, rule 1) and never touch the database (rule 2).

**Tenancy.** ``hospital_id`` always comes from the authenticated user, never
from the request body or a query parameter.

**Permissions.** Every endpoint declares one via ``require_permission``
(``docs/07-SECURITY.md``, rule 4), using the codes from module spec §10 —
including the finer-grained ``doctor.availability.*`` and ``doctor.leave.*``
codes, so a doctor can manage their own schedule without holding full
``doctor.update``.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.dependencies.auth import require_permission
from app.api.dependencies.services import get_doctor_service
from app.core.exceptions import BusinessRuleError
from app.models.user import User
from app.schemas.common import (
    MetadataWithPagination,
    PaginatedResponse,
    PaginationMeta,
    PaginationParams,
    SuccessResponse,
)
from app.schemas.doctor import (
    AvailabilityResponse,
    CreateDoctorRequest,
    CreateLeaveRequest,
    DaySlotsResponse,
    DoctorResponse,
    DoctorSummaryResponse,
    LeaveResponse,
    SetAvailabilityRequest,
    UpdateDoctorRequest,
)
from app.services.doctor_service import DoctorService

router = APIRouter(prefix="/doctors", tags=["Doctors"])

#: Responses every doctor endpoint can return, for the OpenAPI schema
#: (``docs/06-API_STANDARDS.md`` §22).
_COMMON_RESPONSES: dict[int | str, dict[str, str]] = {
    401: {"description": "Missing or invalid access token."},
    403: {"description": "Authenticated but lacking the required permission."},
    422: {"description": "Request failed validation."},
}

_NOT_FOUND_RESPONSE: dict[int | str, dict[str, str]] = {
    404: {"description": "Doctor not found in this hospital."},
}


def _tenant_of(current_user: User) -> uuid.UUID:
    """Return the hospital the request acts within.

    A Super Admin has no ``hospital_id``, so there is no tenant to scope doctor
    access to. Rather than silently querying across tenants — which would
    breach CLAUDE.md rule 5 — the request is rejected.

    :param current_user: The authenticated user.
    :returns: The hospital UUID to scope every query by.
    :raises BusinessRuleError: If the user belongs to no hospital.
    """
    if current_user.hospital_id is None:
        msg = "This account is not scoped to a hospital, so doctors cannot be accessed."
        raise BusinessRuleError(msg)
    return current_user.hospital_id


# ── Doctor profile ──────────────────────────────────────────────────────────


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[DoctorResponse],
    summary="Onboard a doctor",
    description=(
        "Create a doctor profile for an existing user (module spec §5.1).\n\n"
        "The user must already exist in this hospital — this module does not "
        "create logins. A user can have at most one doctor profile."
    ),
    responses={
        201: {"description": "Doctor onboarded."},
        409: {"description": "This user already has a doctor profile."},
        **_COMMON_RESPONSES,
    },
)
async def create_doctor(
    payload: CreateDoctorRequest,
    current_user: User = Depends(require_permission("doctor.create")),
    service: DoctorService = Depends(get_doctor_service),
) -> SuccessResponse[DoctorResponse]:
    """Onboard a doctor against an existing user."""
    doctor = await service.create_doctor(
        _tenant_of(current_user), payload, actor_id=current_user.id
    )
    return SuccessResponse[DoctorResponse](message="Doctor onboarded successfully.", data=doctor)


@router.get(
    "",
    response_model=PaginatedResponse[DoctorSummaryResponse],
    summary="List and search doctors",
    description=(
        "Return a page of doctors in the caller's hospital.\n\n"
        "`q` matches a name prefix case-insensitively or an exact licence "
        "number. `specialization` and `department` are exact filters. Results "
        "are ordered by specialization. Deactivated doctors are excluded unless "
        "`include_inactive` is set."
    ),
    responses={200: {"description": "Page of doctors returned."}, **_COMMON_RESPONSES},
)
async def list_doctors(
    q: str | None = Query(None, max_length=100, description="Name prefix or exact licence."),
    specialization: str | None = Query(None, max_length=100, description="Exact specialization."),
    department: uuid.UUID | None = Query(None, description="Department UUID to filter by."),
    include_inactive: bool = Query(False, description="Include deactivated doctors."),
    page: int = Query(1, ge=1, description="1-based page number."),
    page_size: int = Query(25, ge=1, le=100, description="Records per page."),
    current_user: User = Depends(require_permission("doctor.read")),
    service: DoctorService = Depends(get_doctor_service),
) -> PaginatedResponse[DoctorSummaryResponse]:
    """List or search doctors (module spec §9)."""
    page_result = await service.list_doctors(
        _tenant_of(current_user),
        term=q,
        specialization=specialization,
        department_id=department,
        include_inactive=include_inactive,
        pagination=PaginationParams(page=page, page_size=page_size),
    )
    return PaginatedResponse[DoctorSummaryResponse](
        message="Doctors retrieved.",
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
    "/{doctor_id}",
    response_model=SuccessResponse[DoctorResponse],
    summary="Get a doctor",
    description="Return one doctor's full profile, including department and fee.",
    responses={
        200: {"description": "Doctor returned."},
        **_NOT_FOUND_RESPONSE,
        **_COMMON_RESPONSES,
    },
)
async def get_doctor(
    doctor_id: uuid.UUID = Path(description="Doctor UUID."),
    include_inactive: bool = Query(False, description="Return the record even if deactivated."),
    current_user: User = Depends(require_permission("doctor.read")),
    service: DoctorService = Depends(get_doctor_service),
) -> SuccessResponse[DoctorResponse]:
    """Retrieve one doctor by UUID."""
    doctor = await service.get_doctor_details(
        _tenant_of(current_user), doctor_id, include_inactive=include_inactive
    )
    return SuccessResponse[DoctorResponse](message="Doctor retrieved.", data=doctor)


@router.patch(
    "/{doctor_id}",
    response_model=SuccessResponse[DoctorResponse],
    summary="Update a doctor",
    description=(
        "Apply a partial update. Only fields present in the body are changed.\n\n"
        "The linked user and owning hospital are immutable and are rejected if "
        "supplied. Sending `department_id: null` unassigns the doctor from "
        "their department."
    ),
    responses={
        200: {"description": "Doctor updated."},
        **_NOT_FOUND_RESPONSE,
        **_COMMON_RESPONSES,
    },
)
async def update_doctor(
    payload: UpdateDoctorRequest,
    doctor_id: uuid.UUID = Path(description="Doctor UUID."),
    current_user: User = Depends(require_permission("doctor.update")),
    service: DoctorService = Depends(get_doctor_service),
) -> SuccessResponse[DoctorResponse]:
    """Partially update a doctor."""
    doctor = await service.update_doctor(
        _tenant_of(current_user), doctor_id, payload, actor_id=current_user.id
    )
    return SuccessResponse[DoctorResponse](message="Doctor updated.", data=doctor)


@router.delete(
    "/{doctor_id}",
    response_model=SuccessResponse[DoctorResponse],
    summary="Deactivate a doctor",
    description=(
        "Deactivate a doctor by soft-deleting the record.\n\n"
        "The row is never removed: appointments, consultations, and invoices "
        "keep referencing it.\n\n"
        "Refused with 409 while the doctor has future appointments — cancel or "
        "reassign them first (module spec §4 rule 7, FR-5)."
    ),
    responses={
        200: {"description": "Doctor deactivated."},
        400: {"description": "Doctor is already deactivated."},
        409: {"description": "The doctor still has future appointments."},
        **_NOT_FOUND_RESPONSE,
        **_COMMON_RESPONSES,
    },
)
async def deactivate_doctor(
    doctor_id: uuid.UUID = Path(description="Doctor UUID."),
    current_user: User = Depends(require_permission("doctor.delete")),
    service: DoctorService = Depends(get_doctor_service),
) -> SuccessResponse[DoctorResponse]:
    """Soft-delete a doctor."""
    doctor = await service.deactivate_doctor(
        _tenant_of(current_user), doctor_id, actor_id=current_user.id
    )
    return SuccessResponse[DoctorResponse](message="Doctor deactivated.", data=doctor)


@router.post(
    "/{doctor_id}/activate",
    response_model=SuccessResponse[DoctorResponse],
    summary="Reactivate a doctor",
    description="Reactivate a previously deactivated doctor by clearing its soft delete.",
    responses={
        200: {"description": "Doctor reactivated."},
        400: {"description": "Doctor is already active."},
        **_NOT_FOUND_RESPONSE,
        **_COMMON_RESPONSES,
    },
)
async def activate_doctor(
    doctor_id: uuid.UUID = Path(description="Doctor UUID."),
    current_user: User = Depends(require_permission("doctor.update")),
    service: DoctorService = Depends(get_doctor_service),
) -> SuccessResponse[DoctorResponse]:
    """Clear the soft delete on a doctor."""
    doctor = await service.activate_doctor(
        _tenant_of(current_user), doctor_id, actor_id=current_user.id
    )
    return SuccessResponse[DoctorResponse](message="Doctor reactivated.", data=doctor)


# ── Availability ────────────────────────────────────────────────────────────


@router.get(
    "/{doctor_id}/availability",
    response_model=SuccessResponse[list[AvailabilityResponse]],
    summary="Get a doctor's weekly availability",
    description=(
        "Return every availability window, ordered by day then start time.\n\n"
        "`day_of_week` is 0=Monday .. 6=Sunday. Times are wall-clock in the "
        "hospital's timezone."
    ),
    responses={
        200: {"description": "Availability returned."},
        **_NOT_FOUND_RESPONSE,
        **_COMMON_RESPONSES,
    },
)
async def get_availability(
    doctor_id: uuid.UUID = Path(description="Doctor UUID."),
    current_user: User = Depends(require_permission("doctor.availability.read")),
    service: DoctorService = Depends(get_doctor_service),
) -> SuccessResponse[list[AvailabilityResponse]]:
    """Return a doctor's weekly availability."""
    windows = await service.get_availability(_tenant_of(current_user), doctor_id)
    return SuccessResponse[list[AvailabilityResponse]](
        message="Availability retrieved.", data=windows
    )


@router.put(
    "/{doctor_id}/availability",
    response_model=SuccessResponse[list[AvailabilityResponse]],
    summary="Replace a doctor's weekly availability",
    description=(
        "Replace the entire weekly schedule (module spec §5.2).\n\n"
        "This is a full replace, not a merge: whatever is sent becomes the "
        "complete schedule, and omitted days are cleared. Sending an empty "
        "`entries` list removes all availability.\n\n"
        "Windows on the same day must not overlap. Windows that touch — one "
        "ending exactly when the next begins — are fine, and are how a "
        "mid-day change of slot duration is expressed."
    ),
    responses={
        200: {"description": "Availability replaced."},
        **_NOT_FOUND_RESPONSE,
        **_COMMON_RESPONSES,
    },
)
async def set_availability(
    payload: SetAvailabilityRequest,
    doctor_id: uuid.UUID = Path(description="Doctor UUID."),
    current_user: User = Depends(require_permission("doctor.availability.update")),
    service: DoctorService = Depends(get_doctor_service),
) -> SuccessResponse[list[AvailabilityResponse]]:
    """Replace a doctor's weekly availability atomically."""
    windows = await service.set_availability(
        _tenant_of(current_user), doctor_id, payload, actor_id=current_user.id
    )
    return SuccessResponse[list[AvailabilityResponse]](
        message="Availability updated.", data=windows
    )


# ── Leaves ──────────────────────────────────────────────────────────────────


@router.get(
    "/{doctor_id}/leaves",
    response_model=SuccessResponse[list[LeaveResponse]],
    summary="List a doctor's leaves",
    description="Return every recorded leave for a doctor, earliest first.",
    responses={
        200: {"description": "Leaves returned."},
        **_NOT_FOUND_RESPONSE,
        **_COMMON_RESPONSES,
    },
)
async def list_leaves(
    doctor_id: uuid.UUID = Path(description="Doctor UUID."),
    current_user: User = Depends(require_permission("doctor.read")),
    service: DoctorService = Depends(get_doctor_service),
) -> SuccessResponse[list[LeaveResponse]]:
    """List a doctor's leaves."""
    leaves = await service.list_leaves(_tenant_of(current_user), doctor_id)
    return SuccessResponse[list[LeaveResponse]](message="Leaves retrieved.", data=leaves)


@router.post(
    "/{doctor_id}/leaves",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[LeaveResponse],
    summary="Record a leave",
    description=(
        "Record a time-off interval (module spec §5.3). Auto-approved in MVP.\n\n"
        "`starts_at` and `ends_at` must carry a UTC offset — a naive timestamp "
        "is rejected rather than guessed at. The interval is half-open, so a "
        "leave ending at 09:00 leaves the 08:30-09:00 slot bookable.\n\n"
        "Overlapping an existing leave is rejected with 409.\n\n"
        "The response metadata lists appointments that fall inside the leave, "
        "so they can be reassigned."
    ),
    responses={
        201: {"description": "Leave recorded."},
        409: {"description": "The leave overlaps an existing one."},
        **_NOT_FOUND_RESPONSE,
        **_COMMON_RESPONSES,
    },
)
async def create_leave(
    payload: CreateLeaveRequest,
    doctor_id: uuid.UUID = Path(description="Doctor UUID."),
    current_user: User = Depends(require_permission("doctor.leave.create")),
    service: DoctorService = Depends(get_doctor_service),
) -> SuccessResponse[LeaveResponse]:
    """Record an auto-approved leave."""
    leave, affected = await service.create_leave(
        _tenant_of(current_user), doctor_id, payload, actor_id=current_user.id
    )
    message = "Leave recorded."
    if affected:
        message = f"Leave recorded. {len(affected)} appointment(s) need reassignment."
    return SuccessResponse[LeaveResponse](message=message, data=leave)


@router.delete(
    "/{doctor_id}/leaves/{leave_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a leave",
    description=(
        "Cancel a leave by soft-deleting it. The doctor's slots for that "
        "window become bookable again."
    ),
    responses={
        204: {"description": "Leave cancelled."},
        404: {"description": "Leave or doctor not found in this hospital."},
        **_COMMON_RESPONSES,
    },
)
async def delete_leave(
    doctor_id: uuid.UUID = Path(description="Doctor UUID."),
    leave_id: uuid.UUID = Path(description="Leave UUID."),
    current_user: User = Depends(require_permission("doctor.leave.delete")),
    service: DoctorService = Depends(get_doctor_service),
) -> None:
    """Soft-delete a leave."""
    await service.delete_leave(
        _tenant_of(current_user), doctor_id, leave_id, actor_id=current_user.id
    )


# ── Slots ───────────────────────────────────────────────────────────────────


@router.get(
    "/{doctor_id}/slots",
    response_model=SuccessResponse[DaySlotsResponse],
    summary="Compute a doctor's slots for a date",
    description=(
        "Return the doctor's bookable slots for one date (module spec §5.4).\n\n"
        "Slots are a **read model**: computed on demand from availability, "
        "leaves, and existing appointments, never stored. Each slot is "
        "`available`, `booked` (with its `appointment_id`), or `on_leave`.\n\n"
        "Times are returned in the hospital's timezone, which is echoed in the "
        "`timezone` field. Availability is wall-clock, so on a daylight-saving "
        "transition the day has the number of hours the local clock says it "
        "has."
    ),
    responses={
        200: {"description": "Slots computed."},
        **_NOT_FOUND_RESPONSE,
        **_COMMON_RESPONSES,
    },
)
async def get_slots(
    doctor_id: uuid.UUID = Path(description="Doctor UUID."),
    slot_date: date = Query(alias="date", description="Date to compute, as YYYY-MM-DD."),
    current_user: User = Depends(require_permission("doctor.availability.read")),
    service: DoctorService = Depends(get_doctor_service),
) -> SuccessResponse[DaySlotsResponse]:
    """Compute one day's slots for a doctor."""
    slots = await service.get_slots(_tenant_of(current_user), doctor_id, slot_date)
    return SuccessResponse[DaySlotsResponse](message="Slots computed.", data=slots)
