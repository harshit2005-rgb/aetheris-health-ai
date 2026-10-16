"""add departments.head_doctor_id

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-31 09:05:00.000000

Adds the column ``0005`` deliberately left out.

``departments`` and ``doctors`` reference each other: a doctor belongs to a
department, and a department has a head doctor. Neither table could carry its
foreign key at creation time, so ``0005`` created ``departments`` without
``head_doctor_id``, ``0006`` created ``doctors`` with ``department_id``, and
this migration closes the loop now that both tables exist.

Kept separate from ``0006`` because that migration creates tables and this one
alters an existing table — one atomic change each (``backend/CLAUDE.md``,
"Migrations").

Nullable, and ``ON DELETE SET NULL``: most departments have no designated head,
and a department must survive its head doctor being deactivated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "departments",
        sa.Column(
            "head_doctor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("doctors.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_departments_head_doctor", "departments", ["head_doctor_id"])


def downgrade() -> None:
    """Rollback — drop the head doctor reference."""
    op.drop_index("ix_departments_head_doctor", table_name="departments")
    op.drop_column("departments", "head_doctor_id")
