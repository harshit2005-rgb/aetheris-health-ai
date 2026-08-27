"""create appointment tables

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-31 14:00:00.000000

Creates the appointment schema (``docs/05-DATABASE_DESIGN.md`` §2.11–2.12,
``docs/modules/05-appointment-management.md`` §8):

- ``appointment_status`` / ``appointment_type`` enum types
- ``appointments`` — the schedule the clinic runs on
- ``appointment_status_history`` — immutable record of every transition

Three points worth stating up front.

**``btree_gist`` is required.** The no-overlap exclusion constraint compares
``doctor_id`` for equality inside a GiST index, and GiST has no native equality
operator for UUID without this extension. A role running this migration needs
``CREATE EXTENSION`` privileges; on a locked-down production database that may
have to be granted, or the extension installed out of band, before deploy.

**Double-booking is prevented by the database, not the service.** Module spec
§14 has two receptionists booking the same slot simultaneously: application
checks cannot close that race, because both transactions read before either
writes. The EXCLUDE constraint makes one of them fail at COMMIT, which is what
AC-2 asks for.

**``changed_by`` is nullable, unlike §2.12.** That column is ``NOT NULL`` in the
database design, but the no-show sweeper (§5.7) is a background job with no
acting user, and FR-7 requires it to write history rows like any other
transition. NULL means "system", matching how the audit mixins already document
``created_by`` ("NULL for system rows"). The alternative — inventing a synthetic
system user — would put a fake row in ``users`` that permission checks and user
lists would then have to special-case.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Statuses that free the slot back up. An appointment in one of these no
#: longer occupies its time, so the exclusion constraint must ignore it —
#: otherwise a cancelled 09:00 booking would block rebooking 09:00.
_SLOT_FREEING_STATUSES = ("cancelled", "no_show")


def upgrade() -> None:
    # ── Extension ──────────────────────────────────────────────────────────────
    # Needed for `doctor_id WITH =` inside the GiST exclusion index below.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # ── Enums ──────────────────────────────────────────────────────────────────
    # Created explicitly rather than inline so they drop cleanly on downgrade
    # and a re-run after a partial failure is not blocked.
    appointment_status = postgresql.ENUM(
        "booked",
        "checked_in",
        "in_progress",
        "completed",
        "cancelled",
        "no_show",
        name="appointment_status",
        create_type=False,
    )
    appointment_status.create(op.get_bind(), checkfirst=True)

    appointment_type = postgresql.ENUM(
        "new",
        "follow_up",
        "walk_in",
        "emergency",
        name="appointment_type",
        create_type=False,
    )
    appointment_type.create(op.get_bind(), checkfirst=True)

    # ── appointments ───────────────────────────────────────────────────────────
    op.create_table(
        "appointments",
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
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "doctor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("doctors.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", appointment_status, nullable=False),
        sa.Column("type", appointment_type, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("cancelled_reason", sa.Text, nullable=True),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # Business rule 8: a client retry must not double-book. Scoped per
        # hospital so two tenants cannot collide on the same generated key.
        sa.Column("idempotency_key", sa.String(200), nullable=True),
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

    op.create_check_constraint(
        "time_order", "appointments", sa.text("scheduled_end > scheduled_start")
    )

    # Idempotency (business rule 8). A partial unique index rather than a
    # constraint, so the many rows with no key do not collide with each other.
    op.create_index(
        "uq_appointments_hospital_idempotency_key",
        "appointments",
        ["hospital_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    # ── No double-booking, enforced by Postgres (module spec §8, AC-2) ─────────
    statuses = ", ".join(f"'{status}'" for status in _SLOT_FREEING_STATUSES)
    op.execute(
        f"""
        ALTER TABLE appointments
        ADD CONSTRAINT no_overlap_per_doctor
        EXCLUDE USING gist (
            doctor_id WITH =,
            tstzrange(scheduled_start, scheduled_end, '[)') WITH &&
        ) WHERE (deleted_at IS NULL AND status NOT IN ({statuses}))
        """
    )

    # ── Read paths (module spec §8) ────────────────────────────────────────────
    op.create_index(
        "ix_appointments_hospital_scheduled_start",
        "appointments",
        ["hospital_id", "scheduled_start"],
    )
    op.create_index(
        "ix_appointments_doctor_scheduled_start",
        "appointments",
        ["doctor_id", "scheduled_start"],
    )
    op.create_index(
        "ix_appointments_patient_scheduled_start",
        "appointments",
        ["patient_id", sa.text("scheduled_start DESC")],
    )
    op.create_index("ix_appointments_status", "appointments", ["hospital_id", "status"])

    # ── appointment_status_history ─────────────────────────────────────────────
    # Immutable (§2.12): no updated_at, no soft delete. Rows are only ever
    # appended, so there is nothing to update or retract.
    op.create_table(
        "appointment_status_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "appointment_id",
            postgresql.UUID(as_uuid=True),
            # CASCADE: history has no meaning without its appointment, and
            # appointments are soft-deleted in practice so this rarely fires.
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "hospital_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # NULL on the first row: an appointment transitions *from* nothing when
        # it is booked.
        sa.Column("from_status", appointment_status, nullable=True),
        sa.Column("to_status", appointment_status, nullable=False),
        sa.Column(
            "changed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            # Nullable — see the module docstring. NULL means the system acted,
            # which is how the no-show sweeper records itself.
            nullable=True,
        ),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text, nullable=True),
    )

    op.create_index(
        "ix_appt_status_history_appointment",
        "appointment_status_history",
        ["appointment_id", "changed_at"],
    )


def downgrade() -> None:
    """Rollback — drop the appointment tables and their enum types.

    ``btree_gist`` is deliberately left installed: other modules may come to
    depend on it, and dropping a shared extension on the way out of one
    migration is more likely to break something than to tidy anything up.
    """
    op.drop_index("ix_appt_status_history_appointment", table_name="appointment_status_history")
    op.drop_table("appointment_status_history")

    op.drop_index("ix_appointments_status", table_name="appointments")
    op.drop_index("ix_appointments_patient_scheduled_start", table_name="appointments")
    op.drop_index("ix_appointments_doctor_scheduled_start", table_name="appointments")
    op.drop_index("ix_appointments_hospital_scheduled_start", table_name="appointments")
    op.execute("ALTER TABLE appointments DROP CONSTRAINT IF EXISTS no_overlap_per_doctor")
    op.drop_index("uq_appointments_hospital_idempotency_key", table_name="appointments")
    op.drop_table("appointments")

    op.execute("DROP TYPE IF EXISTS appointment_type")
    op.execute("DROP TYPE IF EXISTS appointment_status")
