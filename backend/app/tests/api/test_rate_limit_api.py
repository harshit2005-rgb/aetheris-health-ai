"""End-to-end checks that rate limiting reaches the right tier through the app.

The unit tests in ``app/tests/unit/middleware/test_rate_limit.py`` verify tier
selection in isolation. These verify the property that actually broke in
production: that ``AuthMiddleware`` runs *outside* ``RateLimitMiddleware``, so
identity exists by the time a budget is chosen.

That ordering is invisible in isolation — every unit test passes with the stack
assembled backwards. What it produces is a silent downgrade of every
authenticated request to the anonymous per-IP tier, which behind a load balancer
means one shared bucket of 60 requests per minute for an entire hospital. These
tests assert on the advertised ``X-RateLimit-Limit`` header, which is the
cheapest observable proof of which tier was applied.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.security import create_access_token

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    """Plain HTTP client — these tests never reach the database."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as http_client:
        yield http_client


def _bearer(hospital_id: uuid.UUID | None = None) -> dict[str, str]:
    """Authorization header carrying a genuine, signed access token."""
    token = create_access_token(
        user_id=uuid.uuid4(),
        hospital_id=hospital_id,
        roles=["Doctor"],
        permissions=["patient.read"],
    )
    return {"Authorization": f"Bearer {token}"}


class TestTierAppliedThroughTheStack:
    """Which budget the assembled application bills a request against."""

    @pytest.mark.asyncio
    async def test_anonymous_request_advertises_the_anonymous_limit(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/healthz")

        assert response.headers["X-RateLimit-Limit"] == str(settings.RATE_LIMIT_ANON_PER_MIN)

    @pytest.mark.asyncio
    async def test_authenticated_request_advertises_the_user_limit(
        self, client: AsyncClient
    ) -> None:
        """The regression guard for the middleware ordering."""
        response = await client.get("/healthz", headers=_bearer())

        assert response.headers["X-RateLimit-Limit"] == str(settings.RATE_LIMIT_USER_PER_MIN)
        assert response.headers["X-RateLimit-Limit"] != str(settings.RATE_LIMIT_ANON_PER_MIN)

    @pytest.mark.asyncio
    async def test_authenticated_traffic_does_not_consume_the_anonymous_budget(
        self, client: AsyncClient
    ) -> None:
        """A logged-in user must not exhaust the bucket shared by anonymous callers."""
        headers = _bearer()
        for _ in range(5):
            await client.get("/healthz", headers=headers)

        anonymous = await client.get("/healthz")

        remaining = int(anonymous.headers["X-RateLimit-Remaining"])
        assert remaining == settings.RATE_LIMIT_ANON_PER_MIN - 1

    @pytest.mark.asyncio
    async def test_two_users_have_independent_budgets(self, client: AsyncClient) -> None:
        first = await client.get("/healthz", headers=_bearer())
        second = await client.get("/healthz", headers=_bearer())

        assert first.headers["X-RateLimit-Remaining"] == second.headers["X-RateLimit-Remaining"]

    @pytest.mark.asyncio
    async def test_an_invalid_token_is_billed_as_anonymous(self, client: AsyncClient) -> None:
        """A forged token must not buy the higher authenticated budget."""
        response = await client.get(
            "/healthz", headers={"Authorization": "Bearer forged.token.value"}
        )

        assert response.headers["X-RateLimit-Limit"] == str(settings.RATE_LIMIT_ANON_PER_MIN)


class TestExceededResponse:
    """The 429 contract in ``docs/06-API_STANDARDS.md`` §5.3 and §15."""

    @pytest.mark.asyncio
    async def test_exceeding_the_limit_returns_the_standard_error_envelope(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "RATE_LIMIT_ANON_PER_MIN", 2)

        await client.get("/healthz")
        await client.get("/healthz")
        blocked = await client.get("/healthz")

        assert blocked.status_code == 429
        body = blocked.json()
        assert body["success"] is False
        assert body["error_code"] == "RATE_LIMITED"

    @pytest.mark.asyncio
    async def test_a_429_carries_retry_and_reset_headers(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "RATE_LIMIT_ANON_PER_MIN", 1)

        await client.get("/healthz")
        blocked = await client.get("/healthz")

        assert blocked.headers["X-RateLimit-Remaining"] == "0"
        assert int(blocked.headers["Retry-After"]) >= 1
        assert int(blocked.headers["X-RateLimit-Reset"]) > 0

    @pytest.mark.asyncio
    async def test_a_429_still_carries_a_correlation_id(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """§16 requires a request id on every response, including rejected ones.

        The limiter short-circuits before the router, so this only holds while
        ``RequestIDMiddleware`` sits outside it.
        """
        monkeypatch.setattr(settings, "RATE_LIMIT_ANON_PER_MIN", 1)

        await client.get("/healthz")
        blocked = await client.get("/healthz")

        assert blocked.json()["metadata"]["request_id"] is not None
