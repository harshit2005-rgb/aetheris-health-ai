"""Integration tests for the Patient Management module.

Real database, real repositories, real service — only the audit sink is a
double, so that the events can be asserted on
(``docs/11-TESTING_STRATEGY.md`` §2.4, §5).

Covers the workflow the module spec lists under "Integration Tests": register →
retrieve → update → search → deactivate, plus the tenancy and MRN guarantees
that only show up once every layer is wired together.

The API layer is not exercised here: the patient router is blocked on the
authentication module's ``require_permission`` dependency
(``docs/modules/01-authentication.md``, Sprint 1). When it lands, the API tests
in ``app/tests/api/`` sit on top of exactly this service surface.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.repositories.mrn_sequence_repository import MrnSequenceRepository
from app.repositories.patient_repository import PatientRepository
from app.schemas.common import PaginationParams
from app.schemas.patient import SearchPatientRequest
from app.services.mrn_service import MRNService
from app.services.patient_service import (
    PatientAlreadyActiveError,
    PatientNotDeactivatedError,
    PatientNotFoundError,
    PatientService,
)
from app.tests.factories import build_create_patient_request, build_update_patient_request
from app.utils.datetime import utc_today

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.tests.conftest import RecordingAuditSink

pytestmark = pytest.mark.database


@pytest.fixture
def service(db_session: AsyncSession, audit_sink: RecordingAuditSink) -> PatientService:
    """A fully wired :class:`PatientService` on the transactional test session."""
    return PatientService(
        PatientRepository(db_session),
        MRNService(MrnSequenceRepository(db_session)),
        db_session,
        audit_sink,
    )


class TestRegistrationWorkflow:
    """Register → retrieve (module spec §5.1)."""

    async def test_a_registered_patient_can_be_retrieved_with_every_field_intact(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        created = await service.register_patient(
            hospital_id, build_create_patient_request(), actor_id=actor_id
        )

        fetched = await service.get_patient_details(hospital_id, created.id)

        assert fetched.mrn == created.mrn
        assert fetched.first_name == "Ananya"
        assert fetched.phone == "+919812345678"
        assert fetched.address == {
            "line1": "12, MG Road",
            "line2": None,
            "city": "Hyderabad",
            "state": "TS",
            "postal_code": "500001",
            "country": "IN",
        }
        assert fetched.allergies[0]["name"] == "Penicillin"
        assert fetched.chronic_conditions[0]["since_year"] == 2019
        assert fetched.status == "active"

    async def test_the_first_patient_of_a_hospital_gets_sequence_one(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
    ) -> None:
        # AC-2: MRN follows the configured format, MRN-{year}-{seq:05d}.
        created = await service.register_patient(hospital_id, build_create_patient_request())

        assert created.mrn == f"MRN-{utc_today().year}-00001"

    async def test_mrns_increment_within_a_hospital(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
    ) -> None:
        mrns = [
            (await service.register_patient(hospital_id, build_create_patient_request())).mrn
            for _ in range(3)
        ]

        year = utc_today().year
        assert mrns == [f"MRN-{year}-0000{n}" for n in (1, 2, 3)]

    async def test_two_hospitals_number_their_patients_independently(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        first = await service.register_patient(hospital_id, build_create_patient_request())
        second = await service.register_patient(other_hospital_id, build_create_patient_request())

        assert first.mrn == second.mrn == f"MRN-{utc_today().year}-00001"
        assert first.id != second.id

    async def test_registration_records_the_acting_user_on_the_row(
        self,
        service: PatientService,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        created = await service.register_patient(
            hospital_id, build_create_patient_request(), actor_id=None
        )

        stored = await PatientRepository(db_session).get_patient_by_id(hospital_id, created.id)

        assert stored is not None
        assert stored.created_at is not None

    async def test_registration_writes_an_audit_event(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
        audit_sink: RecordingAuditSink,
        actor_id: uuid.UUID,
    ) -> None:
        created = await service.register_patient(
            hospital_id, build_create_patient_request(), actor_id=actor_id
        )

        event = audit_sink.last()
        assert event.action == "patient.created"
        assert event.target_id == created.id
        assert event.actor_id == actor_id


class TestUpdateWorkflow:
    """Register → update (module spec §5.2)."""

    async def test_an_update_persists_and_leaves_other_fields_alone(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        created = await service.register_patient(hospital_id, build_create_patient_request())

        await service.update_patient(
            hospital_id,
            created.id,
            build_update_patient_request(phone="+919812349999", occupation="Engineer"),
            actor_id=actor_id,
        )
        refetched = await service.get_patient_details(hospital_id, created.id)

        assert refetched.phone == "+919812349999"
        assert refetched.occupation == "Engineer"
        assert refetched.first_name == "Ananya"
        assert refetched.email == "ananya@example.com"

    async def test_an_update_can_replace_structured_medical_history(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
    ) -> None:
        created = await service.register_patient(hospital_id, build_create_patient_request())

        await service.update_patient(
            hospital_id,
            created.id,
            build_update_patient_request(
                allergies=[{"name": "Latex", "severity": "severe", "reaction": "hives"}]
            ),
        )
        refetched = await service.get_patient_details(hospital_id, created.id)

        assert len(refetched.allergies) == 1
        assert refetched.allergies[0]["name"] == "Latex"
        assert refetched.allergies[0]["reaction"] == "hives"

    async def test_an_update_never_changes_the_mrn(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
    ) -> None:
        created = await service.register_patient(hospital_id, build_create_patient_request())

        await service.update_patient(
            hospital_id, created.id, build_update_patient_request(occupation="Engineer")
        )
        refetched = await service.get_patient_details(hospital_id, created.id)

        assert refetched.mrn == created.mrn

    async def test_an_update_audits_the_before_and_after_values(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
        audit_sink: RecordingAuditSink,
        actor_id: uuid.UUID,
    ) -> None:
        # AC-5: every write produces an audit entry with actor and diff.
        created = await service.register_patient(hospital_id, build_create_patient_request())

        await service.update_patient(
            hospital_id,
            created.id,
            build_update_patient_request(phone="+919812349999"),
            actor_id=actor_id,
        )

        event = audit_sink.last()
        assert event.action == "patient.updated"
        assert event.changes["phone"] == {
            "before": "+919812345678",
            "after": "+919812349999",
        }

    async def test_updating_an_unknown_patient_raises(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
    ) -> None:
        with pytest.raises(PatientNotFoundError):
            await service.update_patient(
                hospital_id, uuid.uuid4(), build_update_patient_request(occupation="Engineer")
            )


class TestSearchWorkflow:
    """Register → search (module spec §5.5)."""

    async def test_search_finds_a_patient_by_name_prefix(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
    ) -> None:
        # AC-3: first three letters of the name.
        await service.register_patient(hospital_id, build_create_patient_request(last_name="Rao"))
        await service.register_patient(
            hospital_id, build_create_patient_request(last_name="Sharma")
        )

        page = await service.search_patients(hospital_id, SearchPatientRequest(q="rao"))

        assert page.total_records == 1
        assert page.items[0].last_name == "Rao"

    async def test_search_finds_a_patient_by_exact_mrn(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
    ) -> None:
        created = await service.register_patient(hospital_id, build_create_patient_request())

        page = await service.search_patients(hospital_id, SearchPatientRequest(q=created.mrn))

        assert page.items[0].id == created.id

    async def test_search_finds_a_patient_by_full_phone_number(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
    ) -> None:
        created = await service.register_patient(hospital_id, build_create_patient_request())

        page = await service.search_patients(hospital_id, SearchPatientRequest(q="+919812345678"))

        assert page.items[0].id == created.id

    async def test_search_filters_by_age_range(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
    ) -> None:
        today = utc_today()
        await service.register_patient(
            hospital_id,
            build_create_patient_request(
                last_name="Young", date_of_birth=date(today.year - 20, 1, 1).isoformat()
            ),
        )
        await service.register_patient(
            hospital_id,
            build_create_patient_request(
                last_name="Older", date_of_birth=date(today.year - 60, 1, 1).isoformat()
            ),
        )

        page = await service.search_patients(hospital_id, SearchPatientRequest(age_gte=50))

        assert page.total_records == 1
        assert page.items[0].last_name == "Older"

    async def test_list_paginates_and_reports_a_consistent_total(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
    ) -> None:
        for index in range(5):
            await service.register_patient(
                hospital_id, build_create_patient_request(last_name=f"Patient{index}")
            )

        page = await service.list_patients(
            hospital_id, pagination=PaginationParams(page=2, page_size=2)
        )

        assert page.total_records == 5
        assert page.total_pages == 3
        assert len(page.items) == 2

    async def test_search_reports_a_result_count_in_the_audit_event(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
        audit_sink: RecordingAuditSink,
        actor_id: uuid.UUID,
    ) -> None:
        await service.register_patient(hospital_id, build_create_patient_request())

        await service.search_patients(hospital_id, SearchPatientRequest(q="rao"), actor_id=actor_id)

        event = audit_sink.last()
        assert event.action == "patient.searched"
        assert event.context["result_count"] == 1


class TestDeactivationWorkflow:
    """Deactivate → reactivate (module spec §4, rule 4)."""

    async def test_a_deactivated_patient_disappears_from_lists_and_search(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        created = await service.register_patient(
            hospital_id, build_create_patient_request(last_name="Rao")
        )

        await service.deactivate_patient(hospital_id, created.id, actor_id=actor_id)

        assert (await service.list_patients(hospital_id)).total_records == 0
        assert (
            await service.search_patients(hospital_id, SearchPatientRequest(q="rao"))
        ).total_records == 0
        with pytest.raises(PatientNotFoundError):
            await service.get_patient_details(hospital_id, created.id)

    async def test_a_deactivated_patient_is_still_in_the_database(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
    ) -> None:
        # Soft delete only: appointments and invoices keep their reference.
        created = await service.register_patient(hospital_id, build_create_patient_request())

        await service.deactivate_patient(hospital_id, created.id)
        fetched = await service.get_patient_details(hospital_id, created.id, include_inactive=True)

        assert fetched.status == "inactive"
        assert fetched.mrn == created.mrn

    async def test_a_deactivated_patient_keeps_its_mrn_and_the_next_one_is_fresh(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
    ) -> None:
        first = await service.register_patient(hospital_id, build_create_patient_request())
        await service.deactivate_patient(hospital_id, first.id)

        second = await service.register_patient(hospital_id, build_create_patient_request())

        assert second.mrn != first.mrn
        assert second.mrn == f"MRN-{utc_today().year}-00002"

    async def test_reactivating_restores_the_patient_to_lists(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        created = await service.register_patient(hospital_id, build_create_patient_request())
        await service.deactivate_patient(hospital_id, created.id)

        reactivated = await service.activate_patient(hospital_id, created.id, actor_id=actor_id)

        assert reactivated.status == "active"
        assert (await service.list_patients(hospital_id)).total_records == 1

    async def test_deactivating_twice_is_rejected(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
    ) -> None:
        created = await service.register_patient(hospital_id, build_create_patient_request())
        await service.deactivate_patient(hospital_id, created.id)

        with pytest.raises(PatientNotDeactivatedError):
            await service.deactivate_patient(hospital_id, created.id)

    async def test_reactivating_an_active_patient_is_rejected(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
    ) -> None:
        created = await service.register_patient(hospital_id, build_create_patient_request())

        with pytest.raises(PatientAlreadyActiveError):
            await service.activate_patient(hospital_id, created.id)

    async def test_the_full_lifecycle_produces_one_audit_event_per_mutation(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
        audit_sink: RecordingAuditSink,
        actor_id: uuid.UUID,
    ) -> None:
        created = await service.register_patient(
            hospital_id, build_create_patient_request(), actor_id=actor_id
        )
        await service.update_patient(
            hospital_id,
            created.id,
            build_update_patient_request(occupation="Engineer"),
            actor_id=actor_id,
        )
        await service.deactivate_patient(hospital_id, created.id, actor_id=actor_id)
        await service.activate_patient(hospital_id, created.id, actor_id=actor_id)

        assert audit_sink.actions() == [
            "patient.created",
            "patient.updated",
            "patient.deactivated",
            "patient.activated",
        ]
        assert all(event.actor_id == actor_id for event in audit_sink.events)


class TestTenantIsolationEndToEnd:
    """A patient registered in one hospital is invisible from another."""

    async def test_a_patient_cannot_be_read_from_another_hospital(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        # AC-7 and CLAUDE.md rule 5. A 404 rather than a 403, so the response
        # does not confirm that the record exists somewhere.
        created = await service.register_patient(hospital_id, build_create_patient_request())

        with pytest.raises(PatientNotFoundError):
            await service.get_patient_details(other_hospital_id, created.id)

    async def test_a_patient_cannot_be_updated_from_another_hospital(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        created = await service.register_patient(hospital_id, build_create_patient_request())

        with pytest.raises(PatientNotFoundError):
            await service.update_patient(
                other_hospital_id,
                created.id,
                build_update_patient_request(occupation="Engineer"),
            )

    async def test_a_patient_cannot_be_deactivated_from_another_hospital(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        created = await service.register_patient(hospital_id, build_create_patient_request())

        with pytest.raises(PatientNotFoundError):
            await service.deactivate_patient(other_hospital_id, created.id)

    async def test_search_never_returns_another_hospitals_patients(
        self,
        service: PatientService,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        await service.register_patient(
            other_hospital_id, build_create_patient_request(last_name="Rao")
        )

        page = await service.search_patients(hospital_id, SearchPatientRequest(q="rao"))

        assert page.total_records == 0
        assert page.items == []
