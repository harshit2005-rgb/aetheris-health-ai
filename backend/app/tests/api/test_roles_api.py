"""API tests for the Roles & Permissions endpoints.

``docs/06-API_STANDARDS.md`` §24: every endpoint has a happy-path test and a
permission-denied case. ``docs/modules/02-user-management.md`` §9: roles and
the permissions catalog are read-only in the MVP.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.dependencies.db import get_db_session
from app.core.security import create_access_token, hash_password
from app.main import create_app
from app.models.permission import Permission
from app.models.role import Role, RolePermission
from app.models.user import User
from app.tests.conftest import grant_permissions

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.database


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
async def viewer(db_session: AsyncSession, hospital_id: uuid.UUID) -> dict[str, Any]:
    """A user holding ``role.read`` — enough to view roles and permissions."""
    user = User(
        id=uuid.uuid4(),
        hospital_id=hospital_id,
        email=f"viewer-{uuid.uuid4().hex[:12]}@hospital.example",
        password_hash=hash_password("Str0ng!Passw0rd123"),
        first_name="Role",
        last_name="Viewer",
    )
    db_session.add(user)
    await db_session.flush()
    await grant_permissions(
        db_session, hospital_id=hospital_id, user_id=user.id, codes=["role.read"]
    )
    token = create_access_token(user_id=user.id, hospital_id=hospital_id)
    return {"id": user.id, "headers": {"Authorization": f"Bearer {token}"}}


async def _seed_role_with_permissions(
    db_session: AsyncSession,
    hospital_id: uuid.UUID,
    *,
    name: str = "Custom Role",
    is_system: bool = False,
) -> Role:
    """Insert a role with one permission row attached."""
    role = Role(
        id=uuid.uuid4(),
        hospital_id=None if is_system else hospital_id,
        name=name,
        is_system=is_system,
    )
    db_session.add(role)
    await db_session.flush()

    permission = await db_session.execute(
        select(Permission).where(Permission.code == "patient.read")
    )
    perm = permission.unique().scalar_one_or_none()
    if perm is None:
        perm = Permission(
            id=uuid.uuid4(),
            code="patient.read",
            module="patient",
            description="View patient records.",
        )
        db_session.add(perm)
        await db_session.flush()

    db_session.add(RolePermission(id=uuid.uuid4(), role_id=role.id, permission_id=perm.id))
    await db_session.flush()
    return role


class TestListRoles:
    """``GET /api/v1/roles``."""

    async def test_lists_system_and_own_roles(
        self,
        api: AsyncClient,
        viewer: dict[str, Any],
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        await _seed_role_with_permissions(db_session, hospital_id, name="Receptionist")
        await _seed_role_with_permissions(
            db_session, hospital_id, name="Super Admin", is_system=True
        )

        response = await api.get("/api/v1/roles", headers=viewer["headers"])

        assert response.status_code == 200, response.text
        body = response.json()
        names = {item["name"] for item in body["data"]}
        assert {"Receptionist", "Super Admin"} <= names
        assert body["metadata"]["pagination"]["total_records"] >= 2

    async def test_list_requires_role_read_permission(
        self, api: AsyncClient, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        """A user without ``role.read`` gets 403."""
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

        response = await api.get("/api/v1/roles", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 403

    async def test_list_requires_authentication(self, api: AsyncClient) -> None:
        response = await api.get("/api/v1/roles")

        assert response.status_code == 401


class TestGetRole:
    """``GET /api/v1/roles/{id}``."""

    async def test_get_role_includes_permission_codes(
        self,
        api: AsyncClient,
        viewer: dict[str, Any],
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        role = await _seed_role_with_permissions(db_session, hospital_id, name="Receptionist")

        response = await api.get(f"/api/v1/roles/{role.id}", headers=viewer["headers"])

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["name"] == "Receptionist"
        assert "patient.read" in data["permission_codes"]

    async def test_get_system_role_is_visible(
        self,
        api: AsyncClient,
        viewer: dict[str, Any],
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        role = await _seed_role_with_permissions(
            db_session, hospital_id, name="Super Admin", is_system=True
        )

        response = await api.get(f"/api/v1/roles/{role.id}", headers=viewer["headers"])

        assert response.status_code == 200
        assert response.json()["data"]["is_system"] is True

    async def test_get_unknown_role_returns_404(
        self, api: AsyncClient, viewer: dict[str, Any]
    ) -> None:
        response = await api.get(f"/api/v1/roles/{uuid.uuid4()}", headers=viewer["headers"])

        assert response.status_code == 404
        assert response.json()["error_code"] == "RESOURCE_NOT_FOUND"

    async def test_get_another_tenants_role_returns_404(
        self,
        api: AsyncClient,
        viewer: dict[str, Any],
        db_session: AsyncSession,
        other_hospital_id: uuid.UUID,
    ) -> None:
        """A role in another hospital is indistinguishable from a miss."""
        role = await _seed_role_with_permissions(db_session, other_hospital_id, name="Theirs")

        response = await api.get(f"/api/v1/roles/{role.id}", headers=viewer["headers"])

        assert response.status_code == 404


class TestListPermissions:
    """``GET /api/v1/permissions``."""

    async def test_lists_the_catalog(self, api: AsyncClient, viewer: dict[str, Any]) -> None:
        response = await api.get("/api/v1/permissions", headers=viewer["headers"])

        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body["data"], list)
        assert body["metadata"]["pagination"]["total_records"] >= 1

    async def test_filters_by_module(
        self, api: AsyncClient, db_session: AsyncSession, viewer: dict[str, Any]
    ) -> None:
        # Each test rolls back, so the seeded catalog is not present — the
        # rows the filter is asserted against have to be created here.
        for code, module in (
            ("patient.read", "patient"),
            ("patient.create", "patient"),
            ("billing.read", "billing"),
        ):
            db_session.add(Permission(id=uuid.uuid4(), code=code, module=module, description=code))
        await db_session.flush()

        response = await api.get("/api/v1/permissions?module=patient", headers=viewer["headers"])

        assert response.status_code == 200, response.text
        codes = {item["code"] for item in response.json()["data"]}
        assert codes == {"patient.read", "patient.create"}

    async def test_list_requires_role_read_permission(
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

        response = await api.get(
            "/api/v1/permissions", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
