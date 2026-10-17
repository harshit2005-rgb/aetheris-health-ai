"""API tests for the Consultation (EMR) endpoints (``docs/modules/16-consultation.md``).

Real app, service, repositories and database; only the HTTP transport is
in-process. Audit events are captured by a recording sink.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.dependencies.db import get_db_session
from app.api.dependencies.services import get_audit_sink
from app.main import create_app
from app.models.appointment import AppointmentStatus
from app.seeds.seed import SYSTEM_ROLES
from app.tests.billing_helpers import (
    auth_headers,
    insert_appointment,
    insert_doctor,
    insert_patient,
    insert_user_with_permissions,
)
from app.tests.conftest import RecordingAuditSink

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.appointment import Appointment

pytestmark = pytest.mark.database

URL = "/api/v1/consultations"


def _role(name: str) -> list[str]:
    """The permission codes the seed gives a role."""
    return next(list(codes) for role, _, codes in SYSTEM_ROLES if role == name)


@pytest.fixture
def audit() -> RecordingAuditSink:
    return RecordingAuditSink()


@pytest_asyncio.fixture
async def api(db_session: AsyncSession, audit: RecordingAuditSink) -> AsyncGenerator[AsyncClient]:
    application: FastAPI = create_app()

    async def _session_override() -> AsyncGenerator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_db_session] = _session_override
    application.dependency_overrides[get_audit_sink] = lambda: audit
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    application.dependency_overrides.clear()


@dataclass
class Visit:
    appointment: Appointment
    doctor: dict[str, str]
    other_doctor: dict[str, str]
    nurse: dict[str, str]
    admin: dict[str, str]


async def _visit(session: AsyncSession, hospital_id: uuid.UUID, status: AppointmentStatus) -> Visit:
    doctor_user = await insert_user_with_permissions(session, hospital_id, _role("Doctor"))
    doctor = await insert_doctor(session, hospital_id, user_id=doctor_user.id)
    other_user = await insert_user_with_permissions(session, hospital_id, _role("Doctor"))
    await insert_doctor(session, hospital_id, user_id=other_user.id)
    nurse = await insert_user_with_permissions(session, hospital_id, _role("Nurse"))
    admin = await insert_user_with_permissions(session, hospital_id, _role("Hospital Admin"))
    patient = await insert_patient(session, hospital_id)
    appointment = await insert_appointment(
        session, hospital_id, patient_id=patient.id, doctor_id=doctor.id, status=status
    )
    return Visit(
        appointment=appointment,
        doctor=auth_headers(doctor_user.id, hospital_id),
        other_doctor=auth_headers(other_user.id, hospital_id),
        nurse=auth_headers(nurse.id, hospital_id),
        admin=auth_headers(admin.id, hospital_id),
    )


@pytest_asyncio.fixture
async def visit(db_session: AsyncSession, hospital_id: uuid.UUID) -> Visit:
    """A visit in progress, with its doctor, another doctor, a nurse and an admin."""
    return await _visit(db_session, hospital_id, AppointmentStatus.IN_PROGRESS)


async def _start(api: AsyncClient, visit: Visit, **body: Any) -> dict[str, Any]:
    response = await api.post(
        URL, json={"appointment_id": str(visit.appointment.id), **body}, headers=visit.doctor
    )
    assert response.status_code == 201, response.text
    return dict(response.json()["data"])


COMPLETE = {
    "chief_complaint": "Fever for three days",
    "history": "No travel. Mild cough.",
    "examination": "Throat congested. Chest clear.",
    "diagnoses": [{"code": "J02.9", "description": "Acute pharyngitis"}],
    "plan": "Paracetamol, fluids, review if fever persists.",
}


class TestLifecycle:
    async def test_doctor_writes_and_finalizes_a_note(
        self, api: AsyncClient, visit: Visit, audit: RecordingAuditSink
    ) -> None:
        note = await _start(api, visit, chief_complaint="Fever")
        assert note["status"] == "draft"
        assert note["is_own"] is True
        assert note["patient_name"]
        assert note["doctor_name"].startswith("Dr. ")

        saved = await api.patch(f"{URL}/{note['id']}", json=COMPLETE, headers=visit.doctor)
        assert saved.status_code == 200, saved.text
        assert saved.json()["data"]["diagnoses"] == COMPLETE["diagnoses"]

        done = await api.post(f"{URL}/{note['id']}/finalize", headers=visit.doctor)
        assert done.status_code == 200, done.text
        body = done.json()["data"]
        assert body["status"] == "finalized"
        assert body["finalized_at"] is not None

        actions = [event.action for event in audit.events]
        assert actions == [
            "consultation.created",
            "consultation.updated",
            "consultation.finalized",
        ]

    async def test_a_finalized_note_is_never_edited_but_takes_addenda(
        self, api: AsyncClient, visit: Visit
    ) -> None:
        note = await _start(api, visit, **COMPLETE)
        await api.post(f"{URL}/{note['id']}/finalize", headers=visit.doctor)

        edit = await api.patch(
            f"{URL}/{note['id']}", json={"plan": "Changed"}, headers=visit.doctor
        )
        assert edit.status_code == 400
        assert "addendum" in edit.json()["message"]

        added = await api.post(
            f"{URL}/{note['id']}/addenda",
            json={"text": "CBC normal; continue plan."},
            headers=visit.doctor,
        )
        assert added.status_code == 201, added.text
        [addendum] = added.json()["data"]["addenda"]
        assert addendum["text"] == "CBC normal; continue plan."
        assert added.json()["data"]["plan"] == COMPLETE["plan"]

    async def test_a_draft_takes_no_addendum(self, api: AsyncClient, visit: Visit) -> None:
        note = await _start(api, visit)

        response = await api.post(
            f"{URL}/{note['id']}/addenda", json={"text": "x"}, headers=visit.doctor
        )

        assert response.status_code == 400

    async def test_finalizing_needs_a_complaint_and_a_diagnosis(
        self, api: AsyncClient, visit: Visit
    ) -> None:
        note = await _start(api, visit)

        response = await api.post(f"{URL}/{note['id']}/finalize", headers=visit.doctor)

        assert response.status_code == 422
        fields = {e["field"] for e in response.json()["errors"]["errors"]}
        assert fields == {"chief_complaint", "diagnoses"}

    async def test_one_note_per_visit(self, api: AsyncClient, visit: Visit) -> None:
        await _start(api, visit)

        again = await api.post(
            URL, json={"appointment_id": str(visit.appointment.id)}, headers=visit.doctor
        )

        assert again.status_code == 409

    async def test_the_visit_note_is_found_by_appointment(
        self, api: AsyncClient, visit: Visit
    ) -> None:
        missing = await api.get(
            f"/api/v1/appointments/{visit.appointment.id}/consultation", headers=visit.doctor
        )
        assert missing.status_code == 404

        note = await _start(api, visit)
        found = await api.get(
            f"/api/v1/appointments/{visit.appointment.id}/consultation", headers=visit.doctor
        )
        assert found.status_code == 200
        assert found.json()["data"]["id"] == note["id"]


class TestVisitState:
    @pytest.mark.parametrize("status", [AppointmentStatus.CHECKED_IN, AppointmentStatus.COMPLETED])
    async def test_a_checked_in_or_completed_visit_can_be_documented(
        self,
        api: AsyncClient,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        status: AppointmentStatus,
    ) -> None:
        visit = await _visit(db_session, hospital_id, status)

        assert (await _start(api, visit))["status"] == "draft"

    @pytest.mark.parametrize(
        "status",
        [AppointmentStatus.BOOKED, AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW],
    )
    async def test_a_visit_not_under_way_cannot_be_documented(
        self,
        api: AsyncClient,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        status: AppointmentStatus,
    ) -> None:
        visit = await _visit(db_session, hospital_id, status)

        response = await api.post(
            URL, json={"appointment_id": str(visit.appointment.id)}, headers=visit.doctor
        )

        assert response.status_code == 400


class TestOwnership:
    async def test_another_doctor_cannot_start_the_note(
        self, api: AsyncClient, visit: Visit
    ) -> None:
        response = await api.post(
            URL, json={"appointment_id": str(visit.appointment.id)}, headers=visit.other_doctor
        )

        assert response.status_code == 403

    async def test_another_doctor_can_read_but_not_write(
        self, api: AsyncClient, visit: Visit
    ) -> None:
        note = await _start(api, visit, **COMPLETE)

        read = await api.get(f"{URL}/{note['id']}", headers=visit.other_doctor)
        assert read.status_code == 200
        assert read.json()["data"]["is_own"] is False

        for response in (
            await api.patch(f"{URL}/{note['id']}", json={"plan": "x"}, headers=visit.other_doctor),
            await api.post(f"{URL}/{note['id']}/finalize", headers=visit.other_doctor),
        ):
            assert response.status_code == 403

    async def test_an_admin_reads_but_cannot_write(self, api: AsyncClient, visit: Visit) -> None:
        note = await _start(api, visit)

        assert (await api.get(f"{URL}/{note['id']}", headers=visit.admin)).status_code == 200
        response = await api.patch(f"{URL}/{note['id']}", json={"plan": "x"}, headers=visit.admin)
        assert response.status_code == 403

    async def test_without_a_token_it_is_unauthorised(self, api: AsyncClient, visit: Visit) -> None:
        assert (await api.get(URL)).status_code == 401

    async def test_another_hospital_sees_nothing(
        self,
        api: AsyncClient,
        visit: Visit,
        db_session: AsyncSession,
        other_hospital_id: uuid.UUID,
    ) -> None:
        note = await _start(api, visit)
        outsider = await insert_user_with_permissions(
            db_session, other_hospital_id, _role("Doctor")
        )
        headers = auth_headers(outsider.id, other_hospital_id)

        assert (await api.get(f"{URL}/{note['id']}", headers=headers)).status_code == 404
        listed = await api.get(URL, headers=headers)
        assert listed.json()["data"] == []


class TestVitals:
    VITALS = {
        "bp_systolic": 128,
        "bp_diastolic": 82,
        "pulse": 88,
        "temperature_c": "38.4",
        "spo2": 97,
        "weight_kg": "70.0",
        "height_cm": "175.0",
    }

    async def test_a_nurse_records_vitals_before_the_doctor_starts(
        self, api: AsyncClient, visit: Visit
    ) -> None:
        response = await api.put(
            f"/api/v1/appointments/{visit.appointment.id}/consultation/vitals",
            json={"vitals": self.VITALS},
            headers=visit.nurse,
        )
        assert response.status_code == 200, response.text
        body = response.json()["data"]
        assert body["status"] == "draft"
        assert body["vitals"]["pulse"] == 88
        assert body["bmi"] == "22.9"

        # The doctor finds the nurse's draft and writes into it.
        found = await api.get(
            f"/api/v1/appointments/{visit.appointment.id}/consultation", headers=visit.doctor
        )
        assert found.json()["data"]["is_own"] is True
        saved = await api.patch(
            f"{URL}/{body['id']}", json={"chief_complaint": "Fever"}, headers=visit.doctor
        )
        assert saved.status_code == 200
        assert saved.json()["data"]["vitals"]["spo2"] == 97

    async def test_a_nurse_cannot_write_clinical_sections(
        self, api: AsyncClient, visit: Visit
    ) -> None:
        note = await _start(api, visit)

        response = await api.patch(f"{URL}/{note['id']}", json={"plan": "x"}, headers=visit.nurse)

        assert response.status_code == 403

    @pytest.mark.parametrize(
        "vitals",
        [
            {},
            {"bp_systolic": 120},
            {"bp_systolic": 80, "bp_diastolic": 90},
            {"spo2": 120},
            {"pulse": 5},
        ],
    )
    async def test_implausible_vitals_are_refused(
        self, api: AsyncClient, visit: Visit, vitals: dict[str, Any]
    ) -> None:
        note = await _start(api, visit)

        response = await api.put(
            f"{URL}/{note['id']}/vitals", json={"vitals": vitals}, headers=visit.doctor
        )

        assert response.status_code == 422

    async def test_vitals_are_locked_once_finalized(self, api: AsyncClient, visit: Visit) -> None:
        note = await _start(api, visit, **COMPLETE)
        await api.post(f"{URL}/{note['id']}/finalize", headers=visit.doctor)

        response = await api.put(
            f"{URL}/{note['id']}/vitals", json={"vitals": {"pulse": 80}}, headers=visit.nurse
        )

        assert response.status_code == 400


class TestValidation:
    async def test_a_follow_up_in_the_past_is_refused(self, api: AsyncClient, visit: Visit) -> None:
        note = await _start(api, visit)
        yesterday = (date.today() - timedelta(days=2)).isoformat()

        response = await api.patch(
            f"{URL}/{note['id']}", json={"follow_up_date": yesterday}, headers=visit.doctor
        )

        assert response.status_code == 422

    async def test_an_empty_update_is_refused(self, api: AsyncClient, visit: Visit) -> None:
        note = await _start(api, visit)

        response = await api.patch(f"{URL}/{note['id']}", json={}, headers=visit.doctor)

        assert response.status_code == 422

    async def test_unknown_fields_are_refused(self, api: AsyncClient, visit: Visit) -> None:
        response = await api.post(
            URL,
            json={"appointment_id": str(visit.appointment.id), "patient_id": str(uuid.uuid4())},
            headers=visit.doctor,
        )

        assert response.status_code == 422


class TestListAndVisitOrders:
    async def test_list_by_patient_newest_first(self, api: AsyncClient, visit: Visit) -> None:
        note = await _start(api, visit, chief_complaint="Fever")

        listed = await api.get(URL, params={"patient_id": note["patient_id"]}, headers=visit.admin)

        assert listed.status_code == 200
        [row] = listed.json()["data"]
        assert row["id"] == note["id"]
        assert row["chief_complaint"] == "Fever"
        assert listed.json()["metadata"]["pagination"]["total_records"] == 1

    async def test_the_note_shows_the_visit_prescriptions(
        self, api: AsyncClient, visit: Visit, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        from app.tests.pharmacy_helpers import insert_medicine  # noqa: PLC0415

        para = await insert_medicine(db_session, hospital_id, "PARA", name="Paracetamol")
        written = await api.post(
            "/api/v1/prescriptions",
            json={
                "appointment_id": str(visit.appointment.id),
                "items": [
                    {
                        "medicine_id": str(para.id),
                        "dosage": "1 tablet",
                        "frequency": "three times daily",
                        "duration_days": 5,
                        "quantity": 15,
                    }
                ],
            },
            headers=visit.doctor,
        )
        assert written.status_code == 201, written.text
        note = await _start(api, visit)

        [rx] = note["prescriptions"]
        assert rx["items"][0]["medicine_name"].startswith("Paracetamol")
        assert note["lab_orders"] == []
