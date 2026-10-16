"""Hospital model — the multi-tenant root entity.

Every user, patient, appointment, and business record belongs to exactly one
hospital. See :mod:`app.models.base` for the shared column mixins.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.role import Role
    from app.models.user import User


class Hospital(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A hospital or clinic — the multi-tenant root entity.

    Every user, patient, appointment, and business record belongs to
    exactly one hospital. Hospitals are deactivated via :attr:`is_active`
    rather than soft-deleted, because all foreign keys reference this table.
    """

    __tablename__ = "hospitals"

    __table_args__ = (
        UniqueConstraint("slug", name="uq_hospitals_slug"),
        Index("ix_hospitals_name", "name"),
        Index("ix_hospitals_is_active", "is_active"),
    )

    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="Full hospital name for display."
    )
    slug: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="URL-friendly unique identifier for the hospital."
    )
    address: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, comment="Structured address (street, city, state, zip, country)."
    )
    phone: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="Primary contact phone number."
    )
    email: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="Primary contact email address."
    )
    tax_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Government tax or business registration ID."
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="INR", comment="ISO 4217 currency code (e.g. INR, USD)."
    )
    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Asia/Kolkata",
        comment="IANA timezone (e.g. Asia/Kolkata).",
    )
    locale: Mapped[str] = mapped_column(
        String(10), nullable=False, default="en-IN", comment="Locale for formatting and i18n."
    )
    logo_url: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="URL to the hospital logo (stored in object storage)."
    )
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Hospital configuration (feature flags, hours, policies).",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the hospital is active. Deactivate rather than delete.",
    )

    # ── Relationships ───────────────────────────────────────────────────
    # `foreign_keys` is required on any relationship to `users`: the audit
    # mixins put created_by/updated_by/deleted_by FKs on almost every table,
    # so more than one FK path links these tables. Name the tenancy column.
    users: Mapped[list[User]] = relationship(
        "User",
        back_populates="hospital",
        foreign_keys="User.hospital_id",
        lazy="selectin",
    )
    roles: Mapped[list[Role]] = relationship(
        "Role",
        back_populates="hospital",
        foreign_keys="Role.hospital_id",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Hospital id={self.id!s:.8} name={self.name!r}>"
