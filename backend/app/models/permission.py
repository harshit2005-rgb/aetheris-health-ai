"""Permission model — atomic, globally-scoped access rights.

Permissions are seeded via migration and never modified through the
application. See :mod:`app.models.role` for the role-to-permission join.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.role import RolePermission


class Permission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An atomic access right (e.g. ``patient.create``, ``billing.approve_discount``).

    Permissions are global — they are not scoped to any hospital.
    They are seeded once and never modified. New permissions are
    added via migration, never through the application.
    """

    __tablename__ = "permissions"

    __table_args__ = (
        UniqueConstraint("code", name="uq_permissions_code"),
        Index("ix_permissions_module", "module"),
    )

    code: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Unique permission code (e.g. 'patient.create').",
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Human-readable explanation of what this permission grants.",
    )
    module: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Module this permission belongs to (e.g. 'patient', 'billing').",
    )

    # ── Relationships ───────────────────────────────────────────────────
    role_permissions: Mapped[list[RolePermission]] = relationship(
        "RolePermission",
        back_populates="permission",
        foreign_keys="RolePermission.permission_id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Permission id={self.id!s:.8} code={self.code!r}>"
