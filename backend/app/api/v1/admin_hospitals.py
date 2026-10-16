"""Platform routes for provisioning hospitals (``docs/modules/14-hospital-settings.md`` §5, §9).

Only a holder of ``platform.hospital.provision`` (Super Admin) reaches them.
The route parses, delegates to :class:`HospitalProvisioningService` and
responds; it never returns the new administrator's activation link, which
goes only to their mailbox.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencies.auth import require_permission, user_permission_codes
from app.api.dependencies.services import get_hospital_provisioning_service
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.hospital_provisioning import ProvisionedHospitalResponse, ProvisionHospitalRequest
from app.services.hospital_provisioning_service import HospitalProvisioningService

router = APIRouter(prefix="/admin/hospitals", tags=["Platform — Hospitals"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[ProvisionedHospitalResponse],
    summary="Provision a new hospital",
    description=(
        "Create a hospital and invite its first administrator, with the Hospital "
        "Admin role, in one transaction (module spec §5). The administrator gets "
        "a one-time activation link by email only; it is never in this response. "
        "`invitation` says whether that email was queued.\\n\\n"
        "`slug` is permanent and unique (§4 rule 3). Defaults: `Asia/Kolkata`, `INR`."
    ),
    responses={
        201: {"description": "Hospital provisioned."},
        401: {"description": "Missing or invalid access token."},
        403: {"description": "Lacking platform.hospital.provision."},
        409: {"description": "The slug or the administrator's email is already in use."},
        422: {"description": "Request failed validation."},
    },
)
async def provision_hospital(
    payload: ProvisionHospitalRequest,
    current_user: User = Depends(require_permission("platform.hospital.provision")),
    service: HospitalProvisioningService = Depends(get_hospital_provisioning_service),
) -> SuccessResponse[ProvisionedHospitalResponse]:
    """Provision a hospital with its first administrator."""
    result = await service.provision(
        payload,
        actor_id=current_user.id,
        # A platform-level Super Admin (no hospital) holds every code implicitly.
        actor_permissions=None
        if current_user.hospital_id is None
        else sorted(user_permission_codes(current_user)),
    )
    return SuccessResponse[ProvisionedHospitalResponse](
        message="Hospital provisioned.", data=result
    )
