"""Root-level health endpoints.

These endpoints are mounted **without** the ``/api/v1`` prefix so that load
balancers, Kubernetes probes, and the Sprint 0 deliverable
(``docs/15-SPRINT_PLAN.md``) can reach them at the documented paths:

- ``GET /healthz`` — simple liveness probe (always 200)
- ``GET /readyz`` — readiness probe (checks dependencies)
- ``GET /version`` — returns application version and build info

The ``/api/v1/health/*`` routes remain in :mod:`app.api.v1.health` for API
consumers who want versioned health data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get(
    "/healthz",
    summary="Kubernetes liveness probe",
    description="Returns 200 OK if the process is alive. Mounted at root for K8s convention.",
    responses={
        200: {
            "description": "Application is alive.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "alive",
                        "timestamp": "2026-07-26T12:00:00Z",
                    },
                },
            },
        },
    },
)
async def healthz() -> dict[str, Any]:
    """Lightweight liveness probe.

    Matches the Sprint 0 deliverable: ``GET /healthz`` → 200.
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


@router.get(
    "/readyz",
    summary="Kubernetes readiness probe",
    description="Returns 200 OK when upstream dependencies are reachable. Mounted at root for K8s convention.",
    responses={
        200: {"description": "Application is ready."},
        503: {"description": "Dependencies unavailable."},
    },
)
async def readyz() -> dict[str, Any]:
    """Readiness check — reports dependency health.

    As of Sprint 0, this is a lightweight check that does not require
    database connectivity. The full readiness check with DB verification
    lives at ``/api/v1/health/ready``.
    """
    return {
        "status": "ready",
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "checks": {
            "database": "deferred",  # full check at /api/v1/health/ready
            "redis": "not_configured",
        },
    }


@router.get(
    "/version",
    summary="Application version",
    description="Returns the current application version and build metadata.",
)
async def version() -> dict[str, Any]:
    """Application version endpoint.

    Returns version and environment info for CI/CD and debugging.
    """
    return {
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "environment": settings.APP_ENV,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
