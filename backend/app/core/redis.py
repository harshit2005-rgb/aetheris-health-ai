"""Shared async Redis client.

One connection pool for the whole process, created on first use and closed by
the application lifespan. Two callers depend on it:

* :mod:`app.middleware.rate_limit` — the counters behind
  ``docs/06-API_STANDARDS.md`` §15, which specifies limits "tracked in Redis" so
  they hold across worker processes.
* the health endpoints — a readiness probe that cannot observe a Redis outage is
  not a readiness probe.

Redis is treated as **optional infrastructure**. Every helper here reports
failure by returning ``None`` or ``False`` rather than raising, so a Redis
outage degrades rate limiting to per-process counting instead of returning 500s
across the API. Callers decide what to do with the absence.
"""

from __future__ import annotations

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = structlog.get_logger(__name__)

_client: Redis | None = None


def get_redis_client() -> Redis:
    """Return the process-wide Redis client, creating it on first call.

    Construction does not connect — ``redis.asyncio`` dials lazily on the first
    command — so this is safe to call at import-adjacent points and in tests.

    :returns: The shared client.
    """
    global _client
    if _client is None:
        _client = Redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )
    return _client


async def ping_redis() -> bool:
    """Report whether Redis answers a ``PING``.

    :returns: ``True`` when Redis is reachable, ``False`` on any Redis or
        connection error.
    """
    try:
        return bool(await get_redis_client().ping())
    except (RedisError, OSError) as exc:
        logger.warning("redis_ping_failed", error=str(exc))
        return False


async def close_redis_client() -> None:
    """Close the shared client and drop the reference.

    Called from the application lifespan on shutdown. Safe to call when no
    client was ever created.
    """
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except (RedisError, OSError) as exc:  # pragma: no cover - shutdown path
            logger.warning("redis_close_failed", error=str(exc))
        finally:
            _client = None


def reset_redis_client() -> None:
    """Drop the cached client without closing it.

    Test-support hook: lets a test swap ``settings.REDIS_URL`` or install a
    double without leaking a client between cases.
    """
    global _client
    _client = None


__all__ = [
    "close_redis_client",
    "get_redis_client",
    "ping_redis",
    "reset_redis_client",
]
