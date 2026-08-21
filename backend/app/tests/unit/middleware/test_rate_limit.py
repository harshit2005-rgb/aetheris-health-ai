"""Unit tests for :mod:`app.middleware.rate_limit`.

These cover the tier selection rules in ``docs/06-API_STANDARDS.md`` §15 and the
failure behaviour around Redis. The property under test throughout is *which
budget a request is billed against* — the defect these tests exist to prevent
was authenticated traffic silently falling through to the anonymous per-IP
tier, which behind a proxy meant an entire hospital sharing 60 requests per
minute while ``RATE_LIMIT_USER_PER_MIN`` sat unused.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.config import settings
from app.middleware import rate_limit
from app.middleware.rate_limit import (
    InMemoryRateLimiter,
    RateLimitMiddleware,
    _client_ip,
    reset_limiter_state,
)

# Captured at import, before the suite-wide ``reset_rate_limiters`` fixture
# replaces it with a stub that forces the circuit open. The Redis tests below
# restore this so they exercise the real short-circuit logic.
_REAL_CIRCUIT_CHECK = rate_limit._redis_is_circuit_open


def _request(
    *,
    path: str = "/api/v1/patients",
    user_id: uuid.UUID | None = None,
    hospital_id: uuid.UUID | None = None,
    client_host: str | None = "203.0.113.7",
    headers: dict[str, str] | None = None,
) -> Any:
    """Build a stand-in request exposing only what the middleware reads."""
    return SimpleNamespace(
        url=SimpleNamespace(path=path),
        state=SimpleNamespace(user_id=user_id, hospital_id=hospital_id),
        client=SimpleNamespace(host=client_host) if client_host else None,
        headers=headers or {},
    )


@pytest.fixture(autouse=True)
def _clean_limiter_state() -> None:
    """Reset the module-level counters between cases."""
    reset_limiter_state()


class TestTierSelection:
    """Which ``(key, limit)`` pairs a request is checked against."""

    def test_anonymous_request_uses_ip_and_anon_limit(self) -> None:
        limits = RateLimitMiddleware._applicable_limits(_request())

        assert limits == [("ip:203.0.113.7", settings.RATE_LIMIT_ANON_PER_MIN)]

    def test_authenticated_request_uses_user_limit_not_ip(self) -> None:
        """The regression guard: an identified caller must never be billed by IP."""
        user_id = uuid.uuid4()

        limits = RateLimitMiddleware._applicable_limits(_request(user_id=user_id))

        assert (f"user:{user_id}", settings.RATE_LIMIT_USER_PER_MIN) in limits
        assert not any(key.startswith("ip:") for key, _ in limits)

    def test_authenticated_request_also_checks_hospital_ceiling(self) -> None:
        """§15 caps a tenant as well as a user, so both budgets apply."""
        user_id, hospital_id = uuid.uuid4(), uuid.uuid4()

        limits = RateLimitMiddleware._applicable_limits(
            _request(user_id=user_id, hospital_id=hospital_id)
        )

        assert limits == [
            (f"user:{user_id}", settings.RATE_LIMIT_USER_PER_MIN),
            (f"hospital:{hospital_id}", settings.RATE_LIMIT_HOSPITAL_PER_MIN),
        ]

    def test_token_without_hospital_claim_still_gets_user_limit(self) -> None:
        user_id = uuid.uuid4()

        limits = RateLimitMiddleware._applicable_limits(_request(user_id=user_id, hospital_id=None))

        assert limits == [(f"user:{user_id}", settings.RATE_LIMIT_USER_PER_MIN)]

    def test_ai_path_uses_the_lower_ai_budget(self) -> None:
        """AI calls cost money per request, so they get their own ceiling."""
        user_id = uuid.uuid4()

        limits = RateLimitMiddleware._applicable_limits(
            _request(path="/api/v1/appointments/recommend-slot", user_id=user_id)
        )

        assert limits[0] == (f"ai:{user_id}", settings.RATE_LIMIT_AI_PER_MIN)

    def test_anonymous_ai_path_uses_ai_budget_on_the_ip_key(self) -> None:
        limits = RateLimitMiddleware._applicable_limits(
            _request(path="/api/v1/appointments/recommend-slot")
        )

        assert limits == [("ip:203.0.113.7", settings.RATE_LIMIT_AI_PER_MIN)]


class TestClientIp:
    """Proxy-header trust. Getting this wrong fails open in both directions."""

    def test_ignores_forwarded_header_by_default(self) -> None:
        """Untrusted X-Forwarded-For would let any client mint a fresh bucket."""
        request = _request(headers={"X-Forwarded-For": "198.51.100.1"})

        assert _client_ip(request) == "203.0.113.7"

    def test_uses_forwarded_header_when_trusted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "RATE_LIMIT_TRUST_PROXY_HEADER", True)
        request = _request(headers={"X-Forwarded-For": "198.51.100.1"})

        assert _client_ip(request) == "198.51.100.1"

    def test_takes_leftmost_entry_of_the_proxy_chain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The original client is left-most; the rest are proxy hops."""
        monkeypatch.setattr(settings, "RATE_LIMIT_TRUST_PROXY_HEADER", True)
        request = _request(headers={"X-Forwarded-For": "198.51.100.1, 10.0.0.1, 10.0.0.2"})

        assert _client_ip(request) == "198.51.100.1"

    def test_falls_back_when_peer_is_unknown(self) -> None:
        assert _client_ip(_request(client_host=None)) == "unknown"


class TestInMemoryRateLimiter:
    """The fallback counter used when Redis is unreachable."""

    def test_allows_up_to_the_limit_then_blocks(self) -> None:
        limiter = InMemoryRateLimiter()

        results = [limiter.check("k", limit=3)[0] for _ in range(4)]

        assert results == [True, True, True, False]

    def test_remaining_counts_down(self) -> None:
        limiter = InMemoryRateLimiter()

        assert limiter.check("k", limit=3)[1] == 2
        assert limiter.check("k", limit=3)[1] == 1

    def test_keys_are_independent(self) -> None:
        limiter = InMemoryRateLimiter()
        limiter.check("a", limit=1)

        allowed, _, _ = limiter.check("b", limit=1)

        assert allowed is True

    def test_blocked_request_is_not_counted_again(self) -> None:
        """A rejected request must not extend the window it was rejected by."""
        limiter = InMemoryRateLimiter()
        limiter.check("k", limit=1)

        limiter.check("k", limit=1)
        _, remaining, _ = limiter.check("k", limit=1)

        assert remaining == 0


class TestRedisFallback:
    """Redis is optional infrastructure; an outage must not take the API down."""

    @pytest.fixture(autouse=True)
    def _use_real_circuit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Undo the suite-wide stub so Redis is actually attempted here."""
        monkeypatch.setattr(rate_limit, "_redis_is_circuit_open", _REAL_CIRCUIT_CHECK)
        reset_limiter_state()

    @pytest.mark.asyncio
    async def test_falls_back_to_memory_when_redis_errors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _boom(key: str, limit: int) -> tuple[bool, int, int]:
            raise RedisConnectionError("no route to host")

        monkeypatch.setattr(rate_limit._redis_limiter, "check", _boom)

        allowed, remaining, _ = await RateLimitMiddleware._check("user:x", limit=5)

        assert allowed is True
        assert remaining == 4

    @pytest.mark.asyncio
    async def test_failure_opens_the_circuit_so_redis_is_not_retried(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Retrying a dead Redis per request would add its timeout to every call."""
        calls = 0

        async def _boom(key: str, limit: int) -> tuple[bool, int, int]:
            nonlocal calls
            calls += 1
            raise RedisConnectionError("no route to host")

        monkeypatch.setattr(rate_limit._redis_limiter, "check", _boom)

        await RateLimitMiddleware._check("user:x", limit=5)
        await RateLimitMiddleware._check("user:x", limit=5)
        await RateLimitMiddleware._check("user:x", limit=5)

        assert calls == 1

    @pytest.mark.asyncio
    async def test_uses_redis_result_when_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _ok(key: str, limit: int) -> tuple[bool, int, int]:
            return False, 0, 1_800_000_000

        monkeypatch.setattr(rate_limit._redis_limiter, "check", _ok)

        allowed, remaining, reset_at = await RateLimitMiddleware._check("user:x", limit=5)

        assert (allowed, remaining, reset_at) == (False, 0, 1_800_000_000)


class TestHeaderBudget:
    """Advertised headers must describe the tightest applicable budget."""

    def test_keeps_the_smaller_remaining(self) -> None:
        current = (300, 250, 100)

        assert RateLimitMiddleware._tightest(current, 1000, 10, 200) == (1000, 10, 200)

    def test_keeps_existing_when_it_is_tighter(self) -> None:
        current = (300, 5, 100)

        assert RateLimitMiddleware._tightest(current, 1000, 900, 200) == current

    def test_first_budget_wins_when_none_recorded(self) -> None:
        assert RateLimitMiddleware._tightest(None, 300, 299, 100) == (300, 299, 100)
