"""Identity database models.

Provides the core identity and access control schema:

- :class:`Hospital` — Multi-tenant root (every user belongs to one)
- :class:`User` — System users with login credentials
- :class:`Role` — Named collections of permissions (hospital-scoped or global)
- :class:`Permission` — Atomic access rights (global)
- :class:`UserRole` — Many-to-many join between users and roles
- :class:`RolePermission` — Many-to-many join between roles and permissions
- :class:`RefreshToken` — Server-side refresh token store with rotation support

All models use UUID primary keys, audit timestamps, and soft delete
where appropriate. Models follow the conventions in
:mod:`app.shared.database.base`.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Mapped[uuid.UUID] resolution
from datetime import (  # noqa: TC003 — needed at runtime for Mapped[datetime] resolution
    UTC,
    datetime,
)
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database.base import (
    Base,
    CommonColumnsMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)

# ── Enums ───────────────────────────────────────────────────────────────────


class UserStatus(StrEnum):
    """Valid states for a user account."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    INVITED = "invited"


# ── Hospital ────────────────────────────────────────────────────────────────


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
        String(50), nullable=False, default="Asia/Kolkata", comment="IANA timezone (e.g. Asia/Kolkata)."
    )
    locale: Mapped[str] = mapped_column(
        String(10), nullable=False, default="en-IN", comment="Locale for formatting and i18n."
    )
    logo_url: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="URL to the hospital logo (stored in object storage)."
    )
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}",
        comment="Hospital configuration (feature flags, hours, policies).",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="Whether the hospital is active. Deactivate rather than delete.",
    )

    # ── Relationships ───────────────────────────────────────────────────
    users: Mapped[list[User]] = relationship(
        "User", back_populates="hospital", lazy="selectin"
    )
    roles: Mapped[list[Role]] = relationship(
        "Role", back_populates="hospital", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Hospital id={self.id!s:.8} name={self.name!r}>"


# ── User ────────────────────────────────────────────────────────────────────


class User(UUIDPrimaryKeyMixin, CommonColumnsMixin, Base):
    """A user who can authenticate and interact with the system.

    Every user belongs to exactly one hospital (Super Admin is a future
    consideration). Users are soft-deleted rather than permanently removed.
    """

    __tablename__ = "users"

    __table_args__ = (
        UniqueConstraint("hospital_id", "email", name="uq_users_hospital_email"),
        Index("ix_users_phone", "phone"),
        Index("ix_users_hospital_status", "hospital_id", "status"),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="RESTRICT"),
        nullable=False,
        comment="UUID of the hospital this user belongs to. NULL only for Super Admin.",
    )
    email: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="Login email address. Unique per hospital."
    )
    phone: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="Phone number for contact and SMS notifications."
    )
    password_hash: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Argon2id password hash."
    )
    first_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="User's given name."
    )
    last_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="User's family name."
    )
    status: Mapped[UserStatus] = mapped_column(
        SQLEnum(UserStatus, name="user_status", create_type=True),
        nullable=False, default=UserStatus.ACTIVE,
        comment="Current account status (active, suspended, invited).",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp of last successful login.",
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp of last password change.",
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Consecutive failed login attempts.",
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Account is locked until this timestamp.",
    )
    mfa_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="Whether MFA/TOTP is enabled.",
    )
    mfa_secret: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Encrypted TOTP secret. NULL if MFA is not set up.",
    )

    # ── Relationships ───────────────────────────────────────────────────
    hospital: Mapped[Hospital] = relationship(
        "Hospital", back_populates="users", lazy="joined"
    )
    user_roles: Mapped[list[UserRole]] = relationship(
        "UserRole", back_populates="user",
        cascade="all, delete-orphan", lazy="selectin",
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken", back_populates="user",
        cascade="all, delete-orphan", lazy="selectin",
    )

    @property
    def full_name(self) -> str:
        """Full display name."""
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<User id={self.id!s:.8} email={self.email!r} hospital={self.hospital_id!s:.8}>"


# ── Role ────────────────────────────────────────────────────────────────────


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
        String(100), nullable=False,
        comment="Display name (e.g. 'Doctor', 'Receptionist').",
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Human-readable description of the role.",
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="System roles cannot be deleted or modified.",
    )

    # ── Relationships ───────────────────────────────────────────────────
    hospital: Mapped[Hospital | None] = relationship(
        "Hospital", back_populates="roles", lazy="joined"
    )
    user_roles: Mapped[list[UserRole]] = relationship(
        "UserRole", back_populates="role",
        cascade="all, delete-orphan", lazy="selectin",
    )
    role_permissions: Mapped[list[RolePermission]] = relationship(
        "RolePermission", back_populates="role",
        cascade="all, delete-orphan", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Role id={self.id!s:.8} name={self.name!r}>"


# ── Permission ──────────────────────────────────────────────────────────────


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
        "RolePermission", back_populates="permission",
        cascade="all, delete-orphan", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Permission id={self.id!s:.8} code={self.code!r}>"


# ── UserRole (Join Table) ───────────────────────────────────────────────────


class UserRole(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Many-to-many join between :class:`User` and :class:`Role`.

    Records which roles are assigned to which users, including
    who performed the assignment.
    """

    __tablename__ = "user_roles"

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
        Index("ix_user_roles_role_id", "role_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="UUID of the user being assigned a role.",
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        comment="UUID of the role being assigned.",
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="UUID of the user who performed this assignment. NULL if system-assigned.",
    )

    # ── Relationships ───────────────────────────────────────────────────
    user: Mapped[User] = relationship(
        "User", back_populates="user_roles", lazy="joined"
    )
    role: Mapped[Role] = relationship(
        "Role", back_populates="user_roles", lazy="joined"
    )

    def __repr__(self) -> str:
        return f"<UserRole user={self.user_id!s:.8} role={self.role_id!s:.8}>"


# ── RolePermission (Join Table) ─────────────────────────────────────────────


class RolePermission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Many-to-many join between :class:`Role` and :class:`Permission`.

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
        "Role", back_populates="role_permissions", lazy="joined"
    )
    permission: Mapped[Permission] = relationship(
        "Permission", back_populates="role_permissions", lazy="joined"
    )

    def __repr__(self) -> str:
        return f"<RolePermission role={self.role_id!s:.8} perm={self.permission_id!s:.8}>"


# ── RefreshToken ────────────────────────────────────────────────────────────


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Server-side refresh token store with rotation support.

    Supports the token rotation pattern:
    1. Client presents refresh token → server hashes it and looks up by hash.
    2. If found and not revoked → issue new pair, revoke old token,
       set ``rotated_by_token_id`` to the new token's ID.
    3. If found and already revoked → **reuse detection**: invalidate
       ALL tokens for this user (token theft suspected).
    4. If not found → reject.

    Expired and revoked tokens are cleaned up by a background job.
    """

    __tablename__ = "refresh_tokens"

    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="UUID of the token owner.",
    )
    token_hash: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="SHA-256 hash of the opaque refresh token. Used for O(1) lookup.",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        comment="Token expiration timestamp (UTC). Default 7 days from issuance.",
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="Whether this token has been revoked.",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp when this token was revoked.",
    )
    rotated_by_token_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
        comment="UUID of the replacement token. NULL = current token. Enables rotation chain tracking.",
    )
    device_info: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="User-agent or device description at issuance.",
    )
    ip_address: Mapped[str | None] = mapped_column(
        INET, nullable=True,
        comment="IP address at token issuance.",
    )

    # ── Relationships ───────────────────────────────────────────────────
    user: Mapped[User] = relationship(
        "User", back_populates="refresh_tokens", lazy="joined"
    )
    rotated_by: Mapped[RefreshToken | None] = relationship(
        "RefreshToken",
        remote_side="RefreshToken.id",
        foreign_keys=[rotated_by_token_id],
        lazy="joined",
        uselist=False,
    )

    @property
    def is_expired(self) -> bool:
        """True if the token has passed its expiration time."""
        return datetime.now(UTC) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """True if the token is not revoked and not expired."""
        return not self.is_revoked and not self.is_expired

    def __repr__(self) -> str:
        return (
            f"<RefreshToken id={self.id!s:.8} "
            f"user={self.user_id!s:.8} "
            f"revoked={self.is_revoked}>"
        )
