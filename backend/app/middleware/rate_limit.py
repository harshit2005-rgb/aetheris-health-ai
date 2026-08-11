"""Rate limiting middleware.

Applies per-IP and per-user request rate limits. Uses an in-memory store by
default; Redis-backed implementation will be added in Sprint 3.

Currently a **foundation** — the middleware is registered but uses a simple
in-memory token bucket. The Redis-backed production implementation ships
alongside the Redis integration in Sprint 3.
"""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.envelope import error_envelope
from app.core.error_codes import ErrorCode


class _InMemoryRateLimiter:
    """Simple in-memory token-bucket rate limiter.

    Not suitable for multi-process deployments — use a Redis-backed
    implementation in production. This exists for development convenience.
    """

    def __init__(self, max_requests: int, window_seconds: int = 60) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    @property
    def max_requests(self) -> int:
        """Return the maximum requests allowed per window."""
        return self._max

    def is_allowed(self, key: str) -> tuple[bool, int, int]:
        """Check whether a request from *key* is within the limit.

        :param key: Identifies the client (IP or user ID).
        :returns: ``(allowed, remaining, reset_seconds)``.
        """
        now = time.monotonic()
        cutoff = now - self._window
        bucket = self._buckets[key]

        # Prune timestamps outside the window.
        self._buckets[key] = [t for t in bucket if t > cutoff]
        bucket = self._buckets[key]

        allowed = len(bucket) < self._max
        if allowed:
            bucket.append(now)

        remaining = max(0, self._max - len(bucket))
        reset_at = int(bucket[0] + self._window) if bucket else int(now + self._window)
        return allowed, remaining, reset_at


# Shared rate limiter instances.
_anon_limiter = _InMemoryRateLimiter(max_requests=settings.RATE_LIMIT_ANON_PER_MIN)
_user_limiter = _InMemoryRateLimiter(max_requests=settings.RATE_LIMIT_USER_PER_MIN)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces per-client request rate limits."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Check rate limits before passing the request to the next handler.

        :param request: The incoming HTTP request.
        :param call_next: The next middleware or route handler.
        :returns: The HTTP response, or a 429 error response if rate-limited.
        """
        # Determine rate limit key: authenticated user ID or client IP.
        user = getattr(request.state, "user", None)
        rate_limit_key: str
        limiter: _InMemoryRateLimiter

        if user is not None:
            rate_limit_key = f"user:{user.id}"
            limiter = _user_limiter
        else:
            client_ip = request.client.host if request.client else "unknown"
            rate_limit_key = f"ip:{client_ip}"
            limiter = _anon_limiter

        allowed, remaining, reset_at = limiter.is_allowed(rate_limit_key)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content=error_envelope(
                    "Rate limit exceeded. Try again later.",
                    error_code=ErrorCode.RATE_LIMITED,
                    request_id=getattr(request.state, "request_id", None),
                ),
                headers={
                    "X-RateLimit-Limit": str(limiter.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                    "Retry-After": str(max(1, reset_at - int(time.monotonic()))),
                },
            )

        response: Response = await call_next(request)

        response.headers["X-RateLimit-Limit"] = str(limiter.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_at)

        return response


__all__ = ["RateLimitMiddleware"]
