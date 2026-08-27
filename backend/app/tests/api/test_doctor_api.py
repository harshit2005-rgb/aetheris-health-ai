"""API tests for the doctor endpoints.

Real app, real service, real repository, real database — only the HTTP
transport is in-process (``docs/11-TESTING_STRATEGY.md`` §2.3).

Per ``docs/06-API_STANDARDS.md`` §24 every endpoint gets a happy path, a
missing-auth case, a wrong-permission case, a not-found case where applicable,
and a validation-failure case, plus a cross-tenant test because tenant
isolation is the one bug class that would be catastrophic and silent.

The finer-grained permission codes matter here: module spec §3 lets a doctor
manage their own availability and leave without holding ``doctor.update``, so
those are exercised separately.
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
from app.tests.factories import (
    build_availability_payload,
    build_doctor_payload,
    build_leave_payload,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.database

ALL_DOCTOR_PERMISSIONS = [
    "doctor.read",
    "doctor.create",
    "doctor.update",
    "doctor.delete",
    "doctor.availability.read",
    "doctor.availability.update",
    "doctor.leave.create",
    "doctor.leave.delete",
]


async def _make_user(
    session: AsyncSession,
    hospital_id: uuid.UUID,
    permissions: list[str],
    *,
    first: str = "Api",
    last: str = "Tester",
) -> uuid.UUID:
    """Create an active user in ``hospital_id`` holding ``permissions``."""
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        hospital_id=hospital_id,
        email=f"doc-api-{uuid.uuid4().hex[:12]}@hospital.test",
        password_hash="test-placeholder-not-a-hash",
        first_name=first,
        last_name=last,
    )
    session.add(user)
    await session.flush()
    if permissions:
        await grant_permissions(
            session, hospital_id=hospital_id, user_id=user.id, codes=permissions
        )
    return user.id


def _auth_header(user_id: uuid.UUID, hospital_id: uuid.UUID | None) -> dict[str, str]:
    """Mint a Bearer header for a user."""
    return {
        "Authorization": f"Bearer {create_access_token(user_id=user_id, hospital_id=hospital_id)}"
    }


@pytest_asyncio.fixture
async def api(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """An HTTP client whose requests share the test's rolled-back session."""
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
    """Auth header for a user holding every doctor permission."""
    return _auth_header(
        await _make_user(db_session, hospital_id, ALL_DOCTOR_PERMISSIONS), hospital_id
    )


@pytest_asyncio.fixture
async def read_only(db_session: AsyncSession, hospital_id: uuid.UUID) -> dict[str, str]:
    """Auth header for a user holding only ``doctor.read``."""
    return _auth_header(await _make_user(db_session, hospital_id, ["doctor.read"]), hospital_id)


@pytest_asyncio.fixture
async def other_tenant(db_session: AsyncSession, other_hospital_id: uuid.UUID) -> dict[str, str]:
    """Auth header for a fully-permissioned user in a *different* hospital."""
    return _auth_header(
        await _make_user(db_session, other_hospital_id, ALL_DOCTOR_PERMISSIONS),
        other_hospital_id,
    )


@pytest_asyncio.fixture
async def doctor_user(db_session: AsyncSession, hospital_id: uuid.UUID) -> uuid.UUID:
    """A user with no permissions, to attach a doctor profile to."""
    return await _make_user(db_session, hospital_id, [], first="Asha", last="Menon")


async def _create_doctor(
    api: AsyncClient, headers: dict[str, str], user_id: uuid.UUID, **overrides: Any
) -> dict[str, Any]:
    """Onboard a doctor through the API and return the data block."""
    payload = build_doctor_payload(user_id=str(user_id), **overrides)
    response = await api.post("/api/v1/doctors", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return dict(response.json()["data"])


class TestCreateDoctor:
    """``POST /api/v1/doctors``."""

    async def test_create_returns_201(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        data = await _create_doctor(api, full_access, doctor_user)
        assert data["specialization"] == "Cardiology"
        assert data["full_name"] == "Asha Menon"
        assert data["status"] == "active"

    async def test_create_without_token_returns_401(
        self, api: AsyncClient, doctor_user: uuid.UUID
    ) -> None:
        response = await api.post(
            "/api/v1/doctors", json=build_doctor_payload(user_id=str(doctor_user))
        )
        assert response.status_code == 401

    async def test_create_without_permission_returns_403(
        self, api: AsyncClient, read_only: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        response = await api.post(
            "/api/v1/doctors",
            json=build_doctor_payload(user_id=str(doctor_user)),
            headers=read_only,
        )
        assert response.status_code == 403

    async def test_create_with_invalid_fee_returns_422(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        response = await api.post(
            "/api/v1/doctors",
            json=build_doctor_payload(user_id=str(doctor_user), consultation_fee="-1"),
            headers=full_access,
        )
        assert response.status_code == 422

    async def test_second_profile_for_same_user_returns_409(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        await _create_doctor(api, full_access, doctor_user)

        response = await api.post(
            "/api/v1/doctors",
            json=build_doctor_payload(user_id=str(doctor_user)),
            headers=full_access,
        )
        assert response.status_code == 409

    async def test_create_for_user_in_another_tenant_returns_422(
        self, api: AsyncClient, other_tenant: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        """A user from another hospital is unusable, and is not confirmed to exist."""
        response = await api.post(
            "/api/v1/doctors",
            json=build_doctor_payload(user_id=str(doctor_user)),
            headers=other_tenant,
        )
        assert response.status_code == 422


class TestListDoctors:
    """``GET /api/v1/doctors``."""

    async def test_list_returns_pagination_metadata(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        await _create_doctor(api, full_access, doctor_user)

        response = await api.get("/api/v1/doctors", headers=full_access)

        assert response.status_code == 200
        body = response.json()
        assert body["metadata"]["pagination"]["total_records"] == 1

    async def test_read_only_user_can_list(
        self,
        api: AsyncClient,
        full_access: dict[str, str],
        read_only: dict[str, str],
        doctor_user: uuid.UUID,
    ) -> None:
        await _create_doctor(api, full_access, doctor_user)
        response = await api.get("/api/v1/doctors", headers=read_only)
        assert response.status_code == 200

    async def test_filter_by_specialization(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        await _create_doctor(api, full_access, doctor_user, specialization="Neurology")

        hit = await api.get(
            "/api/v1/doctors", params={"specialization": "Neurology"}, headers=full_access
        )
        miss = await api.get(
            "/api/v1/doctors", params={"specialization": "Cardiology"}, headers=full_access
        )

        assert len(hit.json()["data"]) == 1
        assert miss.json()["data"] == []

    async def test_search_by_name(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        await _create_doctor(api, full_access, doctor_user)
        response = await api.get("/api/v1/doctors", params={"q": "ash"}, headers=full_access)
        assert len(response.json()["data"]) == 1

    async def test_list_requires_token(self, api: AsyncClient) -> None:
        assert (await api.get("/api/v1/doctors")).status_code == 401

    async def test_list_does_not_leak_another_tenant(
        self,
        api: AsyncClient,
        full_access: dict[str, str],
        other_tenant: dict[str, str],
        doctor_user: uuid.UUID,
    ) -> None:
        await _create_doctor(api, full_access, doctor_user)
        response = await api.get("/api/v1/doctors", headers=other_tenant)
        assert response.json()["data"] == []


class TestGetAndUpdateDoctor:
    """``GET`` / ``PATCH`` / ``DELETE`` on a single doctor."""

    async def test_get_returns_the_record(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)
        response = await api.get(f"/api/v1/doctors/{created['id']}", headers=full_access)
        assert response.status_code == 200
        assert response.json()["data"]["id"] == created["id"]

    async def test_get_unknown_returns_404(
        self, api: AsyncClient, full_access: dict[str, str]
    ) -> None:
        response = await api.get(f"/api/v1/doctors/{uuid.uuid4()}", headers=full_access)
        assert response.status_code == 404

    async def test_get_across_tenants_returns_404(
        self,
        api: AsyncClient,
        full_access: dict[str, str],
        other_tenant: dict[str, str],
        doctor_user: uuid.UUID,
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)
        response = await api.get(f"/api/v1/doctors/{created['id']}", headers=other_tenant)
        assert response.status_code == 404

    async def test_patch_applies_only_sent_fields(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)

        response = await api.patch(
            f"/api/v1/doctors/{created['id']}",
            json={"consultation_fee": "950.00"},
            headers=full_access,
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["consultation_fee"] == "950.00"
        assert data["specialization"] == created["specialization"]

    async def test_patch_without_permission_returns_403(
        self,
        api: AsyncClient,
        full_access: dict[str, str],
        read_only: dict[str, str],
        doctor_user: uuid.UUID,
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)
        response = await api.patch(
            f"/api/v1/doctors/{created['id']}", json={"bio": "x"}, headers=read_only
        )
        assert response.status_code == 403

    async def test_patch_rejects_immutable_user_id(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)
        response = await api.patch(
            f"/api/v1/doctors/{created['id']}",
            json={"user_id": str(uuid.uuid4())},
            headers=full_access,
        )
        assert response.status_code == 422

    async def test_delete_soft_deletes(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)

        response = await api.delete(f"/api/v1/doctors/{created['id']}", headers=full_access)

        assert response.status_code == 200
        assert response.json()["data"]["status"] == "inactive"

        # The row survives — appointments and invoices reference it.
        still_there = await api.get(
            f"/api/v1/doctors/{created['id']}",
            params={"include_inactive": True},
            headers=full_access,
        )
        assert still_there.status_code == 200

    async def test_activate_restores(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)
        await api.delete(f"/api/v1/doctors/{created['id']}", headers=full_access)

        response = await api.post(f"/api/v1/doctors/{created['id']}/activate", headers=full_access)

        assert response.status_code == 200
        assert response.json()["data"]["status"] == "active"

    async def test_delete_across_tenants_returns_404(
        self,
        api: AsyncClient,
        full_access: dict[str, str],
        other_tenant: dict[str, str],
        doctor_user: uuid.UUID,
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)
        response = await api.delete(f"/api/v1/doctors/{created['id']}", headers=other_tenant)
        assert response.status_code == 404


class TestAvailability:
    """``GET`` / ``PUT /doctors/{id}/availability``."""

    async def test_put_then_get_round_trips(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)

        put = await api.put(
            f"/api/v1/doctors/{created['id']}/availability",
            json=build_availability_payload(),
            headers=full_access,
        )
        assert put.status_code == 200

        got = await api.get(f"/api/v1/doctors/{created['id']}/availability", headers=full_access)
        assert [w["day_of_week"] for w in got.json()["data"]] == [0, 2]

    async def test_put_is_a_full_replace(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        """Module spec §5.2: the payload becomes the entire schedule."""
        created = await _create_doctor(api, full_access, doctor_user)
        await api.put(
            f"/api/v1/doctors/{created['id']}/availability",
            json=build_availability_payload(),
            headers=full_access,
        )

        replaced = await api.put(
            f"/api/v1/doctors/{created['id']}/availability",
            json={
                "entries": [
                    {
                        "day_of_week": 5,
                        "start_time": "10:00:00",
                        "end_time": "11:00:00",
                        "slot_duration_minutes": 20,
                    }
                ]
            },
            headers=full_access,
        )

        assert [w["day_of_week"] for w in replaced.json()["data"]] == [5]

    async def test_put_rejects_overlapping_windows(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)

        response = await api.put(
            f"/api/v1/doctors/{created['id']}/availability",
            json={
                "entries": [
                    {"day_of_week": 0, "start_time": "09:00:00", "end_time": "12:00:00"},
                    {"day_of_week": 0, "start_time": "11:00:00", "end_time": "13:00:00"},
                ]
            },
            headers=full_access,
        )

        assert response.status_code == 422

    async def test_availability_permission_is_distinct_from_update(
        self,
        api: AsyncClient,
        full_access: dict[str, str],
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        doctor_user: uuid.UUID,
    ) -> None:
        """Module spec §3: a doctor edits their own schedule without doctor.update."""
        created = await _create_doctor(api, full_access, doctor_user)
        scheduler = _auth_header(
            await _make_user(
                db_session,
                hospital_id,
                ["doctor.read", "doctor.availability.read", "doctor.availability.update"],
            ),
            hospital_id,
        )

        allowed = await api.put(
            f"/api/v1/doctors/{created['id']}/availability",
            json=build_availability_payload(),
            headers=scheduler,
        )
        assert allowed.status_code == 200

        # ...but still cannot edit the profile itself.
        refused = await api.patch(
            f"/api/v1/doctors/{created['id']}", json={"bio": "x"}, headers=scheduler
        )
        assert refused.status_code == 403

    async def test_availability_across_tenants_returns_404(
        self,
        api: AsyncClient,
        full_access: dict[str, str],
        other_tenant: dict[str, str],
        doctor_user: uuid.UUID,
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)
        response = await api.get(
            f"/api/v1/doctors/{created['id']}/availability", headers=other_tenant
        )
        assert response.status_code == 404


class TestLeaves:
    """Leave endpoints."""

    async def test_create_and_list_leave(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)

        post = await api.post(
            f"/api/v1/doctors/{created['id']}/leaves",
            json=build_leave_payload(),
            headers=full_access,
        )
        assert post.status_code == 201

        listed = await api.get(f"/api/v1/doctors/{created['id']}/leaves", headers=full_access)
        assert [leave["reason"] for leave in listed.json()["data"]] == ["Conference"]

    async def test_overlapping_leave_returns_409(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)
        await api.post(
            f"/api/v1/doctors/{created['id']}/leaves",
            json=build_leave_payload(),
            headers=full_access,
        )

        response = await api.post(
            f"/api/v1/doctors/{created['id']}/leaves",
            json=build_leave_payload(
                starts_at="2026-08-16T00:00:00+00:00", ends_at="2026-08-20T00:00:00+00:00"
            ),
            headers=full_access,
        )

        assert response.status_code == 409

    async def test_naive_timestamp_returns_422(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        """A timestamp with no offset is ambiguous and must be refused."""
        created = await _create_doctor(api, full_access, doctor_user)

        response = await api.post(
            f"/api/v1/doctors/{created['id']}/leaves",
            json={"starts_at": "2026-08-15T00:00:00", "ends_at": "2026-08-18T00:00:00"},
            headers=full_access,
        )

        assert response.status_code == 422

    async def test_delete_leave_returns_204(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)
        post = await api.post(
            f"/api/v1/doctors/{created['id']}/leaves",
            json=build_leave_payload(),
            headers=full_access,
        )
        leave_id = post.json()["data"]["id"]

        response = await api.delete(
            f"/api/v1/doctors/{created['id']}/leaves/{leave_id}", headers=full_access
        )
        assert response.status_code == 204

        listed = await api.get(f"/api/v1/doctors/{created['id']}/leaves", headers=full_access)
        assert listed.json()["data"] == []

    async def test_delete_unknown_leave_returns_404(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)
        response = await api.delete(
            f"/api/v1/doctors/{created['id']}/leaves/{uuid.uuid4()}", headers=full_access
        )
        assert response.status_code == 404

    async def test_leave_create_permission_is_distinct(
        self,
        api: AsyncClient,
        full_access: dict[str, str],
        read_only: dict[str, str],
        doctor_user: uuid.UUID,
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)
        response = await api.post(
            f"/api/v1/doctors/{created['id']}/leaves",
            json=build_leave_payload(),
            headers=read_only,
        )
        assert response.status_code == 403


class TestSlots:
    """``GET /doctors/{id}/slots``."""

    async def test_slots_reflect_availability(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)
        await api.put(
            f"/api/v1/doctors/{created['id']}/availability",
            json={
                "entries": [
                    {
                        "day_of_week": 0,
                        "start_time": "09:00:00",
                        "end_time": "10:00:00",
                        "slot_duration_minutes": 15,
                    }
                ]
            },
            headers=full_access,
        )

        # 2026-08-17 is a Monday (day_of_week 0).
        response = await api.get(
            f"/api/v1/doctors/{created['id']}/slots",
            params={"date": "2026-08-17"},
            headers=full_access,
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["slots"]) == 4
        assert {s["status"] for s in data["slots"]} == {"available"}
        assert data["timezone"] == "Asia/Kolkata"

    async def test_slots_on_a_day_with_no_availability_are_empty(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)
        response = await api.get(
            f"/api/v1/doctors/{created['id']}/slots",
            params={"date": "2026-08-18"},
            headers=full_access,
        )
        assert response.json()["data"]["slots"] == []

    async def test_leave_marks_slots_on_leave(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        """End-to-end proof of AC-2: a leave window shows up in the slot feed."""
        created = await _create_doctor(api, full_access, doctor_user)
        await api.put(
            f"/api/v1/doctors/{created['id']}/availability",
            json={
                "entries": [
                    {
                        "day_of_week": 0,
                        "start_time": "09:00:00",
                        "end_time": "10:00:00",
                        "slot_duration_minutes": 15,
                    }
                ]
            },
            headers=full_access,
        )
        # 09:15-09:30 IST on 2026-08-17 == 03:45-04:00 UTC.
        await api.post(
            f"/api/v1/doctors/{created['id']}/leaves",
            json={
                "starts_at": "2026-08-17T03:45:00+00:00",
                "ends_at": "2026-08-17T04:00:00+00:00",
                "reason": "Ward round",
            },
            headers=full_access,
        )

        response = await api.get(
            f"/api/v1/doctors/{created['id']}/slots",
            params={"date": "2026-08-17"},
            headers=full_access,
        )

        statuses = [s["status"] for s in response.json()["data"]["slots"]]
        assert statuses == ["available", "on_leave", "available", "available"]

    async def test_slots_require_availability_read_permission(
        self,
        api: AsyncClient,
        full_access: dict[str, str],
        read_only: dict[str, str],
        doctor_user: uuid.UUID,
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)
        response = await api.get(
            f"/api/v1/doctors/{created['id']}/slots",
            params={"date": "2026-08-17"},
            headers=read_only,
        )
        assert response.status_code == 403

    async def test_slots_missing_date_returns_422(
        self, api: AsyncClient, full_access: dict[str, str], doctor_user: uuid.UUID
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)
        response = await api.get(f"/api/v1/doctors/{created['id']}/slots", headers=full_access)
        assert response.status_code == 422

    async def test_slots_across_tenants_returns_404(
        self,
        api: AsyncClient,
        full_access: dict[str, str],
        other_tenant: dict[str, str],
        doctor_user: uuid.UUID,
    ) -> None:
        created = await _create_doctor(api, full_access, doctor_user)
        response = await api.get(
            f"/api/v1/doctors/{created['id']}/slots",
            params={"date": "2026-08-17"},
            headers=other_tenant,
        )
        assert response.status_code == 404
