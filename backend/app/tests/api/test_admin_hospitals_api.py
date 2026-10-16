# ruff: noqa: F811 — the `api` fixture imported from the settings tests is requested by name
"""API tests for provisioning hospitals (``docs/modules/14-hospital-settings.md`` §5, §9, §11).

Real app, service, repositories and database. Who may provision, that it is
atomic, and that no credential ever comes back.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.models.audit_log import AuditLog
from app.models.hospital import Hospital
from app.models.permission import Permission
from app.models.role import Role, RolePermission
from app.models.user import User, UserStatus
from app.tests.api.test_hospital_settings_api import _auth_header, _make_user, api  # noqa: F401

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.database

URL = "/api/v1/admin/hospitals"

#: What the seeded Hospital Admin role carries, as far as these tests need.
ADMIN_ROLE_CODES = ["settings.read", "settings.update", "user.read", "user.create"]


@pytest_asyncio.fixture
async def hospital_admin_role(db_session: AsyncSession) -> Role:
    """The seeded system role a new hospital's first administrator gets."""
    existing = (
        (
            await db_session.execute(
                select(Role).where(Role.name == "Hospital Admin", Role.hospital_id.is_(None))
            )
        )
        .unique()
        .scalar_one_or_none()
    )
    if existing is not None:
        return existing
    # Resolve every permission first: a query after the role's graph exists
    # would autoflush it half-built.
    permissions = []
    for code in ADMIN_ROLE_CODES:
        found = (
            (await db_session.execute(select(Permission).where(Permission.code == code)))
            .unique()
            .scalar_one_or_none()
        )
        if found is None:
            found = Permission(
                id=uuid.uuid4(), code=code, module=code.split(".")[0], description=code
            )
            db_session.add(found)
            await db_session.flush()
        permissions.append(found)
    role = Role(
        id=uuid.uuid4(), name="Hospital Admin", description="test", is_system=True, hospital_id=None
    )
    role.role_permissions = [RolePermission(permission=permission) for permission in permissions]
    db_session.add(role)
    await db_session.flush()
    return role


@pytest_asyncio.fixture
async def platform_admin(db_session: AsyncSession, hospital_id: uuid.UUID) -> dict[str, str]:
    """A Super Admin, as seeded: in a hospital, holding the platform code and every
    code the Hospital Admin role carries (so the invite's escalation check passes)."""
    user_id = await _make_user(
        db_session, hospital_id, [*ADMIN_ROLE_CODES, "platform.hospital.provision"]
    )
    return _auth_header(user_id, hospital_id)


def _body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "City Care Clinic",
        "slug": f"city-care-{uuid.uuid4().hex[:6]}",
        "email": "contact@citycare.example",
        "address": {
            "line1": "4 Lake Road",
            "city": "Hyderabad",
            "state": "Telangana",
            "postal_code": "500034",
        },
        "admin": {
            "email": f"owner-{uuid.uuid4().hex[:8]}@citycare.example",
            "first_name": "Asha",
            "last_name": "Rao",
        },
    }
    body.update(overrides)
    return body


async def _count(session: AsyncSession, model: Any, *where: Any) -> int:
    return int(
        (await session.execute(select(func.count()).select_from(model).where(*where))).scalar_one()
    )


class TestProvision:
    async def test_creates_the_hospital_and_invites_its_admin_in_one_go(
        self,
        api: AsyncClient,
        platform_admin: dict[str, str],
        hospital_admin_role: Role,
        db_session: AsyncSession,
    ) -> None:
        body = _body()

        response = await api.post(URL, json=body, headers=platform_admin)

        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert set(data) == {
            "hospital_id",
            "name",
            "slug",
            "admin_user_id",
            "admin_email",
            "invitation",
        }
        # No activation link or token, under any name.
        assert "token" not in response.text and "reset-password" not in response.text
        assert data["invitation"] in {"queued", "unavailable"}

        hospital = await db_session.get(Hospital, uuid.UUID(data["hospital_id"]))
        assert hospital is not None
        assert (hospital.slug, hospital.timezone, hospital.currency, hospital.is_active) == (
            body["slug"],
            "Asia/Kolkata",
            "INR",
            True,
        )
        assert hospital.address["city"] == "Hyderabad"

        admin = await db_session.get(User, uuid.UUID(data["admin_user_id"]))
        assert admin is not None
        assert admin.hospital_id == hospital.id
        assert admin.status == UserStatus.INVITED
        assert [ur.role_id for ur in admin.user_roles] == [hospital_admin_role.id]

        provisioned = await _count(
            db_session,
            AuditLog,
            AuditLog.action == "hospital.provisioned",
            AuditLog.hospital_id == hospital.id,
        )
        assert provisioned == 1

    async def test_a_taken_slug_is_a_conflict(
        self, api: AsyncClient, platform_admin: dict[str, str], hospital_admin_role: Role
    ) -> None:
        body = _body()
        assert (await api.post(URL, json=body, headers=platform_admin)).status_code == 201

        again = await api.post(URL, json=_body(slug=body["slug"]), headers=platform_admin)

        assert again.status_code == 409

    async def test_nothing_is_created_when_the_admin_email_is_taken(
        self,
        api: AsyncClient,
        platform_admin: dict[str, str],
        hospital_admin_role: Role,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        taken = (await db_session.get(User, await _make_user(db_session, hospital_id, []))).email  # type: ignore[union-attr]
        body = _body(admin={"email": taken, "first_name": "A", "last_name": "B"})

        response = await api.post(URL, json=body, headers=platform_admin)

        assert response.status_code == 409
        await db_session.rollback()
        assert await _count(db_session, Hospital, Hospital.slug == body["slug"]) == 0

    @pytest.mark.parametrize(
        "change",
        [
            {"slug": "AB"},
            {"slug": "Has Spaces"},
            {"slug": "admin"},
            {"slug": "-leading"},
            {"timezone": "Mars/Olympus"},
            {"currency": "rupees"},
            {"address": {"street": "old key"}},
            {"admin": {"email": "not-an-email", "first_name": "A", "last_name": "B"}},
            {"is_active": False},
        ],
    )
    async def test_invalid_requests_are_refused(
        self,
        api: AsyncClient,
        platform_admin: dict[str, str],
        hospital_admin_role: Role,
        change: dict[str, Any],
    ) -> None:
        response = await api.post(URL, json=_body(**change), headers=platform_admin)

        assert response.status_code == 422


class TestWhoMayProvision:
    async def test_a_hospital_admin_may_not(
        self,
        api: AsyncClient,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        hospital_admin_role: Role,
    ) -> None:
        admin = _auth_header(
            await _make_user(db_session, hospital_id, [*ADMIN_ROLE_CODES, "user.update"]),
            hospital_id,
        )

        response = await api.post(URL, json=_body(), headers=admin)

        assert response.status_code == 403

    async def test_no_token_is_401(self, api: AsyncClient) -> None:
        assert (await api.post(URL, json=_body())).status_code == 401
