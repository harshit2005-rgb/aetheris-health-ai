"""Unit tests for :mod:`app.middleware.auth`.

The middleware resolves identity for downstream consumers; it is explicitly not
the authorization boundary (``docs/03-ARCHITECTURE.md`` §4.2 — routes enforce,
via ``require_permission``). Two properties matter here and are easy to break in
opposite directions:

* it must **populate** ``user_id`` / ``hospital_id`` for a valid token, because
  the rate limiter bills requests against them; and
* it must **never reject** a request, because public endpoints legitimately
  arrive without a usable token and rejecting here would create a second,
  divergent auth path.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from starlette.responses import Response

from app.core.security import create_access_token
from app.middleware.auth import AuthMiddleware


def _request(headers: dict[str, str] | None = None) -> Any:
    """Build a stand-in request exposing only what the middleware touches."""
    return SimpleNamespace(
        headers=headers or {},
        state=SimpleNamespace(),
        url=SimpleNamespace(path="/api/v1/patients"),
    )


async def _dispatch(request: Any) -> Any:
    """Run the middleware over *request*, returning a sentinel response."""
    sentinel = object()

    async def _call_next(_: Any) -> Any:
        return sentinel

    middleware = AuthMiddleware(app=lambda *a, **k: None)  # type: ignore[arg-type]
    return await middleware.dispatch(request, _call_next)


def _token(user_id: uuid.UUID, hospital_id: uuid.UUID | None = None) -> str:
    """Mint a genuine access token so signature verification is exercised."""
    return create_access_token(
        user_id=user_id,
        hospital_id=hospital_id,
        roles=["Doctor"],
        permissions=["patient.read"],
    )


class TestIdentityResolution:
    """A valid token populates the state the rate limiter depends on."""

    @pytest.mark.asyncio
    async def test_sets_user_and_hospital_from_a_valid_token(self) -> None:
        user_id, hospital_id = uuid.uuid4(), uuid.uuid4()
        request = _request({"Authorization": f"Bearer {_token(user_id, hospital_id)}"})

        await _dispatch(request)

        assert request.state.user_id == user_id
        assert request.state.hospital_id == hospital_id

    @pytest.mark.asyncio
    async def test_token_without_hospital_claim_leaves_hospital_none(self) -> None:
        user_id = uuid.uuid4()
        request = _request({"Authorization": f"Bearer {_token(user_id)}"})

        await _dispatch(request)

        assert request.state.user_id == user_id
        assert request.state.hospital_id is None

    @pytest.mark.asyncio
    async def test_stores_the_raw_token(self) -> None:
        token = _token(uuid.uuid4())
        request = _request({"Authorization": f"Bearer {token}"})

        await _dispatch(request)

        assert request.state.raw_token == token


class TestNeverRejects:
    """Unusable credentials degrade to anonymous rather than erroring."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("label", "headers"),
        [
            ("no header", {}),
            ("empty bearer", {"Authorization": "Bearer "}),
            ("wrong scheme", {"Authorization": "Basic abc123"}),
            ("garbage token", {"Authorization": "Bearer not.a.jwt"}),
            ("tampered signature", {"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.e30.x"}),
        ],
    )
    async def test_leaves_identity_unset_without_raising(
        self, label: str, headers: dict[str, str]
    ) -> None:
        request = _request(headers)

        await _dispatch(request)

        assert request.state.user_id is None, label
        assert request.state.hospital_id is None, label

    @pytest.mark.asyncio
    async def test_always_calls_the_next_layer(self) -> None:
        """Public endpoints must still be reachable without a token."""
        request = _request({"Authorization": "Bearer not.a.jwt"})
        called = False
        expected = Response(status_code=204)

        async def _call_next(_: Any) -> Response:
            nonlocal called
            called = True
            return expected

        middleware = AuthMiddleware(app=lambda *a, **k: None)  # type: ignore[arg-type]
        result = await middleware.dispatch(request, _call_next)

        assert called is True
        assert result is expected

    @pytest.mark.asyncio
    async def test_refresh_token_is_not_accepted_as_identity(self) -> None:
        """Only ``type: access`` tokens establish identity."""
        from app.core.security import create_mfa_ticket

        request = _request({"Authorization": f"Bearer {create_mfa_ticket(uuid.uuid4())}"})

        await _dispatch(request)

        assert request.state.user_id is None
