"""Model base and column mixins for all SQLAlchemy models.

Every database model inherits from :class:`Base` (re-exported here from
:mod:`app.database.base_class`) plus the mixins it needs:

- :class:`UUIDPrimaryKeyMixin` — ``id`` UUID primary key
- :class:`TimestampMixin` — ``created_at``, ``updated_at``, ``created_by``, ``updated_by``
- :class:`SoftDeleteMixin` — ``deleted_at``, ``deleted_by``
- :class:`TenantMixin` — ``hospital_id`` for multi-tenant isolation
- :class:`CommonColumnsMixin` — timestamps + soft delete combined

Usage::

    from app.models.base import Base, CommonColumnsMixin, UUIDPrimaryKeyMixin

    class Patient(UUIDPrimaryKeyMixin, CommonColumnsMixin, Base):
        __tablename__ = "patients"
"""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003 — needed at runtime for Mapped[datetime] resolution

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.database.base_class import Base

__all__ = [
    "Base",
    "CommonColumnsMixin",
    "SoftDeleteMixin",
    "TenantMixin",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
]


class TimestampMixin:
    """Adds created_at, updated_at, created_by, and updated_by columns.

    Every table must include these audit columns.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when the record was created (UTC).",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Timestamp when the record was last updated (UTC).",
    )

    @declared_attr
    def created_by(cls) -> Mapped[uuid.UUID | None]:  # noqa: N805
        """UUID of the user who created this record. NULL for system-seeded rows."""
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="UUID of the creating user. NULL for system rows.",
        )

    @declared_attr
    def updated_by(cls) -> Mapped[uuid.UUID | None]:  # noqa: N805
        """UUID of the user who last updated this record."""
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="UUID of the last updating user.",
        )


class SoftDeleteMixin:
    """Adds deleted_at and deleted_by columns for soft deletion.

    Queries in the repository layer automatically filter out
    soft-deleted records unless explicitly requested.

    **Never DELETE FROM a business table.** Always soft-delete.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Timestamp of soft deletion (NULL = not deleted).",
    )

    @declared_attr
    def deleted_by(cls) -> Mapped[uuid.UUID | None]:  # noqa: N805
        """UUID of the user who soft-deleted this record."""
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="UUID of the user who soft-deleted this record.",
        )

    @property
    def is_deleted(self) -> bool:
        """True if this record has been soft-deleted."""
        return self.deleted_at is not None


class TenantMixin:
    """Adds hospital_id column for multi-tenant data isolation.

    Every business table must have a hospital_id column.
    The repository layer automatically filters by the current
    hospital context.
    """

    @declared_attr
    def hospital_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805
        """UUID of the hospital (tenant) that owns this record.

        Used by the base repository to enforce multi-tenant isolation.
        Every query automatically filters by this value.
        """
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey("hospitals.id", ondelete="RESTRICT"),
            nullable=False,
            comment="UUID of the owning hospital (tenant).",
        )


class CommonColumnsMixin(TimestampMixin, SoftDeleteMixin):
    """Combines audit timestamps and soft-delete columns.

    Most business models should inherit from this mixin to get
    all common columns with a single declaration.
    """


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary key column named ``id``.

    Every table must use UUID primary keys (no auto-increment).
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="UUID primary key (generated in application code).",
    )
