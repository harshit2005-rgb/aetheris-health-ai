"""create doctor tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-31 09:00:00.000000

Creates the doctor schema (``docs/05-DATABASE_DESIGN.md`` §2.8–2.10,
``docs/modules/04-doctor-management.md`` §8):

- ``doctors`` — clinical profile attached to exactly one user
- ``doctor_availability`` — weekly recurring bookable windows
- ``doctor_leaves`` — time-off intervals that subtract from availability

Grouped into one migration because they are a single aggregate that ships
together, the same way ``0001`` created the identity tables as a set. A doctor
row without its availability and leave tables is not a usable state.

Two deliberate departures from ``docs/05-DATABASE_DESIGN.md``:

**``hospital_id`` on the child tables.** §2.9 and §2.10 scope availability and
leaves through ``doctor_id`` alone. CLAUDE.md rules 4 and 5 require a
``hospital_id`` on every tenant table and a filter on it at the repository
layer, and those rules are non-negotiable. Carrying the column means a child
row can be tenant-filtered directly instead of relying on every call site to
resolve the parent doctor first.

**``department_id`` on ``doctors``.** Feature 5.2 assigns doctors to a
department and spec §9 filters the doctor list by one, so the foreign key
belongs here. It is nullable: a doctor can be onboarded before their
department is decided.

``departments.head_doctor_id`` is the mirror of this reference and lands in
``0007`` — it alters an existing table, which is a separate atomic change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Slot durations the scheduler supports (module spec §11). Enforced in the
#: database as well as the schema because the service is reachable from seed
#: scripts and background jobs that never cross the API boundary.
_SLOT_DURATIONS = (10, 15, 20, 30, 45, 60)


def _audit_columns() -> list[sa.Column]:
    """Return the standard audit column set (``docs/05-DATABASE_DESIGN.md`` §1.3)."""
    return [
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
    ]


def upgrade() -> None:
    # ── doctors ────────────────────────────────────────────────────────────────
    op.create_table(
        "doctors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            # RESTRICT: a user row backs the doctor's identity and login.
            # Removing it would leave appointments pointing at a nameless doctor.
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "hospital_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("specialization", sa.String(100), nullable=False),
        sa.Column("qualifications", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("license_number", sa.String(50), nullable=False),
        sa.Column(
            "consultation_fee", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("languages", postgresql.JSONB, nullable=False, server_default="[]"),
        *_audit_columns(),
    )

    # One doctor row per user (module spec §4, rule 1 and FR-1). Global rather
    # than per-hospital because a user already belongs to exactly one hospital.
    op.create_unique_constraint("uq_doctors_user_id", "doctors", ["user_id"])

    op.create_index(
        "ix_doctors_hospital_specialization", "doctors", ["hospital_id", "specialization"]
    )
    op.create_index("ix_doctors_department", "doctors", ["department_id"])
    op.create_index(
        "ix_doctors_hospital_active",
        "doctors",
        ["hospital_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ── doctor_availability ────────────────────────────────────────────────────
    op.create_table(
        "doctor_availability",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "doctor_id",
            postgresql.UUID(as_uuid=True),
            # CASCADE: availability has no meaning without its doctor, and rows
            # are replaced wholesale on every PUT (module spec §5.2).
            sa.ForeignKey("doctors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "hospital_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("day_of_week", sa.SmallInteger, nullable=False),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column(
            "slot_duration_minutes", sa.Integer, nullable=False, server_default=sa.text("15")
        ),
        *_audit_columns(),
    )

    # Bare constraint names throughout: the metadata naming convention is
    # ``ck_%(table_name)s_%(constraint_name)s`` and Alembic applies it to
    # whatever is passed, so a fully-spelled name would be doubled up.
    op.create_check_constraint(
        "time_order", "doctor_availability", sa.text("end_time > start_time")
    )
    op.create_check_constraint(
        "day_of_week_range", "doctor_availability", sa.text("day_of_week BETWEEN 0 AND 6")
    )
    op.create_check_constraint(
        "slot_duration",
        "doctor_availability",
        sa.text(f"slot_duration_minutes IN ({', '.join(str(d) for d in _SLOT_DURATIONS)})"),
    )

    op.create_index(
        "ix_doctor_avail_doctor_day", "doctor_availability", ["doctor_id", "day_of_week"]
    )

    # ── doctor_leaves ──────────────────────────────────────────────────────────
    op.create_table(
        "doctor_leaves",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "doctor_id",
            postgresql.UUID(as_uuid=True),
            # RESTRICT rather than CASCADE: a leave is a soft-deleted business
            # record with its own audit trail, unlike availability.
            sa.ForeignKey("doctors.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "hospital_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(200), nullable=True),
        *_audit_columns(),
    )

    op.create_check_constraint("range_order", "doctor_leaves", sa.text("ends_at > starts_at"))

    op.create_index(
        "ix_doctor_leaves_doctor_range", "doctor_leaves", ["doctor_id", "starts_at", "ends_at"]
    )
    op.create_index(
        "ix_doctor_leaves_hospital_active",
        "doctor_leaves",
        ["hospital_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Rollback — drop the three doctor tables, children first."""
    op.drop_index("ix_doctor_leaves_hospital_active", table_name="doctor_leaves")
    op.drop_index("ix_doctor_leaves_doctor_range", table_name="doctor_leaves")
    op.drop_table("doctor_leaves")

    op.drop_index("ix_doctor_avail_doctor_day", table_name="doctor_availability")
    op.drop_table("doctor_availability")

    op.drop_index("ix_doctors_hospital_active", table_name="doctors")
    op.drop_index("ix_doctors_department", table_name="doctors")
    op.drop_index("ix_doctors_hospital_specialization", table_name="doctors")
    op.drop_table("doctors")
