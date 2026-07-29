"""API tests for the authentication endpoints.

These exist because the auth module shipped with no HTTP-level coverage, and a
whole class of bug slipped through as a result: every service wrote to the
session but nothing ever committed, so **the API reported success for writes
that were silently rolled back**. Unit tests with mocked repositories cannot
detect that — only a test that writes through the real stack and then reads the
row back can.

``docs/06-API_STANDARDS.md`` §24 and ``docs/11-TESTING_STRATEGY.md`` §2.3.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api.dependencies.db import get_db_session
from app.core.security import hash_password
from app.main import create_app
from app.models.refresh_token import RefreshToken
from app.models.user import User

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.database

PASSWORD = "Str0ng!Passw0rd123"


@pytest_asyncio.fixture
async def api(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """HTTP client sharing the test's rolled-back session."""
    application = create_app()

    async def _override() -> AsyncGenerator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_db_session] = _override
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        yield client
    application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def account(db_session: AsyncSession, hospital_id: uuid.UUID) -> dict[str, Any]:
    """A real, active user that can log in."""
    email = f"login-{uuid.uuid4().hex[:12]}@hospital.example"
    user = User(
        id=uuid.uuid4(),
        hospital_id=hospital_id,
        email=email,
        password_hash=hash_password(PASSWORD),
        first_name="Login",
        last_name="Tester",
    )
    db_session.add(user)
    await db_session.flush()
    return {"id": user.id, "email": email}


class TestLogin:
    """``POST /api/v1/auth/login``."""

    async def test_login_with_valid_credentials_returns_tokens(
        self, api: AsyncClient, account: dict[str, Any]
    ) -> None:
        response = await api.post(
            "/api/v1/auth/login", json={"email": account["email"], "password": PASSWORD}
        )

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["access_token"]
        assert data["refresh_token"]

    async def test_login_persists_the_refresh_token(
        self, api: AsyncClient, db_session: AsyncSession, account: dict[str, Any]
    ) -> None:
        # Regression: the row was created in the session but never committed, so
        # the token handed to the client did not exist server-side and every
        # subsequent refresh failed with "Invalid refresh token".
        await api.post("/api/v1/auth/login", json={"email": account["email"], "password": PASSWORD})

        stored = await db_session.execute(
            select(func.count())
            .select_from(RefreshToken)
            .where(RefreshToken.user_id == account["id"])
        )
        assert stored.scalar_one() == 1

    async def test_login_with_a_wrong_password_returns_401(
        self, api: AsyncClient, account: dict[str, Any]
    ) -> None:
        response = await api.post(
            "/api/v1/auth/login", json={"email": account["email"], "password": "WrongPassw0rd!"}
        )

        assert response.status_code == 401

    async def test_login_with_an_unknown_email_returns_401(self, api: AsyncClient) -> None:
        # Must be indistinguishable from a wrong password
        # (docs/modules/01-authentication.md §4, rule 11).
        response = await api.post(
            "/api/v1/auth/login",
            json={"email": "nobody@hospital.example", "password": PASSWORD},
        )

        assert response.status_code == 401

    async def test_login_response_uses_the_standard_error_envelope(
        self, api: AsyncClient, account: dict[str, Any]
    ) -> None:
        response = await api.post(
            "/api/v1/auth/login", json={"email": account["email"], "password": "WrongPassw0rd!"}
        )

        body = response.json()
        assert body["success"] is False
        assert body["error_code"] == "AUTHENTICATION_REQUIRED"
        assert "detail" not in body

    async def test_a_validation_failure_uses_the_standard_error_envelope(
        self, api: AsyncClient
    ) -> None:
        # Regression: FastAPI's raw {"detail": [...]} leaked `loc` tuples and
        # did not match docs/06-API_STANDARDS.md §5.3.
        response = await api.post("/api/v1/auth/login", json={"email": "not-an-email"})

        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert body["error_code"] == "VALIDATION_ERROR"
        assert isinstance(body["errors"], list)
        assert {"field", "message"} <= set(body["errors"][0])


class TestFailedLoginLockout:
    """Brute-force protection (``docs/modules/01-authentication.md`` §4, rule 4)."""

    async def test_a_failed_attempt_increments_the_counter(
        self, api: AsyncClient, db_session: AsyncSession, account: dict[str, Any]
    ) -> None:
        # Regression: the increment happened on a request that then raised, and
        # the caller's commit was never reached, so the counter always read 0
        # and lockout could never trigger.
        await api.post(
            "/api/v1/auth/login", json={"email": account["email"], "password": "WrongPassw0rd!"}
        )

        result = await db_session.execute(
            select(User.failed_login_attempts).where(User.id == account["id"])
        )
        assert result.scalar_one() == 1

    async def test_repeated_failures_lock_the_account(
        self, api: AsyncClient, db_session: AsyncSession, account: dict[str, Any]
    ) -> None:
        from app.core.config import settings

        for _ in range(settings.MAX_FAILED_LOGIN_ATTEMPTS):
            await api.post(
                "/api/v1/auth/login",
                json={"email": account["email"], "password": "WrongPassw0rd!"},
            )

        result = await db_session.execute(
            select(User.failed_login_attempts, User.locked_until).where(User.id == account["id"])
        )
        attempts, locked_until = result.one()
        assert attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS
        assert locked_until is not None

    async def test_a_locked_account_cannot_log_in_with_the_correct_password(
        self, api: AsyncClient, account: dict[str, Any]
    ) -> None:
        from app.core.config import settings

        for _ in range(settings.MAX_FAILED_LOGIN_ATTEMPTS):
            await api.post(
                "/api/v1/auth/login",
                json={"email": account["email"], "password": "WrongPassw0rd!"},
            )

        response = await api.post(
            "/api/v1/auth/login", json={"email": account["email"], "password": PASSWORD}
        )

        assert response.status_code != 200


class TestRefreshRotation:
    """``POST /api/v1/auth/refresh`` — rotation and reuse detection."""

    async def _login(self, api: AsyncClient, email: str) -> dict[str, Any]:
        response = await api.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert response.status_code == 200, response.text
        return dict(response.json()["data"])

    async def test_a_fresh_refresh_token_is_accepted(
        self, api: AsyncClient, account: dict[str, Any]
    ) -> None:
        # Regression: this returned 401 on first use because the token was
        # never persisted, so sessions could not be renewed at all.
        tokens = await self._login(api, account["email"])

        response = await api.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )

        assert response.status_code == 200, response.text
        assert response.json()["data"]["access_token"]

    async def test_refresh_rotates_the_token(
        self, api: AsyncClient, account: dict[str, Any]
    ) -> None:
        tokens = await self._login(api, account["email"])

        rotated = await api.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )

        assert rotated.json()["data"]["refresh_token"] != tokens["refresh_token"]

    async def test_reusing_a_rotated_token_is_rejected(
        self, api: AsyncClient, account: dict[str, Any]
    ) -> None:
        # Reuse detection (docs/modules/01-authentication.md §4, rule 7).
        tokens = await self._login(api, account["email"])
        await api.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

        replay = await api.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )

        assert replay.status_code == 401

    async def test_an_unknown_refresh_token_is_rejected(self, api: AsyncClient) -> None:
        response = await api.post(
            "/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"}
        )

        assert response.status_code == 401
