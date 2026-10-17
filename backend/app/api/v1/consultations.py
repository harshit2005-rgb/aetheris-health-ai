"""Consultation (EMR) API routes (``docs/modules/16-consultation.md`` §9).

Routes parse input, delegate to
:class:`~app.services.consultation_service.ConsultationService`, and wrap the
result in the standard envelope. No business logic, no database access.

**Tenancy.** ``hospital_id`` always comes from the authenticated user.

**Ownership.** ``consultation.write`` lets a doctor write notes, but only for
their own visits: the service refuses anyone else with 403 (rule 3).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, Path, Query, status

from app.api.dependencies.auth import require_permission
from app.api.dependencies.services import get_consultation_service
from app.core.exceptions import BusinessRuleError
from app.models.consultation import ConsultationStatus
from app.models.user import User
from app.schemas.common import (
    MetadataWithPagination,
    PaginatedResponse,
    PaginationMeta,
    PaginationParams,
    SuccessResponse,
)
from app.schemas.consultation import (
    AddAddendumRequest,
    ConsultationResponse,
    ConsultationSummary,
    CreateConsultationRequest,
    RecordVitalsRequest,
    UpdateConsultationRequest,
)
from app.services.consultation_service import ConsultationService

router = APIRouter(prefix="/consultations", tags=["Consultations"])
appointment_router = APIRouter(prefix="/appointments", tags=["Consultations"])

_READ = "consultation.read"
_WRITE = "consultation.write"
_VITALS = "consultation.vitals.record"

_COMMON_RESPONSES: dict[int | str, dict[str, str]] = {
    401: {"description": "Missing or invalid access token."},
    403: {"description": "Lacking the permission, or not this visit's doctor."},
    422: {"description": "Request failed validation."},
}
_NOT_FOUND: dict[int | str, dict[str, str]] = {
    404: {"description": "Consultation or appointment not found in this hospital."},
}
_STATE: dict[int | str, dict[str, str]] = {
    400: {"description": "The note's or visit's status does not allow this."},
}


def _tenant_of(current_user: User) -> uuid.UUID:
    """Return the hospital the request acts within."""
    if current_user.hospital_id is None:
        msg = "This account is not scoped to a hospital, so consultations cannot be accessed."
        raise BusinessRuleError(msg)
    return current_user.hospital_id


@router.post(
    "",
    response_model=SuccessResponse[ConsultationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Start a consultation note",
    description=(
        "Start the note for a visit that is checked in, in progress or completed. "
        "Only the visit's doctor may. A visit has at most one note (`409`)."
    ),
    responses={
        201: {"description": "Note started."},
        409: {"description": "The visit already has a note."},
        **_STATE,
        **_NOT_FOUND,
        **_COMMON_RESPONSES,
    },
)
async def create_consultation(
    payload: CreateConsultationRequest = Body(...),
    current_user: User = Depends(require_permission(_WRITE)),
    service: ConsultationService = Depends(get_consultation_service),
) -> SuccessResponse[ConsultationResponse]:
    """Start a consultation note."""
    created = await service.create(_tenant_of(current_user), payload, actor_id=current_user.id)
    return SuccessResponse[ConsultationResponse](message="Consultation started.", data=created)


@router.get(
    "",
    response_model=PaginatedResponse[ConsultationSummary],
    summary="List consultations",
    description="Return a page of consultation notes, newest first.",
    responses={200: {"description": "Page returned."}, **_COMMON_RESPONSES},
)
async def list_consultations(
    patient_id: uuid.UUID | None = Query(None, description="Only this patient's notes."),
    doctor_id: uuid.UUID | None = Query(None, description="Only this doctor's notes."),
    appointment_id: uuid.UUID | None = Query(None, description="Only this visit's note."),
    note_status: ConsultationStatus | None = Query(
        None, alias="status", description="Only drafts or only finalized notes."
    ),
    page: int = Query(1, ge=1, description="1-based page number."),
    page_size: int = Query(25, ge=1, le=100, description="Records per page."),
    current_user: User = Depends(require_permission(_READ)),
    service: ConsultationService = Depends(get_consultation_service),
) -> PaginatedResponse[ConsultationSummary]:
    """List consultations."""
    result = await service.list_consultations(
        _tenant_of(current_user),
        pagination=PaginationParams(page=page, page_size=page_size),
        patient_id=patient_id,
        doctor_id=doctor_id,
        appointment_id=appointment_id,
        status=note_status,
    )
    return PaginatedResponse[ConsultationSummary](
        message="Consultations retrieved.",
        data=result.items,
        metadata=MetadataWithPagination(
            pagination=PaginationMeta(
                page=result.page,
                page_size=result.page_size,
                total_records=result.total_records,
                total_pages=result.total_pages,
            ),
        ),
    )


@router.get(
    "/{consultation_id}",
    response_model=SuccessResponse[ConsultationResponse],
    summary="Get a consultation",
    description="One note with its addenda and the visit's prescriptions and lab orders.",
    responses={200: {"description": "Note returned."}, **_NOT_FOUND, **_COMMON_RESPONSES},
)
async def get_consultation(
    consultation_id: uuid.UUID = Path(description="Consultation UUID."),
    current_user: User = Depends(require_permission(_READ)),
    service: ConsultationService = Depends(get_consultation_service),
) -> SuccessResponse[ConsultationResponse]:
    """Retrieve one consultation."""
    found = await service.get(_tenant_of(current_user), consultation_id, actor_id=current_user.id)
    return SuccessResponse[ConsultationResponse](message="Consultation retrieved.", data=found)


@router.patch(
    "/{consultation_id}",
    response_model=SuccessResponse[ConsultationResponse],
    summary="Update a draft consultation",
    description="Change clinical sections of a draft. Only the visit's doctor may.",
    responses={
        200: {"description": "Note updated."},
        **_STATE,
        **_NOT_FOUND,
        **_COMMON_RESPONSES,
    },
)
async def update_consultation(
    consultation_id: uuid.UUID = Path(description="Consultation UUID."),
    payload: UpdateConsultationRequest = Body(...),
    current_user: User = Depends(require_permission(_WRITE)),
    service: ConsultationService = Depends(get_consultation_service),
) -> SuccessResponse[ConsultationResponse]:
    """Update a draft consultation."""
    updated = await service.update(
        _tenant_of(current_user), consultation_id, payload, actor_id=current_user.id
    )
    return SuccessResponse[ConsultationResponse](message="Consultation saved.", data=updated)


@router.put(
    "/{consultation_id}/vitals",
    response_model=SuccessResponse[ConsultationResponse],
    summary="Record vitals",
    description="Record (replace) the vitals on a draft note.",
    responses={
        200: {"description": "Vitals recorded."},
        **_STATE,
        **_NOT_FOUND,
        **_COMMON_RESPONSES,
    },
)
async def record_vitals(
    consultation_id: uuid.UUID = Path(description="Consultation UUID."),
    payload: RecordVitalsRequest = Body(...),
    current_user: User = Depends(require_permission(_VITALS)),
    service: ConsultationService = Depends(get_consultation_service),
) -> SuccessResponse[ConsultationResponse]:
    """Record vitals on a consultation."""
    updated = await service.record_vitals(
        _tenant_of(current_user), consultation_id, payload.vitals, actor_id=current_user.id
    )
    return SuccessResponse[ConsultationResponse](message="Vitals recorded.", data=updated)


@router.post(
    "/{consultation_id}/finalize",
    response_model=SuccessResponse[ConsultationResponse],
    summary="Finalize a consultation",
    description=(
        "Lock the note. Needs a chief complaint and at least one diagnosis. "
        "After this it is never edited; add addenda instead."
    ),
    responses={
        200: {"description": "Note finalized."},
        **_STATE,
        **_NOT_FOUND,
        **_COMMON_RESPONSES,
    },
)
async def finalize_consultation(
    consultation_id: uuid.UUID = Path(description="Consultation UUID."),
    current_user: User = Depends(require_permission(_WRITE)),
    service: ConsultationService = Depends(get_consultation_service),
) -> SuccessResponse[ConsultationResponse]:
    """Finalize a consultation."""
    done = await service.finalize(
        _tenant_of(current_user), consultation_id, actor_id=current_user.id
    )
    return SuccessResponse[ConsultationResponse](message="Consultation finalized.", data=done)


@router.post(
    "/{consultation_id}/addenda",
    response_model=SuccessResponse[ConsultationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add an addendum",
    description="Add to a finalized note. Only the visit's doctor may.",
    responses={
        201: {"description": "Addendum added."},
        **_STATE,
        **_NOT_FOUND,
        **_COMMON_RESPONSES,
    },
)
async def add_addendum(
    consultation_id: uuid.UUID = Path(description="Consultation UUID."),
    payload: AddAddendumRequest = Body(...),
    current_user: User = Depends(require_permission(_WRITE)),
    service: ConsultationService = Depends(get_consultation_service),
) -> SuccessResponse[ConsultationResponse]:
    """Add an addendum to a finalized consultation."""
    updated = await service.add_addendum(
        _tenant_of(current_user), consultation_id, payload, actor_id=current_user.id
    )
    return SuccessResponse[ConsultationResponse](message="Addendum added.", data=updated)


@appointment_router.get(
    "/{appointment_id}/consultation",
    response_model=SuccessResponse[ConsultationResponse],
    summary="Get a visit's consultation",
    description="The note of one visit, or `404` if it has not been started.",
    responses={200: {"description": "Note returned."}, **_NOT_FOUND, **_COMMON_RESPONSES},
)
async def get_visit_consultation(
    appointment_id: uuid.UUID = Path(description="Appointment UUID."),
    current_user: User = Depends(require_permission(_READ)),
    service: ConsultationService = Depends(get_consultation_service),
) -> SuccessResponse[ConsultationResponse]:
    """Retrieve the consultation of one visit."""
    found = await service.get_for_appointment(
        _tenant_of(current_user), appointment_id, actor_id=current_user.id
    )
    return SuccessResponse[ConsultationResponse](message="Consultation retrieved.", data=found)


@appointment_router.put(
    "/{appointment_id}/consultation/vitals",
    response_model=SuccessResponse[ConsultationResponse],
    summary="Record a visit's vitals",
    description=(
        "Record the vitals for a visit, starting its draft note if there is none yet "
        "(how a nurse records vitals before the doctor sees the patient)."
    ),
    responses={
        200: {"description": "Vitals recorded."},
        **_STATE,
        **_NOT_FOUND,
        **_COMMON_RESPONSES,
    },
)
async def record_visit_vitals(
    appointment_id: uuid.UUID = Path(description="Appointment UUID."),
    payload: RecordVitalsRequest = Body(...),
    current_user: User = Depends(require_permission(_VITALS)),
    service: ConsultationService = Depends(get_consultation_service),
) -> SuccessResponse[ConsultationResponse]:
    """Record vitals for a visit."""
    updated = await service.record_vitals_for_appointment(
        _tenant_of(current_user), appointment_id, payload.vitals, actor_id=current_user.id
    )
    return SuccessResponse[ConsultationResponse](message="Vitals recorded.", data=updated)
