"""Database infrastructure — declarative base, async engine, session factory.

This package holds database *plumbing* only. ORM models live in
:mod:`app.models`; data access lives in :mod:`app.repositories`.

Usage::

    from app.database import Base, create_session_factory

    # During startup:
    from app.database import initialize_database
    initialize_database(database_url="postgresql+asyncpg://...")

    # Create a session:
    factory = create_session_factory()
    async with factory() as session:
        result = await session.execute(...)
"""

from app.database.base_class import Base
from app.database.session import (
    create_session_factory,
    dispose_engine,
    get_async_engine,
    initialize_database,
)

__all__ = [
    "Base",
    "create_session_factory",
    "dispose_engine",
    "get_async_engine",
    "initialize_database",
]
