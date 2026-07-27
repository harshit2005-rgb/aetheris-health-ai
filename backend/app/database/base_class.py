"""SQLAlchemy declarative base.

This module owns exactly one thing: the :class:`Base` class that every ORM
model inherits from, together with the project-wide constraint naming
convention applied to its metadata.

Column mixins (audit timestamps, soft delete, tenancy, UUID primary key) live
in :mod:`app.models.base` — they are model concerns, not database-infrastructure
concerns.

Usage::

    from app.database.base_class import Base

    class Hospital(Base):
        __tablename__ = "hospitals"
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase

from app.core.constants import DATABASE_MODEL_NAMING_CONVENTION


class Base(DeclarativeBase):
    """Abstract base class for all SQLAlchemy models.

    Uses the project's naming convention for constraints and indexes so that
    Alembic autogenerate produces stable, predictable constraint names.
    """


# Apply the naming convention to the base metadata
Base.metadata.naming_convention = DATABASE_MODEL_NAMING_CONVENTION
