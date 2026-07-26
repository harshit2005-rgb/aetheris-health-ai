"""API v1 — All version 1 endpoints.

Versioned via URL prefix ``/api/v1``.
See :mod:`app.main` for router registration.
"""

from app.api.v1.health import router as health_router

__all__ = [
    "health_router",
]
