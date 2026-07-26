"""Database infrastructure — async engine, session factory, declarative base.

Usage::

    from app.shared.database import Base, create_session_factory

    # During startup:
    from app.shared.database import initialize_database
    initialize_database(database_url="postgresql+asyncpg://...")

    # Create a session:
    factory = create_session_factory()
    async with factory() as session:
        result = await session.execute(...)
"""

from app.shared.database.base import (
    Base,
    CommonColumnsMixin,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
)
from app.shared.database.session import (
    create_session_factory,
    dispose_engine,
    get_async_engine,
    initialize_database,
)

__all__ = [
    "Base",
    "CommonColumnsMixin",
    "SoftDeleteMixin",
    "TenantMixin",
    "TimestampMixin",
    "create_session_factory",
    "dispose_engine",
    "get_async_engine",
    "initialize_database",
]
