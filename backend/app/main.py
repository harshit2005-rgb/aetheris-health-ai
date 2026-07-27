"""FastAPI application entry point.

This module creates and configures the FastAPI application instance.
It is the single entry point for running the backend server.

Usage::

    # Development
    uv run uvicorn app.main:app --reload

    # Production
    uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import health_router
from app.core.config import settings
from app.core.constants import API_DOCS_URL, API_OPENAPI_URL, API_REDOC_URL, API_V1_PREFIX
from app.core.lifecycle import lifespan
from app.core.logging import configure_logging

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    :returns: A fully configured :class:`FastAPI` instance.
    """
    # Configure structured logging before any app-level logging occurs.
    configure_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="Enterprise Hospital Management Platform",
        lifespan=lifespan,
        docs_url=API_DOCS_URL if settings.is_development else None,
        redoc_url=API_REDOC_URL if settings.is_development else None,
        openapi_url=API_OPENAPI_URL if settings.is_development else None,
        # Disable default 422 handler — we use our own exception handling
        validation_error_details=settings.is_development,
        default_response_class=JSONResponse,
        terms_of_service="https://aetheris.health/terms",
        contact={
            "name": "Aetheris Health",
            "email": "dev@aetheris.health",
            "url": "https://aetheris.health",
        },
        license_info={
            "name": "Proprietary",
            "url": "https://aetheris.health/license",
        },
    )

    # ── Middleware ─────────────────────────────────────────────────────
    _register_middleware(app)

    # ── Routers ────────────────────────────────────────────────────────
    _register_routers(app)

    # ── Exception handlers ─────────────────────────────────────────────
    _register_exception_handlers(app)

    logger.info("application_created", docs_enabled=settings.is_development)
    return app


def _register_middleware(app: FastAPI) -> None:
    """Register ASGI middleware on the application.

    Order matters: middleware is applied in reverse order of registration
    (last registered = first executed).
    """
    # CORS — must be one of the outermost middleware layers
    if settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=[
                "X-Request-ID",
                "X-RateLimit-Limit",
                "X-RateLimit-Remaining",
                "X-RateLimit-Reset",
            ],
        )
        logger.debug("cors_middleware_configured", origins=settings.CORS_ORIGINS)

    # Additional middleware will be added in future sprints:
    # - Request ID middleware (Sprint 2)
    # - Structured logging middleware (Sprint 2)
    # - Rate limiting middleware (Sprint 3)
    # - Authentication middleware (Sprint 2 + 3)


def _register_routers(app: FastAPI) -> None:
    """Register all API routers on the application.

    Each router is mounted at ``API_V1_PREFIX + router_prefix``.
    """
    # Health endpoints — public, no auth required
    app.include_router(
        health_router,
        prefix=API_V1_PREFIX,
    )

    # Future modules will be added here:
    # app.include_router(auth_router, prefix=API_V1_PREFIX)

    logger.debug("routers_registered")


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers.

    Maps :class:`AetherisError` subclasses to structured JSON responses.
    """
    from app.core.envelope import error_envelope
    from app.core.error_codes import ErrorCode
    from app.core.exceptions import AetherisError
    from app.core.logging import get_logger

    handler_logger = get_logger("aetheris.exception_handler")

    @app.exception_handler(AetherisError)
    async def aetheris_exception_handler(request: Request, exc: AetherisError) -> JSONResponse:  # noqa: ARG001
        """Handle all application-level exceptions with a consistent envelope."""
        handler_logger.warning(
            "application_error",
            error_code=exc.error_code,
            status_code=exc.status_code,
            message=exc.message,
            detail=exc.detail,
            path=str(request.url.path),
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(
                exc.message,
                error_code=exc.error_code,
                errors=exc.detail,
                request_id=getattr(request.state, "request_id", None),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
        """Handle unexpected exceptions with a generic 500 response.

        Only logs the detailed error. Never returns stack traces in production.
        """
        handler_logger.exception(
            "unhandled_exception",
            path=str(request.url.path),
            exc_info=exc,
        )

        return JSONResponse(
            status_code=500,
            content=error_envelope(
                "An unexpected error occurred.",
                error_code=ErrorCode.INTERNAL_ERROR,
                request_id=getattr(request.state, "request_id", None),
            ),
        )

    logger.debug("exception_handlers_registered")


# ── Application instance ────────────────────────────────────────────────────
# This is what uvicorn loads: ``uv run uvicorn app.main:app``
app = create_app()
