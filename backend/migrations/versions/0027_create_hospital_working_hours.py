"""create hospital_working_hours

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-16 18:00:00.000000

A hospital's opening hours (``docs/modules/14-hospital-settings.md`` §8): one
row per day it has an entry for, open between two wall-clock times, open all
day, or closed. ``(hospital_id, day_of_week)`` is unique; Monday is 0.

``downgrade`` drops the table. Only configured opening hours are lost.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create ``hospital_working_hours``."""
    op.create_table(
        "hospital_working_hours",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("hospital_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("open_time", sa.Time(), nullable=True),
        sa.Column("close_time", sa.Time(), nullable=True),
        sa.Column("is_24h", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hospital_id", "day_of_week", name="uq_hospital_working_hours_day"),
        sa.CheckConstraint(
            "day_of_week BETWEEN 0 AND 6", name="ck_hospital_working_hours_day_of_week_range"
        ),
        sa.CheckConstraint(
            "(is_24h AND open_time IS NULL AND close_time IS NULL)"
            " OR (NOT is_24h AND open_time IS NULL AND close_time IS NULL)"
            " OR (NOT is_24h AND open_time IS NOT NULL AND close_time IS NOT NULL"
            " AND close_time > open_time)",
            name="ck_hospital_working_hours_hours_shape",
        ),
    )


def downgrade() -> None:
    """Drop ``hospital_working_hours``."""
    op.drop_table("hospital_working_hours")
