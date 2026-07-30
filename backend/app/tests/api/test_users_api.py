"""API tests for the user management endpoints.

Focused on the two contract failures that unit tests could not see: writes that
reported success without persisting, and a list response whose shape did not
match ``docs/06-API_STANDARDS.md`` §5.2.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api.dependencies.db import get_db_session
from app.core.security import create_access_token, hash_password
from app.main import create_app
from app.models.user import User
from app.tests.conftest import grant_permissions

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.database

USER_PERMISSIONS = ["user.read", "user.create", "user.update", "user.deactivate"]


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
async def admin(db_session: AsyncSession, hospital_id: uuid.UUID) -> dict[str, Any]:
    """An admin holding the user-management permissions."""
    user = User(
        id=uuid.uuid4(),
        hospital_id=hospital_id,
        email=f"admin-{uuid.uuid4().hex[:12]}@hospital.example",
        password_hash=hash_password("Str0ng!Passw0rd123"),
        first_name="Admin",
        last_name="User",
    )
    db_session.add(user)
    await db_session.flush()
    await grant_permissions(
        db_session, hospital_id=hospital_id, user_id=user.id, codes=USER_PERMISSIONS
    )
    token = create_access_token(user_id=user.id, hospital_id=hospital_id)
    return {"id": user.id, "headers": {"Authorization": f"Bearer {token}"}}


class TestInviteUserPersistence:
    """``POST /api/v1/users``."""

    async def test_inviting_a_user_actually_persists_the_row(
        self, api: AsyncClient, db_session: AsyncSession, admin: dict[str, Any]
    ) -> None:
        # Regression: this returned 201 Created with a generated id for a user
        # that was never written, because no service in the module committed.
        email = f"invitee-{uuid.uuid4().hex[:12]}@hospital.example"

        response = await api.post(
            "/api/v1/users",
            json={"email": email, "first_name": "New", "last_name": "Nurse"},
            headers=admin["headers"],
        )

        assert response.status_code == 201, response.text
        stored = await db_session.execute(
            select(func.count()).select_from(User).where(User.email == email)
        )
        assert stored.scalar_one() == 1, "API reported success but no row was written"

    async def test_the_returned_id_refers_to_a_real_row(
        self, api: AsyncClient, db_session: AsyncSession, admin: dict[str, Any]
    ) -> None:
        response = await api.post(
            "/api/v1/users",
            json={
                "email": f"invitee-{uuid.uuid4().hex[:12]}@hospital.example",
                "first_name": "New",
                "last_name": "Nurse",
            },
            headers=admin["headers"],
        )

        new_id = uuid.UUID(response.json()["data"]["id"])
        found = await db_session.execute(select(User).where(User.id == new_id))
        assert found.unique().scalar_one_or_none() is not None

    async def test_inviting_without_permission_returns_403(
        self, api: AsyncClient, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        plain = User(
            id=uuid.uuid4(),
            hospital_id=hospital_id,
            email=f"plain-{uuid.uuid4().hex[:12]}@hospital.example",
            password_hash=hash_password("Str0ng!Passw0rd123"),
            first_name="Plain",
            last_name="User",
        )
        db_session.add(plain)
        await db_session.flush()
        await grant_permissions(
            db_session, hospital_id=hospital_id, user_id=plain.id, codes=["user.read"]
        )
        token = create_access_token(user_id=plain.id, hospital_id=hospital_id)

        response = await api.post(
            "/api/v1/users",
            json={
                "email": "x@hospital.example",
                "first_name": "X",
                "last_name": "Y",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403

    async def test_inviting_without_a_token_returns_401(self, api: AsyncClient) -> None:
        response = await api.post(
            "/api/v1/users",
            json={"email": "x@hospital.example", "first_name": "X", "last_name": "Y"},
        )

        assert response.status_code == 401


class TestListUsersEnvelope:
    """``GET /api/v1/users`` — ``docs/06-API_STANDARDS.md`` §5.2."""

    async def test_data_is_the_array_of_records(
        self, api: AsyncClient, admin: dict[str, Any]
    ) -> None:
        # Regression: `data` was the whole result dict, so the records were
        # nested under data.items and the counts appeared twice.
        response = await api.get("/api/v1/users", headers=admin["headers"])

        body = response.json()
        assert response.status_code == 200
        assert isinstance(body["data"], list), "data must be the array of records"

    async def test_pagination_lives_in_metadata(
        self, api: AsyncClient, admin: dict[str, Any]
    ) -> None:
        response = await api.get("/api/v1/users", headers=admin["headers"])

        pagination = response.json()["metadata"]["pagination"]
        assert set(pagination) == {"page", "page_size", "total_records", "total_pages"}
        assert pagination["total_records"] >= 1

    async def test_unauthenticated_errors_use_the_standard_envelope(self, api: AsyncClient) -> None:
        response = await api.get("/api/v1/users")

        body = response.json()
        assert response.status_code == 401
        assert body["success"] is False
        assert body["error_code"] == "AUTHENTICATION_REQUIRED"
        assert "detail" not in body
