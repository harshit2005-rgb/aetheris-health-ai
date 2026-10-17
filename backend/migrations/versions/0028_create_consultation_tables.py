"""create consultation tables

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-16 23:00:00.000000

Creates the Consultation (EMR) module's tables
(``docs/modules/16-consultation.md`` §8): ``consultations`` and
``consultation_addenda``.

Where this departs from ``docs/05-DATABASE_DESIGN.md`` §2.13–2.14, and why:

1. **``diagnoses`` (plural), a list of ``{code, description}``.** A visit
   usually has more than one.
2. **An explicit ``status`` (draft / finalized).** ``finalized_at`` alone would
   make "is it locked?" a null check scattered through the code.
3. **Vitals provenance** (``vitals_recorded_at`` / ``vitals_recorded_by``): a
   nurse often records them before the doctor writes the note.
4. **``follow_up_date``** — what "review in five days" means on the calendar.
5. **``hospital_id`` on addenda** (CLAUDE.md rules 4 and 5).
6. **No ``ai_summary*`` columns yet**; Module 13 adds them when it is built.

One consultation per appointment, through a unique index on
``(hospital_id, appointment_id)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUS_VALUES = ("draft", "finalized")


def _uuid_pk() -> sa.Column[object]:
    """Return the standard UUID primary key column."""
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _fk(
    name: str, target: str, *, nullable: bool = False, ondelete: str = "RESTRICT"
) -> sa.Column[object]:
    """Return a UUID foreign key column."""
    return sa.Column(
        name,
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
    )


def _audit_columns() -> list[sa.Column[object]]:
    """Return the audit and soft-delete columns every business table carries."""
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
        _fk("created_by", "users.id", nullable=True, ondelete="SET NULL"),
        _fk("updated_by", "users.id", nullable=True, ondelete="SET NULL"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        _fk("deleted_by", "users.id", nullable=True, ondelete="SET NULL"),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM(*_STATUS_VALUES, name="consultation_status").create(bind, checkfirst=True)
    status = postgresql.ENUM(name="consultation_status", create_type=False)

    # ── consultations ────────────────────────────────────────────────────────
    op.create_table(
        "consultations",
        _uuid_pk(),
        _fk("hospital_id", "hospitals.id"),
        _fk("appointment_id", "appointments.id"),
        _fk("patient_id", "patients.id"),
        _fk("doctor_id", "doctors.id"),
        sa.Column("status", status, nullable=False, server_default="draft"),
        sa.Column("chief_complaint", sa.Text(), nullable=True),
        sa.Column("history", sa.Text(), nullable=True),
        sa.Column("examination", sa.Text(), nullable=True),
        # Array of {code, description}.
        sa.Column(
            "diagnoses",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("plan", sa.Text(), nullable=True),
        sa.Column("follow_up_date", sa.Date(), nullable=True),
        sa.Column("vitals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("vitals_recorded_at", sa.DateTime(timezone=True), nullable=True),
        _fk("vitals_recorded_by", "users.id", nullable=True, ondelete="SET NULL"),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        _fk("finalized_by", "users.id", nullable=True, ondelete="SET NULL"),
        *_audit_columns(),
        sa.CheckConstraint(
            "(status = 'finalized') = (finalized_at IS NOT NULL)",
            name="ck_consultations_finalized_has_time",
        ),
        comment="One clinical note per appointment (docs/modules/16-consultation.md).",
    )
    op.create_index(
        "uq_consultations_hospital_appointment",
        "consultations",
        ["hospital_id", "appointment_id"],
        unique=True,
    )
    op.create_index(
        "ix_consultations_hospital_patient",
        "consultations",
        ["hospital_id", "patient_id", "created_at"],
    )
    op.create_index(
        "ix_consultations_hospital_doctor",
        "consultations",
        ["hospital_id", "doctor_id", "created_at"],
    )

    # ── consultation_addenda ─────────────────────────────────────────────────
    op.create_table(
        "consultation_addenda",
        _uuid_pk(),
        _fk("hospital_id", "hospitals.id"),
        _fk("consultation_id", "consultations.id", ondelete="CASCADE"),
        sa.Column("text", sa.Text(), nullable=False),
        _fk("added_by", "users.id"),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        *_audit_columns(),
        comment="Additions to a finalized consultation; the note itself is never edited.",
    )
    op.create_index(
        "ix_consultation_addenda_consultation",
        "consultation_addenda",
        ["hospital_id", "consultation_id", "added_at"],
    )


def downgrade() -> None:
    """Rollback — drop the consultation tables and their enum type."""
    op.drop_table("consultation_addenda")
    op.drop_table("consultations")
    postgresql.ENUM(name="consultation_status").drop(op.get_bind(), checkfirst=True)
