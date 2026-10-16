"""Provision a new hospital with its first administrator (``docs/modules/14-hospital-settings.md`` §5).

Platform-level work: it creates a tenant, so it runs in the platform's system
scope and only for a holder of ``platform.hospital.provision`` (Super Admin),
or from ``make provision-hospital``, which is run by the operators.

**One transaction.** The hospital row, the administrator account, their
Hospital Admin role and the audit entries commit together, in the single
commit :meth:`UserService.invite_user` makes, or not at all: a failure
anywhere leaves no hospital without an administrator (§5).

**No credential leaves here.** The administrator is invited exactly as any
user is: their one-time activation link goes only to their mailbox, never to
the caller, the terminal or the log. With no mail transport, the account stays
invited and the invitation is sent again once email is configured.

The system roles (``hospital_id`` NULL) are shared by every hospital, so there
is no per-hospital role catalogue to copy (§5 step 3).
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for type hints
from typing import TYPE_CHECKING, Final

from app.core.audit import AuditEvent, AuditSink
from app.core.exceptions import ConfigurationError, ConflictError
from app.core.logging import get_logger
from app.core.tenancy import TenantScope, cross_tenant, tenant_scope
from app.schemas.hospital_provisioning import ProvisionedHospitalResponse

if TYPE_CHECKING:
    from app.repositories.hospital_repository import HospitalRepository
    from app.repositories.role_repository import RoleRepository
    from app.schemas.hospital_provisioning import ProvisionHospitalRequest
    from app.services.user_service import UserService

__all__ = ["HOSPITAL_ADMIN_ROLE", "HospitalProvisioningService"]

logger = get_logger(__name__)

#: The seeded system role a new hospital's first administrator holds.
HOSPITAL_ADMIN_ROLE: Final = "Hospital Admin"

_SLUG_TAKEN: Final = "That slug is already used by another hospital."


class HospitalProvisioningService:
    """Creates a hospital and invites its first administrator, atomically.

    :param hospitals: Hospital data access.
    :param roles: Role data access, to find the Hospital Admin system role.
    :param users: Invites the administrator; its commit is the transaction's.
    :param audit: Where ``hospital.provisioned`` is recorded.
    """

    def __init__(
        self,
        hospitals: HospitalRepository,
        roles: RoleRepository,
        users: UserService,
        audit: AuditSink,
    ) -> None:
        self._hospitals = hospitals
        self._roles = roles
        self._users = users
        self._audit = audit

    async def provision(
        self,
        payload: ProvisionHospitalRequest,
        *,
        actor_id: uuid.UUID | None,
        actor_permissions: list[str] | None,
    ) -> ProvisionedHospitalResponse:
        """Create the hospital and invite its administrator (§5).

        :param payload: The validated hospital and administrator.
        :param actor_id: The Super Admin provisioning it, or ``None`` for the
            operators' command.
        :param actor_permissions: What the actor holds. The invitation grants
            the Hospital Admin role, so the actor must hold every permission
            that role carries (no privilege escalation), as for any invite.
            ``None`` for a platform principal (a Super Admin with no hospital,
            or the operators' command), who holds every permission implicitly.
        :returns: The hospital, the administrator, and whether their email was queued.
        :raises ConflictError: If the slug, or the administrator's email, is taken.
        :raises ConfigurationError: If the Hospital Admin role has not been seeded.
        """
        # Hospitals are not tenant rows: the uniqueness question spans all of them.
        with tenant_scope(TenantScope.system("hospital slugs are unique across the platform")):
            if await self._hospitals.get_by_slug(payload.slug) is not None:
                raise ConflictError(_SLUG_TAKEN, detail={"field": "slug"})
            role = await self._roles.get_by_name(None, HOSPITAL_ADMIN_ROLE)
        if role is None:
            msg = f"The '{HOSPITAL_ADMIN_ROLE}' system role is missing: run `make seed`."
            raise ConfigurationError(msg)
        if actor_permissions is None:
            # A platform principal holds everything; say so in the terms the
            # invite's escalation check reads: every code the role grants.
            actor_permissions = await self._role_codes(role.id) + ["user.create"]

        with tenant_scope(TenantScope.system("provisioning a new hospital")):
            hospital = await self._hospitals.create(
                name=payload.name,
                slug=payload.slug,
                address=payload.address,
                phone=payload.phone,
                email=payload.email,
                timezone=payload.timezone,
                currency=payload.currency,
                is_active=True,
            )
        # Everything from here is written inside the new hospital. The request
        # is otherwise confined to the caller's own hospital, which would refuse
        # these rows; the scope names the one hospital they belong to.
        with tenant_scope(TenantScope.hospital(hospital.id)):
            await self._audit.record(
                AuditEvent(
                    action="hospital.provisioned",
                    hospital_id=hospital.id,
                    target_type="hospital",
                    target_id=hospital.id,
                    actor_id=actor_id,
                    context={"slug": hospital.slug},
                )
            )

            # Commits the whole provisioning: hospital, audit entry, admin, role.
            admin, delivery = await self._users.invite_user(
                hospital.id,
                email=payload.admin.email,
                first_name=payload.admin.first_name,
                last_name=payload.admin.last_name,
                phone=payload.admin.phone,
                role_ids=[role.id],
                actor_permissions=actor_permissions,
                actor_id=actor_id,
            )
        logger.info(
            "hospital_provisioned",
            hospital_id=str(hospital.id),
            slug=hospital.slug,
            invitation=delivery.value,
        )
        return ProvisionedHospitalResponse(
            hospital_id=hospital.id,
            name=hospital.name,
            slug=hospital.slug,
            admin_user_id=admin.id,
            admin_email=admin.email,
            invitation="queued" if delivery.value == "queued" else "unavailable",
        )

    async def _role_codes(self, role_id: uuid.UUID) -> list[str]:
        """The permission codes a system role grants."""
        role = await self._roles.get_with_permissions(
            role_id, hospital_id=cross_tenant("a system role's permissions, for provisioning")
        )
        if role is None:  # pragma: no cover — found by name a moment ago
            return []
        return [rp.permission.code for rp in role.role_permissions if rp.permission is not None]
