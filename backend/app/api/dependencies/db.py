"""Database session dependency.

Provides the request-scoped :class:`AsyncSession` that every repository and
service is constructed with.

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

# NOTE: ``Request`` and ``AsyncSession`` must be imported at runtime, not under
# TYPE_CHECKING. FastAPI resolves dependency signatures against the module's
# real globals, so a TYPE_CHECKING-only import raises NameError when the route
# that depends on this function is registered.
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


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
