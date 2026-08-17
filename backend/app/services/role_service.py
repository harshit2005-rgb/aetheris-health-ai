"""Business logic for the Roles & Permissions module (read side).

Implements the business rules from ``docs/modules/02-user-management.md`` §4
and the read-only scope of §9/§19:

- A role with ``hospital_id IS NULL`` is a **system role**: visible to every
  tenant, mutable by none.
- Listing returns system roles plus the caller's hospital roles — never
  another tenant's.
- A single-role lookup that misses (or belongs to another tenant) is a 404,
  indistinguishable from absence — the same cross-tenant rule the department
  module enforces.

The permissions catalog is globally seeded and read-only in the MVP; there is
deliberately no write path here (handoff conflict C1 — custom role CRUD is
v2.2).

Returns Pydantic DTOs, never ORM models (``docs/03-ARCHITECTURE.md`` §15,
rule 7). Reads are not mutating operations, so no audit events fire
(CLAUDE.md rule 9 covers mutations only).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.exceptions import NotFoundError
from app.schemas.common import Page, PaginationParams
from app.schemas.role import PermissionResponse, RoleDetailResponse, RoleResponse

if TYPE_CHECKING:
    import uuid

    from app.models.role import Role
    from app.repositories.permission_repository import PermissionRepository
    from app.repositories.role_repository import RoleRepository

__all__ = ["RoleNotFoundError", "RoleService"]


class RoleNotFoundError(NotFoundError):
    """Raised when a role does not exist in the requested scope.

    Also raised when the role exists but belongs to a *different* hospital:
    a cross-tenant lookup must be indistinguishable from a miss, or the
    404/403 difference leaks the existence of another tenant's records.
    """

    def __init__(self, role_id: uuid.UUID) -> None:
        super().__init__(
            message="Role not found.",
            detail={"role_id": str(role_id)},
        )


class RoleService:
    """Role and permission read operations.

    :param roles: Role data access.
    :param permissions: Permission data access.
    """

    def __init__(self, roles: RoleRepository, permissions: PermissionRepository) -> None:
        self._roles = roles
        self._permissions = permissions

    # ── Queries ───────────────────────────────────────────────────────────────

    async def list_roles(
        self,
        hospital_id: uuid.UUID,
        *,
        pagination: PaginationParams | None = None,
    ) -> Page[RoleResponse]:
        """List the roles visible to a hospital.

        System roles (``hospital_id IS NULL``) plus the hospital's own roles,
        ordered by name. Never another tenant's roles (CLAUDE.md rule 5).

        :param hospital_id: The tenant to list roles for.
        :param pagination: Page and page size. Defaults to page 1.
        :returns: One page of role summaries plus the total count.
        """
        page_params = pagination or PaginationParams()

        rows = await self._roles.list_by_hospital(
            hospital_id,
            skip=page_params.offset,
            limit=page_params.limit,
            include_system=True,
        )
        total = await self._roles.count_by_hospital(hospital_id, include_system=True)

        return Page[RoleResponse](
            items=[RoleResponse.from_model(row) for row in rows],
            page=page_params.page,
            page_size=page_params.page_size,
            total_records=total,
        )

    async def get_role(
        self,
        hospital_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> RoleDetailResponse:
        """Retrieve one role with its permission codes.

        :param hospital_id: The tenant acting.
        :param role_id: The role's UUID.
        :returns: The role's full record.
        :raises RoleNotFoundError: If the role is absent from this tenant's
            scope (including another tenant's role).
        """
        role = await self._roles.get_with_permissions(role_id, hospital_id=hospital_id)
        if role is None:
            raise RoleNotFoundError(role_id)
        return self._to_detail(role)

    async def list_permissions(
        self,
        *,
        pagination: PaginationParams | None = None,
        module: str | None = None,
    ) -> Page[PermissionResponse]:
        """List the global permissions catalog, optionally filtered by module.

        Permissions are global and read-only; there is no tenant scoping
        (``docs/modules/02-user-management.md`` §9).

        :param pagination: Page and page size. Defaults to page 1.
        :param module: Optional module filter, e.g. ``"patient"``.
        :returns: One page of permissions plus the total count.
        """
        page_params = pagination or PaginationParams()

        rows = await self._permissions.list_all(
            skip=page_params.offset,
            limit=page_params.limit,
            module=module,
        )
        total = await self._permissions.count_all(module=module)

        return Page[PermissionResponse](
            items=[PermissionResponse.model_validate(row) for row in rows],
            page=page_params.page,
            page_size=page_params.page_size,
            total_records=total,
        )

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _to_detail(role: Role) -> RoleDetailResponse:
        """Build a detail DTO with the role's permission codes sorted.

        :param role: The ORM instance with ``role_permissions`` loaded.
        :returns: The populated DTO.
        """
        codes = sorted(rp.permission.code for rp in (role.role_permissions or []) if rp.permission)
        return RoleDetailResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            is_system=role.is_system,
            hospital_id=role.hospital_id,
            permission_codes=codes,
        )
