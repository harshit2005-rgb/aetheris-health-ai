"""Pydantic DTOs for the Roles & Permissions module.

Request models validate query parameters before a service ever sees them
(``docs/07-SECURITY.md``, rule 5). Response models are the only role shapes
that cross the API boundary — SQLAlchemy models never do
(``docs/03-ARCHITECTURE.md`` §15, rule 7).

Scope per ``docs/modules/02-user-management.md`` §9 and §19: roles and the
permissions catalog are **read-only in the MVP** — roles are seeded and
system-owned. There are deliberately no create/update DTOs here; custom role
management is v2.2 (conflict C1 in the Week 1 handoff).

Usage::

    from app.schemas.role import PermissionResponse, RoleDetailResponse

    response = RoleDetailResponse.from_model(role, permission_codes=codes)
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Pydantic field resolution
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginationParams

if TYPE_CHECKING:
    from app.models.role import Role

__all__ = [
    "PermissionResponse",
    "RoleDetailResponse",
    "RoleListQuery",
    "RoleResponse",
]


class RoleResponse(BaseModel):
    """Compact role shape for list views and role pickers."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Role UUID.")
    name: str = Field(description="Role display name, e.g. 'Doctor'.")
    description: str | None = Field(description="Human-readable role summary.")
    is_system: bool = Field(description="System roles are seeded, shared, and mutable by none.")
    hospital_id: uuid.UUID | None = Field(
        description="Owning hospital UUID. NULL for system roles."
    )

    @classmethod
    def from_model(cls, role: Role) -> Self:
        """Build a summary DTO from an ORM instance.

        :param role: The ORM instance to convert.
        :returns: The populated DTO.
        """
        return cls(
            id=role.id,
            name=role.name,
            description=role.description,
            is_system=role.is_system,
            hospital_id=role.hospital_id,
        )


class RoleDetailResponse(RoleResponse):
    """Full role record including its permission codes."""

    permission_codes: list[str] = Field(
        default_factory=list,
        description="Permission codes granted by this role, sorted.",
    )


class PermissionResponse(BaseModel):
    """One entry in the read-only permissions catalog."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Permission UUID.")
    code: str = Field(description="Permission code, e.g. 'patient.create'.")
    description: str | None = Field(description="What this permission grants.")
    module: str = Field(description="Owning module, e.g. 'patient', 'billing'.")


class RoleListQuery(PaginationParams):
    """Query parameters for ``GET /api/v1/roles``.

    Pagination fields only — roles are not searchable in the MVP.
    """

    pass
