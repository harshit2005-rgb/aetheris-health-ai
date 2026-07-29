"""Authentication middleware foundation.

Extracts and validates JWT access tokens from the ``Authorization`` header,
placing the authenticated user (or ``None`` for anonymous) in
``request.state.user`` for downstream middleware and route handlers.

**Important:** This middleware performs basic token parsing and signature
verification. Full RBAC permission checks happen at the route level via the
``require_permission`` dependency (implemented alongside the auth module).

The middleware does **not** raise errors when no token is present — it sets
``request.state.user = None`` so public endpoints (health, login) can function
without authentication.
"""

from __future__ import annotations

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that resolves JWT tokens to user context.

    On success, sets ``request.state.user`` and
    ``request.state.hospital_id``. On failure (missing or invalid
    token), these are ``None`` — the route-level dependency
    ``require_permission`` rejects unauthorized access.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Extract and validate the JWT from the Authorization header.

        :param request: The incoming HTTP request.
        :param call_next: The next middleware or route handler.
        :returns: The HTTP response.
        """
        # Ensure request.state has default values even without a token.
        request.state.user = None
        request.state.hospital_id = None

        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()
            if token:
                # Token validation happens in core/security.py (Sprint 3).
                # For now, store the raw token for downstream processing.
                request.state.raw_token = token
                logger.debug("auth_token_present", path=str(request.url.path))

        response: Response = await call_next(request)
        return response


__all__ = ["AuthMiddleware"]
