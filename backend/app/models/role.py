"""Role model and the role-to-permission join table.

A role is a named collection of permissions, scoped to a hospital. System
roles (``is_system = True``) have ``hospital_id = NULL`` and cannot be deleted.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Mapped[uuid.UUID] resolution
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CommonColumnsMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.hospital import Hospital
    from app.models.permission import Permission
    from app.models.user import UserRole


class Role(UUIDPrimaryKeyMixin, CommonColumnsMixin, Base):
    """A named collection of permissions.

    Roles are scoped to a hospital (``hospital_id``). System roles
    (e.g. Super Admin) may have ``hospital_id = NULL`` and
    ``is_system = True``. System roles cannot be deleted.
    """

    __tablename__ = "roles"

    __table_args__ = (
        UniqueConstraint("hospital_id", "name", name="uq_roles_hospital_name"),
        Index("ix_roles_is_system", "is_system"),
    )

    hospital_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="RESTRICT"),
        nullable=True,
        comment="UUID of the hospital this role belongs to. NULL for system roles.",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Display name (e.g. 'Doctor', 'Receptionist').",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable description of the role.",
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="System roles cannot be deleted or modified.",
    )

    # ── Relationships ───────────────────────────────────────────────────
    hospital: Mapped[Hospital | None] = relationship(
        "Hospital",
        back_populates="roles",
        foreign_keys="Role.hospital_id",
        lazy="joined",
    )
    user_roles: Mapped[list[UserRole]] = relationship(
        "UserRole",
        back_populates="role",
        foreign_keys="UserRole.role_id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    role_permissions: Mapped[list[RolePermission]] = relationship(
        "RolePermission",
        back_populates="role",
        foreign_keys="RolePermission.role_id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Role id={self.id!s:.8} name={self.name!r}>"


class RolePermission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Many-to-many join between :class:`Role` and :class:`~app.models.permission.Permission`.

    Defines which permissions each role grants.
    """

    __tablename__ = "role_permissions"

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_perm"),
        Index("ix_role_permissions_permission_id", "permission_id"),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        comment="UUID of the role.",
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
        comment="UUID of the permission granted to this role.",
    )

    # ── Relationships ───────────────────────────────────────────────────
    role: Mapped[Role] = relationship(
        "Role",
        back_populates="role_permissions",
        foreign_keys="RolePermission.role_id",
        lazy="joined",
    )
    permission: Mapped[Permission] = relationship(
        "Permission",
        back_populates="role_permissions",
        foreign_keys="RolePermission.permission_id",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<RolePermission role={self.role_id!s:.8} perm={self.permission_id!s:.8}>"
