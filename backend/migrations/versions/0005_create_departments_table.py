"""create departments table

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-30 10:00:00.000000

Creates the department schema (``docs/05-DATABASE_DESIGN.md`` §2.23,
``docs/modules/14-hospital-settings.md`` §8).

A department is an organisational unit inside one hospital — Cardiology,
Radiology, Emergency. Doctors are assigned to one (feature 5.2) and later
modules (Reports, Inventory) filter by it.

Two things deliberately absent:

**No ``status`` column.** Lifecycle state is derived from ``deleted_at``, the
same choice migration 0003 made for patients. A stored status column would
duplicate that state and let the two disagree.

**No ``head_doctor_id``.** ``departments`` and ``doctors`` reference each other,
so neither can carry its foreign key at creation time. The column is added by a
follow-up migration in the Doctor Management module, once ``doctors`` exists.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Allowed shape of a department code. Enforced in the database as well as in
#: the Pydantic schema: the service is reachable from seed scripts and
#: background jobs that never cross the API boundary, and a rule that only
#: holds for HTTP callers is not a rule.
_CODE_FORMAT = r"^[A-Z0-9][A-Z0-9_-]{1,19}$"


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "hospital_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("phone_extension", sa.String(10), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("location", sa.String(150), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "deleted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # ── Uniqueness (module spec §4, rule 11) ───────────────────────────────────
    # Both are enforced in the database, not just the service, so two concurrent
    # creates cannot both win. The service catches the resulting IntegrityError
    # and maps it to a 409.
    op.create_unique_constraint(
        "uq_departments_hospital_code", "departments", ["hospital_id", "code"]
    )

    # Name uniqueness is case-insensitive, so "Cardiology" and "cardiology"
    # cannot coexist. A plain unique constraint would allow both, which reads as
    # two departments to the database and one to every human looking at the list.
    # Expressed as a functional unique index because a UNIQUE *constraint*
    # cannot span an expression in Postgres.
    op.create_index(
        "uq_departments_hospital_name_lower",
        "departments",
        ["hospital_id", sa.text("lower(name)")],
        unique=True,
    )

    # ── Code format (docs/05-DATABASE_DESIGN.md §1.8) ──────────────────────────
    # Named with the bare suffix. The metadata naming convention for check
    # constraints is ``ck_%(table_name)s_%(constraint_name)s``, and Alembic
    # applies it to whatever is passed here — so spelling out the full
    # ``ck_departments_code_format`` would land in Postgres as
    # ``ck_departments_ck_departments_code_format`` and stop matching the model.
    # (The unique constraint above is unaffected: its convention interpolates
    # ``%(column_0_name)s`` rather than ``%(constraint_name)s``.)
    op.create_check_constraint(
        "code_format",
        "departments",
        sa.text(f"code ~ '{_CODE_FORMAT}'"),
    )

    # ── Read paths ─────────────────────────────────────────────────────────────
    # Partial index for the common case: listing live departments in one
    # hospital (docs/05-DATABASE_DESIGN.md §1.7).
    op.create_index(
        "ix_departments_hospital_active",
        "departments",
        ["hospital_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Case-insensitive prefix search on name. Without `varchar_pattern_ops`,
    # `lower(name) LIKE 'card%'` cannot use this index.
    op.create_index(
        "ix_departments_name_lower",
        "departments",
        ["hospital_id", sa.text("lower(name) varchar_pattern_ops")],
    )


def downgrade() -> None:
    """Rollback — drop the departments table and everything attached to it."""
    op.drop_index("ix_departments_name_lower", table_name="departments")
    op.drop_index("ix_departments_hospital_active", table_name="departments")
    # Bare suffix here too — the same naming convention expands it on the way out.
    op.drop_constraint("code_format", "departments", type_="check")
    op.drop_index("uq_departments_hospital_name_lower", table_name="departments")
    op.drop_constraint("uq_departments_hospital_code", "departments", type_="unique")
    op.drop_table("departments")
