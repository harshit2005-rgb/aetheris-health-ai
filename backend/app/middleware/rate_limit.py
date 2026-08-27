"""Rate limiting middleware.

Implements the tiers in ``docs/06-API_STANDARDS.md`` §15:

===============  =========================  ==================================
Tier             Default                    Key
===============  =========================  ==================================
Anonymous        60 / minute                client IP
Authenticated    300 / minute               user id
Hospital         1000 / minute              hospital id (tenant-wide ceiling)
AI endpoints     30 / minute                user id (or client IP if anonymous)
===============  =========================  ==================================

An authenticated request is checked against **both** its user limit and its
hospital limit; the first to trip returns 429. Anonymous requests are checked
against the client IP only.

Two properties this middleware depends on, both enforced by the ordering in
:func:`app.main._register_middleware`:

* :class:`~app.middleware.auth.AuthMiddleware` runs *outside* it, so
  ``request.state.user_id`` is populated before a limit is chosen. When that
  ordering is wrong every authenticated request silently falls back to the
  anonymous per-IP tier, which behind a proxy means an entire hospital shares
  60 requests per minute.
* ``RequestIDMiddleware`` runs outside it too, so a 429 body still carries the
  correlation id that ``docs/06-API_STANDARDS.md`` §16 requires on every
  response.

Counters live in Redis so limits hold across worker processes. If Redis is
unreachable the middleware degrades to per-process in-memory counting rather
than failing requests — a rate limiter that takes the API down with it is worse
than one that is briefly too permissive.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Protocol

import structlog
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.envelope import error_envelope
from app.core.error_codes import ErrorCode
from app.core.redis import get_redis_client

logger = structlog.get_logger(__name__)

WINDOW_SECONDS = 60

#: Path prefixes billed against the AI tier. AI calls cost real money per
#: request (``docs/06-API_STANDARDS.md`` §15, "cost control"), so they get a
#: lower ceiling than ordinary reads.
_AI_PATH_MARKERS: tuple[str, ...] = ("/recommend-slot", "/ai/")


class _Decision(Protocol):
    """Shape returned by a backend check."""

    def __call__(self, key: str, limit: int) -> tuple[bool, int, int]:
        """Return ``(allowed, remaining, reset_epoch)``."""
        ...


class InMemoryRateLimiter:
    """Sliding-window counter held in this process only.

    The fallback used when Redis is unreachable, and the backend used by tests.
    Correct for a single process; under multiple workers each process counts
    independently, so the effective limit multiplies by the worker count. That
    is the reason Redis is the primary backend rather than this.
    """

    def __init__(self, window_seconds: int = WINDOW_SECONDS) -> None:
        self._window = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, limit: int) -> tuple[bool, int, int]:
        """Record a hit against *key* and report the resulting budget.

        :param key: Identifies the caller within its tier.
        :param limit: Maximum requests allowed in the window.
        :returns: ``(allowed, remaining, reset_epoch_seconds)``.
        """
        now = time.time()
        cutoff = now - self._window

        bucket = [t for t in self._buckets[key] if t > cutoff]
        allowed = len(bucket) < limit
        if allowed:
            bucket.append(now)
        self._buckets[key] = bucket

        remaining = max(0, limit - len(bucket))
        reset_at = int((bucket[0] if bucket else now) + self._window)
        return allowed, remaining, reset_at

    def clear(self) -> None:
        """Drop every counter. Test-support hook."""
        self._buckets.clear()


class RedisRateLimiter:
    """Fixed-window counter shared by every process via Redis.

    Uses ``INCR`` plus a first-write ``EXPIRE``, pipelined into one round trip.
    A fixed window can admit up to ``2 * limit`` requests across a window
    boundary; that is accepted here because the alternative (a sorted-set
    sliding window) costs materially more per request, and these limits are
    abuse control rather than metering.
    """

    def __init__(self, window_seconds: int = WINDOW_SECONDS) -> None:
        self._window = window_seconds

    async def check(self, key: str, limit: int) -> tuple[bool, int, int]:
        """Record a hit against *key* in Redis and report the budget.

        :param key: Identifies the caller within its tier.
        :param limit: Maximum requests allowed in the window.
        :returns: ``(allowed, remaining, reset_epoch_seconds)``.
        :raises redis.exceptions.RedisError: If Redis is unreachable. The caller
            is expected to fall back rather than fail the request.
        """
        now = int(time.time())
        window_start = now - (now % self._window)
        redis_key = f"ratelimit:{{{key}}}:{window_start}"
        reset_at = window_start + self._window

        client = get_redis_client()
        async with client.pipeline(transaction=False) as pipe:
            pipe.incr(redis_key)
            # Re-arming the TTL each hit is harmless and avoids a race where the
            # key is created but the EXPIRE is lost, which would leak the key.
            pipe.expire(redis_key, self._window)
            count = int((await pipe.execute())[0])

        allowed = count <= limit
        remaining = max(0, limit - count)
        return allowed, remaining, reset_at


# Shared instances. The in-memory limiter holds state, so it must be a
# module-level singleton rather than constructed per request.
_memory_limiter = InMemoryRateLimiter()
_redis_limiter = RedisRateLimiter()

#: Seconds to stop attempting Redis after a failure. Without this, every request
#: during an outage pays the full connect timeout before falling back, turning a
#: degraded limiter into a latency incident across the whole API.
REDIS_RETRY_COOLDOWN_SECONDS = 10.0

#: Monotonic deadline before which Redis is skipped entirely. Zero means "try".
_redis_down_until: float = 0.0


def _redis_is_circuit_open() -> bool:
    """Return whether Redis attempts are currently short-circuited."""
    return time.monotonic() < _redis_down_until


def _trip_redis_circuit() -> None:
    """Skip Redis for the cooldown window after a failure."""
    global _redis_down_until
    _redis_down_until = time.monotonic() + REDIS_RETRY_COOLDOWN_SECONDS


def reset_limiter_state() -> None:
    """Clear counters and close the Redis circuit.

    Test-support hook: the limiters are module-level singletons, so their state
    outlives any individual app instance and would otherwise leak between tests.
    """
    global _redis_down_until
    _redis_down_until = 0.0
    _memory_limiter.clear()


def _client_ip(request: Request) -> str:
    """Resolve the caller's IP, honouring proxy headers only when configured.

    ``X-Forwarded-For`` is attacker-controlled unless a trusted proxy overwrites
    it, so it is consulted only when ``RATE_LIMIT_TRUST_PROXY_HEADER`` is on.
    Without that flag, every user behind a load balancer shares the balancer's
    address and therefore a single anonymous bucket; with it wrongly enabled,
    any client can forge a fresh identity per request. Both failure modes are
    silent, which is why this is explicit configuration rather than a guess.

    :param request: The incoming request.
    :returns: The client IP, or ``"unknown"`` when it cannot be determined.
    """
    if settings.RATE_LIMIT_TRUST_PROXY_HEADER:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Left-most entry is the original client; the rest are proxy hops.
            client = forwarded.split(",")[0].strip()
            if client:
                return client
    return request.client.host if request.client else "unknown"


def _is_ai_path(path: str) -> bool:
    """Return whether *path* should be billed against the AI tier."""
    return any(marker in path for marker in _AI_PATH_MARKERS)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce per-user, per-hospital, and per-IP request limits."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Check every applicable limit before handing off to the next layer.

        :param request: The incoming HTTP request.
        :param call_next: The next middleware or route handler.
        :returns: The response, or a 429 envelope when a limit is exceeded.
        """
        for key, limit in self._applicable_limits(request):
            allowed, remaining, reset_at = await self._check(key, limit)
            if not allowed:
                logger.info(
                    "rate_limit_exceeded",
                    limit_key=key,
                    limit=limit,
                    path=request.url.path,
                )
                return self._too_many_requests(request, limit, reset_at)

            # Headers advertise the tightest budget the caller has left, so a
            # client near its hospital ceiling is not told it has 299 requests
            # of user budget remaining.
            request.state.rate_limit_headers = self._tightest(
                getattr(request.state, "rate_limit_headers", None),
                limit,
                remaining,
                reset_at,
            )

        response: Response = await call_next(request)

        headers = getattr(request.state, "rate_limit_headers", None)
        if headers is not None:
            limit, remaining, reset_at = headers
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_at)

        return response

    @staticmethod
    def _applicable_limits(request: Request) -> list[tuple[str, int]]:
        """Build the ``(key, limit)`` pairs this request must satisfy.

        :param request: The incoming request, after ``AuthMiddleware`` has run.
        :returns: One pair for an anonymous caller; two for an authenticated one
            (user and hospital), so a single user cannot exhaust a tenant's
            budget unnoticed.
        """
        user_id = getattr(request.state, "user_id", None)
        hospital_id = getattr(request.state, "hospital_id", None)
        is_ai = _is_ai_path(request.url.path)

        if user_id is None:
            ip = _client_ip(request)
            limit = settings.RATE_LIMIT_AI_PER_MIN if is_ai else settings.RATE_LIMIT_ANON_PER_MIN
            return [(f"ip:{ip}", limit)]

        limits = [
            (
                f"{'ai' if is_ai else 'user'}:{user_id}",
                settings.RATE_LIMIT_AI_PER_MIN if is_ai else settings.RATE_LIMIT_USER_PER_MIN,
            )
        ]
        if hospital_id is not None:
            limits.append((f"hospital:{hospital_id}", settings.RATE_LIMIT_HOSPITAL_PER_MIN))
        return limits

    @staticmethod
    async def _check(key: str, limit: int) -> tuple[bool, int, int]:
        """Check *key* against Redis, falling back to the in-process counter.

        :param key: Tier-qualified counter key.
        :param limit: Maximum requests per window.
        :returns: ``(allowed, remaining, reset_epoch_seconds)``.
        """
        if not _redis_is_circuit_open():
            try:
                return await _redis_limiter.check(key, limit)
            except (RedisError, OSError) as exc:
                _trip_redis_circuit()
                logger.warning(
                    "rate_limit_redis_unavailable",
                    error=str(exc),
                    cooldown_seconds=REDIS_RETRY_COOLDOWN_SECONDS,
                )
        return _memory_limiter.check(key, limit)

    @staticmethod
    def _tightest(
        current: tuple[int, int, int] | None,
        limit: int,
        remaining: int,
        reset_at: int,
    ) -> tuple[int, int, int]:
        """Keep whichever budget leaves the caller with fewer requests."""
        if current is None or remaining < current[1]:
            return (limit, remaining, reset_at)
        return current

    @staticmethod
    def _too_many_requests(request: Request, limit: int, reset_at: int) -> JSONResponse:
        """Build the 429 envelope with the standard rate-limit headers.

        :param request: The request being rejected.
        :param limit: The limit that was exceeded.
        :param reset_at: Epoch second at which the window resets.
        :returns: A 429 JSON response in the standard error envelope.
        """
        retry_after = max(1, reset_at - int(time.time()))
        return JSONResponse(
            status_code=429,
            content=error_envelope(
                "Rate limit exceeded. Try again later.",
                error_code=ErrorCode.RATE_LIMITED,
                request_id=getattr(request.state, "request_id", None),
            ),
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_at),
                "Retry-After": str(retry_after),
            },
        )


__all__ = [
    "InMemoryRateLimiter",
    "RateLimitMiddleware",
    "RedisRateLimiter",
    "reset_limiter_state",
]
