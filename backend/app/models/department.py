"""Department model — an organisational unit inside one hospital.

Departments (Cardiology, Radiology, Emergency) are the assignment target for
doctors (``docs/02-FEATURES.md`` feature 5.2) and a filter dimension for
Reports and Inventory. Columns follow ``docs/05-DATABASE_DESIGN.md`` §2.23 and
``docs/modules/14-hospital-settings.md`` §8 exactly.

**No ``status`` column.** Lifecycle state is *derived* from ``deleted_at`` —
see :attr:`Department.status`. This mirrors :mod:`app.models.patient`: a stored
status column would duplicate the soft-delete state and let the two disagree.
"Deactivate" is a soft delete; "activate" clears ``deleted_at``.

**No ``head_doctor_id`` yet.** ``departments`` and ``doctors`` reference each
other, so the column is added by a follow-up migration in the Doctor Management
module rather than at table creation.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Mapped[uuid.UUID] resolution
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CommonColumnsMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.hospital import Hospital

#: Allowed shape of a department code, kept identical to the
#: ``ck_departments_code_format`` check constraint in migration 0005. Declared
#: here so the model, the migration, and the Pydantic schema all state the same
#: rule rather than three drifting approximations of it.
CODE_PATTERN = r"^[A-Z0-9][A-Z0-9_-]{1,19}$"


class DepartmentStatus(StrEnum):
    """Derived lifecycle state of a department.

    Not a stored column — computed from ``deleted_at`` by
    :attr:`Department.status`. See the module docstring for why.
    """

    ACTIVE = "active"
    INACTIVE = "inactive"


class Department(UUIDPrimaryKeyMixin, CommonColumnsMixin, Base):
    """An organisational unit within a hospital.

    Every department belongs to exactly one hospital. Both ``code`` and
    ``name`` are unique within that hospital, and ``name`` uniqueness is
    case-insensitive (module spec §4, rule 11). Departments are never
    hard-deleted (rule 12).
    """

    __tablename__ = "departments"

    __table_args__ = (
        UniqueConstraint("hospital_id", "code", name="uq_departments_hospital_code"),
        # Case-insensitive name uniqueness, so "Cardiology" and "cardiology"
        # cannot coexist. A functional unique *index* rather than a UNIQUE
        # constraint because Postgres constraints cannot span an expression.
        Index(
            "uq_departments_hospital_name_lower",
            "hospital_id",
            text("lower(name)"),
            unique=True,
        ),
        # Named with the bare suffix: the metadata naming convention
        # (``ck_%(table_name)s_%(constraint_name)s``) expands this to
        # ``ck_departments_code_format``, matching migration 0005.
        CheckConstraint(f"code ~ '{CODE_PATTERN}'", name="code_format"),
        # Partial index for the common read: live departments in one hospital.
        Index(
            "ix_departments_hospital_active",
            "hospital_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        # Case-insensitive prefix search on name.
        Index(
            "ix_departments_name_lower",
            "hospital_id",
            text("lower(name) varchar_pattern_ops"),
        ),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # RESTRICT, not CASCADE: removing a hospital out from under its
        # departments would orphan every doctor assigned to them.
        ForeignKey("hospitals.id", ondelete="RESTRICT"),
        nullable=False,
        comment="UUID of the hospital (tenant) this department belongs to.",
    )
    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Short department code, e.g. 'CARD'. Uppercase, unique per hospital.",
    )
    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        comment="Department name, e.g. 'Cardiology'. Unique per hospital, case-insensitively.",
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Free-form description of what the department does."
    )
    phone_extension: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="Internal phone extension for the department."
    )
    email: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="Department inbox address."
    )
    location: Mapped[str | None] = mapped_column(
        String(150), nullable=True, comment="Physical location — floor, wing, or block."
    )

    # ── Relationships ───────────────────────────────────────────────────
    # `foreign_keys` is mandatory on every relationship touching a table the
    # audit mixins also point at: created_by/updated_by/deleted_by are FKs to
    # users.id, so SQLAlchemy sees multiple join paths (see backend/CLAUDE.md).
    #
    # `lazy="raise"` for the same reason Patient.hospital uses it: nothing in
    # this module needs the Hospital object — services carry `hospital_id`
    # directly — and Hospital.users is `lazy="selectin"`, so eager-loading it
    # would pull every user in the hospital on every department read.
    hospital: Mapped[Hospital] = relationship(
        "Hospital",
        foreign_keys="Department.hospital_id",
        lazy="raise",
    )

    # `doctors` back-populates onto this model when the Doctor Management
    # module lands. It is not declared here: a relationship to a model that
    # does not exist yet fails mapper configuration at import time.

    @property
    def status(self) -> DepartmentStatus:
        """Lifecycle state derived from ``deleted_at``.

        ``ACTIVE`` while ``deleted_at`` is NULL; ``INACTIVE`` once the record
        has been soft-deleted (deactivated).
        """
        return DepartmentStatus.INACTIVE if self.deleted_at is not None else DepartmentStatus.ACTIVE

    def __repr__(self) -> str:
        return f"<Department id={self.id!s:.8} code={self.code!r} hospital={self.hospital_id!s:.8}>"
