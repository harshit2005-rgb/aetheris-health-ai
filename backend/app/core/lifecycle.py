"""Application lifecycle management.

Handles startup (create engine, configure logging, warm caches)
and shutdown (close connections, flush logs) events.

Used by :mod:`app.main` via FastAPI's ``lifespan`` parameter.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog

from app.core.config import settings
from app.database import create_session_factory, dispose_engine, initialize_database

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:  # noqa: ARG001
    """Application lifespan context manager.

    Called by FastAPI on startup and shutdown.

    **Startup sequence:**
    1. Initialize the async database engine and session factory.
    2. Verify database connectivity (warm the pool).
    3. Log startup confirmation.

    **Notes:**
    - Structured logging is configured in :func:`app.main.create_app` before the lifespan runs.

    **Shutdown sequence:**
    1. Dispose the database engine (close all connections).
    2. Log shutdown confirmation.
    """
    # ── Startup ──────────────────────────────────────────────────────────
    # Logging was already configured by create_app() in main.py.

    logger.info(
        "application_startup",
        environment=settings.APP_ENV,
        debug=settings.APP_DEBUG,
        database_pool_size=settings.DATABASE_POOL_SIZE,
    )

    initialize_database(database_url=settings.DATABASE_URL)
    _session_factory = create_session_factory(
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        echo=settings.DATABASE_ECHO,
    )

    # Store the session factory on the app state for dependency injection.
    app.state.db_session_factory = _session_factory

    try:
        # Warm the connection pool by making a single connectivity check.
        from sqlalchemy import text

        async with _session_factory() as session:
            await session.execute(text("SELECT 1"))
            logger.info("database_connection_verified")
    except Exception as exc:
        logger.error("database_connection_failed", error=str(exc))
        raise

    logger.info(
        "application_started",
        app_name=settings.APP_NAME,
        base_url=settings.APP_BASE_URL,
    )

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("application_shutdown_started")

    await dispose_engine()

    logger.info("application_shutdown_complete")
