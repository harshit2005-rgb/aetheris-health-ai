"""FastAPI dependency injection wiring.

Provides shared dependencies that route handlers and sub-dependencies
use to access database sessions, services, and repositories.

Usage::

    from fastapi import APIRouter, Depends
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.api.dependencies import get_db_session

    router = APIRouter()

    @router.get("/example")
    async def example_endpoint(
        session: AsyncSession = Depends(get_db_session),
    ):
        ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import Request
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession]:
    """Dependency that yields an async database session.

    The session is obtained from the session factory stored on the app state
    during startup. It is automatically closed when the request completes.

    Usage::

        async def my_endpoint(session: AsyncSession = Depends(get_db_session)):
            result = await session.execute(...)

    :param request: The incoming FastAPI request (injected automatically).
    :yields: An :class:`AsyncSession` bound to the global engine.
    :raises RuntimeError: If the session factory was not initialized during startup.
    """
    factory = getattr(request.app.state, "db_session_factory", None)
    if factory is None:
        msg = (
            "Database session factory not initialized. "
            "Ensure the application lifecycle ran startup correctly."
        )
        raise RuntimeError(msg)

    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()
