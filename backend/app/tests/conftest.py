"""Shared pytest fixtures for the backend test suite.

``asyncio_mode = "auto"`` is set in ``pyproject.toml``, so ``async def`` tests
need no decorator.

These fixtures provide the foundation for all test layers (unit, repository,
API, integration). They are deliberately minimal — populate as test modules
declare their needs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.database.unit_of_work import UnitOfWork


# ── Application ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def app() -> FastAPI:
    """Return the FastAPI application instance (session-scoped)."""
    from app.main import create_app

    return create_app()


# ── Settings ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def override_settings() -> Generator[None]:
    """Override settings for the duration of each test.

    By default, switches to test-friendly values. Individual tests can modify
    settings via ``settings.set(...)`` within their body.

    This fixture is ``autouse`` so every test gets a clean settings context.
    """
    from app.core.config import settings

    original_values: dict[str, Any] = {}

    # Store original values.
    for key in ("APP_ENV", "APP_DEBUG", "LOG_LEVEL"):
        original_values[key] = getattr(settings, key, None)

    try:
        # Apply test defaults.
        settings.APP_ENV = "development"  # type: ignore[assignment]
        settings.APP_DEBUG = True
        settings.LOG_LEVEL = "CRITICAL"
        yield
    finally:
        # Restore original values.
        for key, value in original_values.items():
            if value is not None:
                setattr(settings, key, value)


# ── Database ─────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create an ephemeral async session factory for testing.

    Uses the same database URL as the application. In CI, this connects to
    a test database managed by the CI workflow.

    .. caution::

        This fixture connects to a real PostgreSQL instance. For unit tests
        that do not need a database, mock the repository layer instead.
    """
    from app.core.config import settings
    from app.database import create_session_factory, initialize_database

    initialize_database(database_url=settings.DATABASE_URL)
    return create_session_factory(
        pool_size=5,
        max_overflow=0,
        echo=False,
    )


@pytest_asyncio.fixture
async def db_session(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    """Yield an async session with transactional rollback.

    Every test gets a fresh session. After the test completes, all changes
    are rolled back so tests never leak state.
    """
    async with db_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


@pytest_asyncio.fixture
async def uow(db_session: AsyncSession) -> UnitOfWork:
    """Yield a :class:`UnitOfWork` bound to the test-scoped session."""
    from app.database.unit_of_work import UnitOfWork

    return UnitOfWork(db_session)


# ── HTTP Client ──────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    """Yield an ``httpx.AsyncClient`` configured against the FastAPI app.

    Sends real HTTP requests through ASGI without starting a server.

    Usage::

        async def test_health(async_client: AsyncClient):
            response = await async_client.get("/api/v1/health/live")
            assert response.status_code == 200
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client


# ── Mock helpers ─────────────────────────────────────────────────────────────


@pytest.fixture
def mock_repository() -> AsyncMock:
    """Return a generic :class:`AsyncMock` for repository injection.

    Usage::

        def test_service(mock_repository):
            mock_repo = mock_repository
            mock_repo.get_by_id.return_value = FakeModel()
            service = MyService(mock_repo)
    """
    return AsyncMock()


__all__ = [
    "app",
    "async_client",
    "db_session",
    "db_session_factory",
    "mock_repository",
    "override_settings",
    "uow",
]
