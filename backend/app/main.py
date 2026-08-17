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
from fastapi.responses import JSONResponse

from app.api.v1 import (
    appointment_router,
    auth_router,
    department_router,
    doctor_router,
    health_router,
    patient_router,
    permission_router,
    role_router,
    user_router,
)
from app.core.config import settings
from app.core.constants import API_DOCS_URL, API_OPENAPI_URL, API_REDOC_URL, API_V1_PREFIX
from app.core.error_codes import ErrorCode
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

    Order matters: middleware is applied in reverse order of registration.
    The **last** registered middleware wraps everything and runs **first**
    on each request (outermost layer).

    Execution order (outermost → innermost):
    1. ExceptionHandler (catches errors from all inner layers)
    2. Auth (extracts user context from JWT)
    3. RequestLogging
    4. RequestID
    5. RateLimit
    6. CORS
    """
    from app.middleware.auth import AuthMiddleware
    from app.middleware.cors import add_cors_middleware
    from app.middleware.exception_handler import ExceptionHandlerMiddleware
    from app.middleware.logging import RequestLoggingMiddleware
    from app.middleware.rate_limit import RateLimitMiddleware
    from app.middleware.request_id import RequestIDMiddleware
    from app.middleware.timing import TimingMiddleware

    # 7. Exception handler — outermost, wraps everything
    app.add_middleware(ExceptionHandlerMiddleware)

    # 6. Timing (measures total request time including all inner layers)
    app.add_middleware(TimingMiddleware)

    # 5. Auth
    app.add_middleware(AuthMiddleware)

    # 4. Request logging (captures request_id from state)
    app.add_middleware(RequestLoggingMiddleware)

    # 3. Request ID (sets request.state.request_id for inner layers)
    app.add_middleware(RequestIDMiddleware)

    # 2. Rate limiting
    app.add_middleware(RateLimitMiddleware)

    # 1. CORS — innermost, closest to route handler
    add_cors_middleware(app)

    logger.debug("middleware_registered")


def _register_routers(app: FastAPI) -> None:
    """Register all API routers on the application.

    Routers mounted **without** a prefix (root-level routes):
    - :mod:`app.api.root_health` — K8s health probes (``/healthz``, ``/readyz``, ``/version``)

    Routers mounted at ``API_V1_PREFIX``:
    - :mod:`app.api.v1.health` — versioned health endpoint suite
    - Future modules (auth, patients, etc.)
    """
    from app.api.root_health import router as root_health_router

    # Root-level routes for K8s probes and Sprint 0 compliance.
    app.include_router(root_health_router)

    # Versioned API routes under /api/v1/
    app.include_router(
        health_router,
        prefix=API_V1_PREFIX,
    )

    # Auth routes — public endpoints + authenticated endpoints
    app.include_router(
        auth_router,
        prefix=API_V1_PREFIX,
    )

    # User management routes
    app.include_router(
        user_router,
        prefix=API_V1_PREFIX,
    )

    # Patient management routes
    app.include_router(
        patient_router,
        prefix=API_V1_PREFIX,
    )

    # Department routes (Hospital Settings module, feature 17.2)
    app.include_router(
        department_router,
        prefix=API_V1_PREFIX,
    )

    # Doctor management routes
    app.include_router(
        doctor_router,
        prefix=API_V1_PREFIX,
    )

    # Appointment management routes
    app.include_router(
        appointment_router,
        prefix=API_V1_PREFIX,
    )

    # Roles & Permissions routes (read-only catalog in MVP)
    app.include_router(
        role_router,
        prefix=API_V1_PREFIX,
    )

    # Permissions catalog routes (read-only)
    app.include_router(
        permission_router,
        prefix=API_V1_PREFIX,
    )

    logger.debug("routers_registered")


#: HTTP status → error code, for HTTPExceptions raised with a plain string
#: detail (FastAPI's own 404s and 405s).
_STATUS_TO_ERROR_CODE: dict[int, str] = {
    401: ErrorCode.AUTHENTICATION_REQUIRED,
    403: ErrorCode.PERMISSION_DENIED,
    404: ErrorCode.RESOURCE_NOT_FOUND,
    409: ErrorCode.RESOURCE_CONFLICT,
    422: ErrorCode.VALIDATION_ERROR,
    429: ErrorCode.RATE_LIMITED,
}


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers.

    Maps :class:`AetherisError` subclasses to structured JSON responses.
    """
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

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

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Map HTTPException to the standard failure envelope.

        The auth dependencies raise ``HTTPException`` with a ``{"message",
        "error_code"}`` detail. Without this handler FastAPI serialises that as
        ``{"detail": ...}``, so a 401 or 403 does not match the envelope in
        ``docs/06-API_STANDARDS.md`` §5.3 and clients need a second error shape.
        """
        detail = exc.detail
        if isinstance(detail, dict):
            message = str(detail.get("message", "Request failed."))
            error_code = str(detail.get("error_code", ErrorCode.INTERNAL_ERROR))
        else:
            message = str(detail)
            error_code = str(_STATUS_TO_ERROR_CODE.get(exc.status_code, ErrorCode.INTERNAL_ERROR))

        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(
                message,
                error_code=error_code,
                request_id=getattr(request.state, "request_id", None),
            ),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Map Pydantic request-validation errors to the standard envelope.

        ``docs/06-API_STANDARDS.md`` §5.3 specifies ``errors`` as a list of
        ``{field, message}`` objects; FastAPI's default is a raw ``detail``
        array whose ``loc`` tuples leak internal request structure.
        """
        errors = [
            {
                "field": ".".join(str(part) for part in error.get("loc", ()) if part != "body"),
                "message": str(error.get("msg", "Invalid value.")),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_envelope(
                "Validation failed.",
                error_code=ErrorCode.VALIDATION_ERROR,
                errors=errors,
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
