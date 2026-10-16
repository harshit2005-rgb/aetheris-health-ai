"""A hospital's opening hours (``docs/modules/14-hospital-settings.md`` §8).

One row per day the hospital has an entry for: open between two wall-clock
times, open all day, or closed. Monday is 0, as for doctor availability and
:meth:`datetime.date.weekday`. The hours are informational for staff and
scheduling (§4 rule 9); enforcement lives with appointments.

Configuration, not a business record: the week is replaced as a whole, with
hard deletes, exactly as a doctor's availability is.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Mapped[uuid.UUID] resolution
from datetime import time  # noqa: TC003 — needed at runtime for Mapped[...] resolution

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, SmallInteger, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

__all__ = ["HospitalWorkingHours"]


class HospitalWorkingHours(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One day of a hospital's week: its opening and closing time, all day, or closed."""

    __tablename__ = "hospital_working_hours"

    __table_args__ = (
        UniqueConstraint("hospital_id", "day_of_week", name="uq_hospital_working_hours_day"),
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="day_of_week_range"),
        # All day: no times. Closed: no times. Open: both times, in order.
        CheckConstraint(
            "(is_24h AND open_time IS NULL AND close_time IS NULL)"
            " OR (NOT is_24h AND open_time IS NULL AND close_time IS NULL)"
            " OR (NOT is_24h AND open_time IS NOT NULL AND close_time IS NOT NULL"
            " AND close_time > open_time)",
            name="hours_shape",
        ),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=False,
        comment="Owning tenant.",
    )
    day_of_week: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="0=Monday .. 6=Sunday, matching date.weekday()."
    )
    open_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
        comment="Opening time, hospital wall-clock. NULL when closed or all day.",
    )
    close_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
        comment="Closing time, hospital wall-clock. NULL when closed or all day.",
    )
    is_24h: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", comment="Open all day."
    )

    def __repr__(self) -> str:
        return (
            f"<HospitalWorkingHours day={self.day_of_week} "
            f"{'24h' if self.is_24h else f'{self.open_time}-{self.close_time}'}>"
        )
