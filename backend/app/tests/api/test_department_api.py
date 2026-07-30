"""API tests for the department endpoints.

Real app, real service, real repository, real database — only the HTTP
transport is in-process (``docs/11-TESTING_STRATEGY.md`` §2.3). Repositories are
deliberately not mocked: mocking them here would hide exactly the regressions
these tests exist to catch.

Per ``docs/06-API_STANDARDS.md`` §24 every endpoint gets a happy path, a
missing-auth case, a wrong-permission case, a not-found case where applicable,
and a validation-failure case. There is also a cross-tenant test per endpoint,
because tenant isolation is the one bug class that would be catastrophic and
silent.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.dependencies.db import get_db_session
from app.core.security import create_access_token
from app.main import create_app
from app.tests.conftest import grant_permissions
from app.tests.factories import build_department_payload

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.database

ALL_DEPARTMENT_PERMISSIONS = [
    "department.read",
    "department.create",
    "department.update",
    "department.delete",
]


async def _make_user(
    session: AsyncSession,
    hospital_id: uuid.UUID,
    permissions: list[str],
) -> uuid.UUID:
    """Create an active user in ``hospital_id`` holding ``permissions``."""
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        hospital_id=hospital_id,
        email=f"dept-api-{uuid.uuid4().hex[:12]}@hospital.test",
        password_hash="test-placeholder-not-a-hash",
        first_name="Api",
        last_name="Tester",
    )
    session.add(user)
    await session.flush()
    await grant_permissions(session, hospital_id=hospital_id, user_id=user.id, codes=permissions)
    return user.id


def _auth_header(user_id: uuid.UUID, hospital_id: uuid.UUID | None) -> dict[str, str]:
    """Mint a Bearer header for a user."""
    token = create_access_token(user_id=user_id, hospital_id=hospital_id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def api(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """An HTTP client whose requests share the test's rolled-back session.

    ``get_db_session`` is overridden so the app, the service, and the test all
    see the same transaction. Without this the app would open its own session
    against the real database and the test's rows would be invisible to it.
    """
    application: FastAPI = create_app()

    async def _session_override() -> AsyncGenerator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_db_session] = _session_override

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def full_access(db_session: AsyncSession, hospital_id: uuid.UUID) -> dict[str, str]:
    """Auth header for a user holding every department permission."""
    user_id = await _make_user(db_session, hospital_id, ALL_DEPARTMENT_PERMISSIONS)
    return _auth_header(user_id, hospital_id)


@pytest_asyncio.fixture
async def read_only(db_session: AsyncSession, hospital_id: uuid.UUID) -> dict[str, str]:
    """Auth header for a user holding only ``department.read``."""
    user_id = await _make_user(db_session, hospital_id, ["department.read"])
    return _auth_header(user_id, hospital_id)


@pytest_asyncio.fixture
async def other_tenant(db_session: AsyncSession, other_hospital_id: uuid.UUID) -> dict[str, str]:
    """Auth header for a fully-permissioned user in a *different* hospital."""
    user_id = await _make_user(db_session, other_hospital_id, ALL_DEPARTMENT_PERMISSIONS)
    return _auth_header(user_id, other_hospital_id)


async def _create(api: AsyncClient, headers: dict[str, str], **overrides: Any) -> dict[str, Any]:
    """Create a department through the API and return the response data block."""
    response = await api.post(
        "/api/v1/departments", json=build_department_payload(**overrides), headers=headers
    )
    assert response.status_code == 201, response.text
    return dict(response.json()["data"])


class TestCreateDepartment:
    """``POST /api/v1/departments``."""

    async def test_create_returns_201(self, api: AsyncClient, full_access: dict[str, str]) -> None:
        response = await api.post(
            "/api/v1/departments", json=build_department_payload(), headers=full_access
        )

        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["data"]["code"] == "CARD"
        assert body["data"]["name"] == "Cardiology"
        assert body["data"]["status"] == "active"

    async def test_create_uppercases_the_code(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        data = await _create(api, full_access, code="ortho", name="Orthopaedics")
        assert data["code"] == "ORTHO"

    async def test_create_without_a_token_returns_401(self, api: AsyncClient) -> None:
        response = await api.post("/api/v1/departments", json=build_department_payload())
        assert response.status_code == 401

    async def test_create_without_the_create_permission_returns_403(
        self, api: AsyncClient, read_only: dict[str, str]
    ) -> None:
        response = await api.post(
            "/api/v1/departments", json=build_department_payload(), headers=read_only
        )
        assert response.status_code == 403

    async def test_create_with_an_invalid_code_returns_422(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        response = await api.post(
            "/api/v1/departments",
            json=build_department_payload(code="bad code"),
            headers=full_access,
        )
        assert response.status_code == 422

    async def test_create_rejects_a_client_supplied_hospital_id(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        # Tenancy comes from the token. Accepting it from the body would let a
        # caller plant a department in someone else's hospital.
        response = await api.post(
            "/api/v1/departments",
            json=build_department_payload(hospital_id=str(uuid.uuid4())),
            headers=full_access,
        )
        assert response.status_code == 422

    async def test_duplicate_code_returns_409(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        await _create(api, full_access, code="CARD", name="Cardiology")

        response = await api.post(
            "/api/v1/departments",
            json=build_department_payload(code="CARD", name="Cardiac Sciences"),
            headers=full_access,
        )

        assert response.status_code == 409
        assert response.json()["error_code"] == "RESOURCE_CONFLICT"

    async def test_duplicate_name_returns_409_case_insensitively(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        await _create(api, full_access, code="CARD", name="Cardiology")

        response = await api.post(
            "/api/v1/departments",
            json=build_department_payload(code="CARD2", name="cardiology"),
            headers=full_access,
        )

        assert response.status_code == 409

    async def test_same_code_allowed_in_a_different_hospital(
        self, api: AsyncClient, full_access: dict[str, str], other_tenant: dict[str, str]
    ) -> None:
        await _create(api, full_access, code="CARD", name="Cardiology")
        # Uniqueness is per tenant, so the other hospital may reuse the code.
        await _create(api, other_tenant, code="CARD", name="Cardiology")


class TestListDepartments:
    """``GET /api/v1/departments``."""

    async def test_list_returns_pagination_metadata(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        await _create(api, full_access, code="CARD", name="Cardiology")
        await _create(api, full_access, code="ORTH", name="Orthopaedics")

        response = await api.get("/api/v1/departments", headers=full_access)

        assert response.status_code == 200
        body = response.json()
        assert [d["name"] for d in body["data"]] == ["Cardiology", "Orthopaedics"]
        assert body["metadata"]["pagination"]["total_records"] == 2
        assert body["metadata"]["pagination"]["total_pages"] == 1

    async def test_list_requires_a_token(self, api: AsyncClient) -> None:
        response = await api.get("/api/v1/departments")
        assert response.status_code == 401

    async def test_read_only_user_can_list(
        self, api: AsyncClient, full_access: dict[str, str], read_only: dict[str, str]
    ) -> None:
        await _create(api, full_access, code="CARD", name="Cardiology")
        response = await api.get("/api/v1/departments", headers=read_only)
        assert response.status_code == 200

    async def test_search_by_name_prefix(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        await _create(api, full_access, code="CARD", name="Cardiology")
        await _create(api, full_access, code="ORTH", name="Orthopaedics")

        response = await api.get("/api/v1/departments", params={"q": "cardi"}, headers=full_access)

        assert response.status_code == 200
        assert [d["code"] for d in response.json()["data"]] == ["CARD"]

    async def test_list_excludes_deactivated_by_default(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        kept = await _create(api, full_access, code="KEEP", name="Kept")
        dropped = await _create(api, full_access, code="DROP", name="Dropped")
        await api.delete(f"/api/v1/departments/{dropped['id']}", headers=full_access)

        response = await api.get("/api/v1/departments", headers=full_access)
        assert [d["id"] for d in response.json()["data"]] == [kept["id"]]

        with_inactive = await api.get(
            "/api/v1/departments", params={"include_inactive": True}, headers=full_access
        )
        assert len(with_inactive.json()["data"]) == 2

    async def test_list_does_not_leak_another_tenant(
        self, api: AsyncClient, full_access: dict[str, str], other_tenant: dict[str, str]
    ) -> None:
        await _create(api, full_access, code="MINE", name="Mine")

        response = await api.get("/api/v1/departments", headers=other_tenant)

        assert response.status_code == 200
        assert response.json()["data"] == []


class TestGetDepartment:
    """``GET /api/v1/departments/{id}``."""

    async def test_get_returns_the_record(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        created = await _create(api, full_access)

        response = await api.get(f"/api/v1/departments/{created['id']}", headers=full_access)

        assert response.status_code == 200
        assert response.json()["data"]["id"] == created["id"]

    async def test_get_unknown_id_returns_404(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        response = await api.get(f"/api/v1/departments/{uuid.uuid4()}", headers=full_access)
        assert response.status_code == 404

    async def test_get_requires_a_token(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        created = await _create(api, full_access)
        response = await api.get(f"/api/v1/departments/{created['id']}")
        assert response.status_code == 401

    async def test_get_across_tenants_returns_404_not_403(
        self, api: AsyncClient, full_access: dict[str, str], other_tenant: dict[str, str]
    ) -> None:
        # 404 rather than 403 on purpose: a 403 would confirm the record exists
        # in some other hospital.
        created = await _create(api, full_access)

        response = await api.get(f"/api/v1/departments/{created['id']}", headers=other_tenant)

        assert response.status_code == 404


class TestUpdateDepartment:
    """``PATCH /api/v1/departments/{id}``."""

    async def test_patch_applies_only_sent_fields(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        created = await _create(api, full_access)

        response = await api.patch(
            f"/api/v1/departments/{created['id']}",
            json={"location": "Block C"},
            headers=full_access,
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["location"] == "Block C"
        assert data["name"] == created["name"]
        assert data["code"] == created["code"]

    async def test_patch_without_the_update_permission_returns_403(
        self, api: AsyncClient, full_access: dict[str, str], read_only: dict[str, str]
    ) -> None:
        created = await _create(api, full_access)

        response = await api.patch(
            f"/api/v1/departments/{created['id']}",
            json={"location": "Block C"},
            headers=read_only,
        )

        assert response.status_code == 403

    async def test_empty_patch_returns_422(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        created = await _create(api, full_access)

        response = await api.patch(
            f"/api/v1/departments/{created['id']}", json={}, headers=full_access
        )

        assert response.status_code == 422

    async def test_patch_null_on_required_field_returns_422(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        created = await _create(api, full_access)

        response = await api.patch(
            f"/api/v1/departments/{created['id']}", json={"name": None}, headers=full_access
        )

        assert response.status_code == 422

    async def test_patch_to_a_taken_code_returns_409(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        await _create(api, full_access, code="CARD", name="Cardiology")
        other = await _create(api, full_access, code="ORTH", name="Orthopaedics")

        response = await api.patch(
            f"/api/v1/departments/{other['id']}", json={"code": "CARD"}, headers=full_access
        )

        assert response.status_code == 409

    async def test_patch_unknown_id_returns_404(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        response = await api.patch(
            f"/api/v1/departments/{uuid.uuid4()}",
            json={"location": "Block C"},
            headers=full_access,
        )
        assert response.status_code == 404

    async def test_patch_across_tenants_returns_404(
        self, api: AsyncClient, full_access: dict[str, str], other_tenant: dict[str, str]
    ) -> None:
        created = await _create(api, full_access)

        response = await api.patch(
            f"/api/v1/departments/{created['id']}",
            json={"location": "Hijacked"},
            headers=other_tenant,
        )

        assert response.status_code == 404


class TestDeactivateDepartment:
    """``DELETE /api/v1/departments/{id}``."""

    async def test_delete_soft_deletes_and_returns_the_record(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        created = await _create(api, full_access)

        response = await api.delete(f"/api/v1/departments/{created['id']}", headers=full_access)

        assert response.status_code == 200
        assert response.json()["data"]["status"] == "inactive"

    async def test_delete_is_not_a_hard_delete(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        # The row must survive: doctors and appointments keep referencing it.
        created = await _create(api, full_access)
        await api.delete(f"/api/v1/departments/{created['id']}", headers=full_access)

        response = await api.get(
            f"/api/v1/departments/{created['id']}",
            params={"include_inactive": True},
            headers=full_access,
        )

        assert response.status_code == 200
        assert response.json()["data"]["id"] == created["id"]

    async def test_delete_twice_returns_400(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        created = await _create(api, full_access)
        await api.delete(f"/api/v1/departments/{created['id']}", headers=full_access)

        response = await api.delete(f"/api/v1/departments/{created['id']}", headers=full_access)

        assert response.status_code == 400

    async def test_delete_without_the_delete_permission_returns_403(
        self, api: AsyncClient, full_access: dict[str, str], read_only: dict[str, str]
    ) -> None:
        created = await _create(api, full_access)

        response = await api.delete(f"/api/v1/departments/{created['id']}", headers=read_only)

        assert response.status_code == 403

    async def test_delete_unknown_id_returns_404(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        response = await api.delete(f"/api/v1/departments/{uuid.uuid4()}", headers=full_access)
        assert response.status_code == 404

    async def test_delete_across_tenants_returns_404(
        self, api: AsyncClient, full_access: dict[str, str], other_tenant: dict[str, str]
    ) -> None:
        created = await _create(api, full_access)

        response = await api.delete(f"/api/v1/departments/{created['id']}", headers=other_tenant)

        assert response.status_code == 404

    async def test_delete_succeeds_while_no_doctors_are_assigned(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        """The rule 13 guard's clear branch, through the real HTTP stack.

        The wired usage source reports no assignments today, so deactivation
        goes through. When Doctor Management swaps in the real source, this test
        documents the behaviour for an unassigned department and should keep
        passing unchanged.
        """
        created = await _create(api, full_access)

        response = await api.delete(f"/api/v1/departments/{created['id']}", headers=full_access)

        assert response.status_code == 200

    async def test_delete_blocked_when_doctors_are_assigned(
        self, api: AsyncClient, full_access: dict[str, str], db_session: AsyncSession
    ) -> None:
        """The rule 13 guard's blocking branch, through the real HTTP stack.

        The usage source is overridden to report assignments — which is exactly
        what the Doctor Management adapter will do for a department that has
        them. Asserting it here means the Doctors PR swaps one provider and does
        not have to write this test.
        """
        from app.api.dependencies.services import get_department_usage_source

        created = await _create(api, full_access)

        class BusyUsageSource:
            async def active_doctor_count(
                self, hospital_id: uuid.UUID, department_id: uuid.UUID
            ) -> int:
                return 2

        # Reach the same app instance the `api` fixture is driving.
        api._transport.app.dependency_overrides[  # type: ignore[attr-defined] # noqa: SLF001
            get_department_usage_source
        ] = BusyUsageSource

        response = await api.delete(f"/api/v1/departments/{created['id']}", headers=full_access)

        assert response.status_code == 409
        body = response.json()
        assert body["error_code"] == "RESOURCE_CONFLICT"
        assert "doctors are assigned" in body["message"]

        # And the department is still active — a refused delete changes nothing.
        still_there = await api.get(f"/api/v1/departments/{created['id']}", headers=full_access)
        assert still_there.json()["data"]["status"] == "active"


class TestActivateDepartment:
    """``POST /api/v1/departments/{id}/activate``."""

    async def test_activate_restores_a_deactivated_department(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        created = await _create(api, full_access)
        await api.delete(f"/api/v1/departments/{created['id']}", headers=full_access)

        response = await api.post(
            f"/api/v1/departments/{created['id']}/activate", headers=full_access
        )

        assert response.status_code == 200
        assert response.json()["data"]["status"] == "active"

        listed = await api.get("/api/v1/departments", headers=full_access)
        assert [d["id"] for d in listed.json()["data"]] == [created["id"]]

    async def test_activate_an_active_department_returns_400(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        created = await _create(api, full_access)

        response = await api.post(
            f"/api/v1/departments/{created['id']}/activate", headers=full_access
        )

        assert response.status_code == 400

    async def test_activate_without_the_update_permission_returns_403(
        self, api: AsyncClient, full_access: dict[str, str], read_only: dict[str, str]
    ) -> None:
        created = await _create(api, full_access)
        await api.delete(f"/api/v1/departments/{created['id']}", headers=full_access)

        response = await api.post(
            f"/api/v1/departments/{created['id']}/activate", headers=read_only
        )

        assert response.status_code == 403

    async def test_activate_unknown_id_returns_404(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        response = await api.post(
            f"/api/v1/departments/{uuid.uuid4()}/activate", headers=full_access
        )
        assert response.status_code == 404

    async def test_activate_across_tenants_returns_404(
        self, api: AsyncClient, full_access: dict[str, str], other_tenant: dict[str, str]
    ) -> None:
        created = await _create(api, full_access)
        await api.delete(f"/api/v1/departments/{created['id']}", headers=full_access)

        response = await api.post(
            f"/api/v1/departments/{created['id']}/activate", headers=other_tenant
        )

        assert response.status_code == 404
