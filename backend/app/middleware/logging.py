"""Structured request logging middleware.

Logs every HTTP request with duration, status code, method, path, and request ID.
Installed as ASGI middleware on the FastAPI app in :func:`app.main._register_middleware`.

Middleware order: this must run **after** :class:`RequestIDMiddleware` so that
``request.state.request_id`` is already populated.
"""

from __future__ import annotations

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs structured information for every HTTP request."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Log request metadata before and after the handler executes.

        :param request: The incoming HTTP request.
        :param call_next: The next middleware or route handler.
        :returns: The HTTP response.
        """
        start_ns = time.perf_counter_ns()
        request_id = getattr(request.state, "request_id", None)

        response: Response = await call_next(request)

        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000

        logger.info(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query_string=str(request.url.query),
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            content_length=response.headers.get("content-length"),
            user_agent=request.headers.get("user-agent"),
            ip=request.client.host if request.client else None,
        )

        return response


__all__ = ["RequestLoggingMiddleware"]
