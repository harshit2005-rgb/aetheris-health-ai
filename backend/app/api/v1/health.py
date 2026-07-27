"""Health check endpoints.

Provides three liveness and readiness probes for Kubernetes, Docker Compose,
and load balancer health monitoring:

- ``GET /api/v1/health/live`` — Is the process alive? Always returns 200.
- ``GET /api/v1/health/ready`` — Are upstream dependencies (DB, Redis) reachable?
- ``GET /api/v1/health`` — Comprehensive health status with component detail.

These endpoints are **public** (no authentication required).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text

# NOTE: ``AsyncSession`` must be imported at runtime, not under TYPE_CHECKING.
# FastAPI resolves endpoint signatures against the module's real globals, so a
# TYPE_CHECKING-only import raises NameError at route registration.
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get(
    "/health/live",
    summary="Liveness probe",
    description="Returns 200 OK if the application process is running.",
    responses={
        200: {
            "description": "Application is alive.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "alive",
                        "timestamp": "2026-07-26T12:00:00Z",
                        "app": "Aetheris Health AI",
                        "version": "0.1.0",
                    },
                },
            },
        },
    },
)
async def liveness() -> dict[str, Any]:
    """Lightweight liveness check.

    Returns immediately without checking dependencies.
    Failures here indicate the process is unable to respond to HTTP requests.
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "app": settings.APP_NAME,
        "version": "0.1.0",
    }


@router.get(
    "/health/ready",
    summary="Readiness probe",
    description="Returns 200 OK when all upstream dependencies are reachable.",
    responses={
        200: {"description": "Application is ready to accept traffic."},
        503: {"description": "One or more dependencies are unavailable."},
    },
)
async def readiness(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Readiness check — verifies upstream dependencies.

    Currently checks:
    - Database connectivity (runs ``SELECT 1``).

    Future checks (Sprint 3+):
    - Redis connectivity.
    - Object storage connectivity.

    Returns 200 if all checks pass, 503 otherwise.
    """
    checks: dict[str, Any] = {}
    all_healthy = True

    # ── Database check ────────────────────────────────────────────────
    try:
        result = await session.execute(text("SELECT 1 AS ok"))
        row = result.one_or_none()
        db_healthy = row is not None and row._mapping.get("ok") == 1
        checks["database"] = "healthy" if db_healthy else "unhealthy"
        if not db_healthy:
            all_healthy = False
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"unhealthy: {exc!s}"
        all_healthy = False

    # ── Redis check (placeholder — will be implemented in Sprint 3) ───
    checks["redis"] = "not_configured"

    if not all_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "checks": checks,
            },
        )

    return {
        "status": "ready",
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "checks": checks,
    }


@router.get(
    "/health",
    summary="Comprehensive health check",
    description="Returns detailed health status of the application and all dependencies.",
    responses={
        200: {"description": "Application is healthy."},
        503: {"description": "One or more components are unhealthy."},
    },
)
async def health(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Comprehensive health check with component-level detail.

    Returns a summary of all dependency health statuses.
    """
    checks: dict[str, Any] = {}
    all_healthy = True

    # ── Database check ────────────────────────────────────────────────
    try:
        result = await session.execute(text("SELECT 1 AS ok"))
        row = result.one_or_none()
        db_healthy = row is not None and row._mapping.get("ok") == 1
        checks["database"] = "healthy" if db_healthy else "unhealthy"
        if not db_healthy:
            all_healthy = False
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"unhealthy: {exc!s}"
        all_healthy = False

    # ── Redis check (placeholder) ─────────────────────────────────────
    checks["redis"] = "not_configured"

    # ── Summary ───────────────────────────────────────────────────────
    response: dict[str, Any] = {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "environment": settings.APP_ENV,
        "checks": checks,
    }

    if not all_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response,
        )

    return response
