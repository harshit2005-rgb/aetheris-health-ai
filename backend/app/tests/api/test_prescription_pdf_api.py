"""API tests for ``GET /api/v1/prescriptions/{id}/pdf``.

Real app, service, repository and database. What the slip says is tested in
``app/tests/unit/services/test_prescription_pdf.py``; here: who may download
it and that what comes back is a PDF.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.dependencies.db import get_db_session
from app.main import create_app
from app.models.appointment import AppointmentStatus
from app.tests.billing_helpers import (
    auth_headers,
    insert_appointment,
    insert_doctor,
    insert_patient,
    insert_user_with_permissions,
)
from app.tests.pharmacy_helpers import insert_medicine

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.database

URL = "/api/v1/prescriptions"
WRITER = ["pharmacy.prescription.read", "pharmacy.prescription.create"]


@pytest_asyncio.fixture
async def api(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """An HTTP client sharing the test's rolled-back session."""
    application: FastAPI = create_app()

    async def _session_override() -> AsyncGenerator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_db_session] = _session_override
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def prescription(
    api: AsyncClient, db_session: AsyncSession, hospital_id: uuid.UUID
) -> tuple[dict[str, Any], dict[str, str]]:
    """A prescription written by a doctor, and the doctor's headers."""
    user = await insert_user_with_permissions(db_session, hospital_id, WRITER)
    headers = auth_headers(user.id, hospital_id)
    doctor = await insert_doctor(db_session, hospital_id, user_id=user.id)
    patient = await insert_patient(db_session, hospital_id)
    appointment = await insert_appointment(
        db_session,
        hospital_id,
        patient_id=patient.id,
        doctor_id=doctor.id,
        status=AppointmentStatus.IN_PROGRESS,
    )
    para = await insert_medicine(db_session, hospital_id, "PARA", name="Paracetamol")
    written = await api.post(
        URL,
        json={
            "appointment_id": str(appointment.id),
            "notes": "Plenty of fluids. Review in five days.",
            "items": [
                {
                    "medicine_id": str(para.id),
                    "dosage": "1 tablet",
                    "frequency": "three times daily",
                    "duration_days": 5,
                    "instructions": "After food.",
                    "quantity": 15,
                }
            ],
        },
        headers=headers,
    )
    assert written.status_code == 201, written.text
    return dict(written.json()["data"]), headers


class TestDownload:
    async def test_a_prescription_is_a_pdf(
        self, api: AsyncClient, prescription: tuple[dict[str, Any], dict[str, str]]
    ) -> None:
        rx, headers = prescription

        response = await api.get(f"{URL}/{rx['id']}/pdf", headers=headers)

        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/pdf"
        disposition = response.headers["content-disposition"]
        assert disposition.startswith('attachment; filename="prescription-')
        assert response.headers["cache-control"] == "no-store"
        assert response.content.startswith(b"%PDF-")

    async def test_a_cancelled_prescription_still_prints(
        self, api: AsyncClient, prescription: tuple[dict[str, Any], dict[str, str]]
    ) -> None:
        rx, headers = prescription
        cancelled = await api.post(
            f"{URL}/{rx['id']}/cancel", json={"reason": "Wrong patient"}, headers=headers
        )
        assert cancelled.status_code == 200, cancelled.text

        response = await api.get(f"{URL}/{rx['id']}/pdf", headers=headers)

        assert response.status_code == 200
        assert response.content.startswith(b"%PDF-")


class TestWhoMayDownload:
    async def test_without_read_permission_it_is_forbidden(
        self,
        api: AsyncClient,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        prescription: tuple[dict[str, Any], dict[str, str]],
    ) -> None:
        rx, _ = prescription
        stranger = await insert_user_with_permissions(db_session, hospital_id, ["lab.order.read"])

        response = await api.get(
            f"{URL}/{rx['id']}/pdf", headers=auth_headers(stranger.id, hospital_id)
        )

        assert response.status_code == 403

    async def test_another_hospital_cannot_see_it(
        self,
        api: AsyncClient,
        db_session: AsyncSession,
        other_hospital_id: uuid.UUID,
        prescription: tuple[dict[str, Any], dict[str, str]],
    ) -> None:
        rx, _ = prescription
        outsider = await insert_user_with_permissions(db_session, other_hospital_id, WRITER)

        response = await api.get(
            f"{URL}/{rx['id']}/pdf", headers=auth_headers(outsider.id, other_hospital_id)
        )

        assert response.status_code == 404

    async def test_an_unknown_prescription_is_not_found(
        self, api: AsyncClient, prescription: tuple[dict[str, Any], dict[str, str]]
    ) -> None:
        _, headers = prescription

        response = await api.get(f"{URL}/{uuid.uuid4()}/pdf", headers=headers)

        assert response.status_code == 404
