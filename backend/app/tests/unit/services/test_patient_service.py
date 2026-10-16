"""Unit tests for :class:`~app.services.patient_service.PatientService`.

Repositories are mocked (``docs/11-TESTING_STRATEGY.md`` §2.1), so these tests
prove the *business rules* — MRN retry, tenancy pass-through, PATCH semantics,
lifecycle transitions, and the audit record — without a database. Behaviour
that only a real database can prove (the row lock, the unique index, tenant
filtering in SQL) is covered in ``app/tests/repository/`` and
``app/tests/integration/``.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ValidationError
from app.models.patient import Gender
from app.repositories.patient_repository import PatientRepository
from app.schemas.common import PaginationParams
from app.schemas.patient import CreatePatientRequest, SearchPatientRequest
from app.services.mrn_service import MRNService
from app.services.patient_service import (
    MAX_MRN_ATTEMPTS,
    DuplicateMrnError,
    PatientAlreadyActiveError,
    PatientNotDeactivatedError,
    PatientNotFoundError,
    PatientService,
)
from app.tests.factories import build_create_patient_request, build_update_patient_request
from app.tests.factories.patient import build_patient_model
from app.utils.datetime import subtract_years, utc_today

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.tests.conftest import FakeSession, RecordingAuditSink

HOSPITAL_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_HOSPITAL_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
ACTOR_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def _mrn_integrity_error() -> IntegrityError:
    """Build the IntegrityError PostgreSQL raises on an MRN collision."""
    return IntegrityError(
        "INSERT INTO patients ...",
        {},
        Exception('duplicate key value violates unique constraint "uq_patients_hospital_mrn"'),
    )


def _unrelated_integrity_error() -> IntegrityError:
    """Build an IntegrityError from a different constraint."""
    return IntegrityError(
        "INSERT INTO patients ...",
        {},
        Exception(
            'insert or update on table "patients" violates foreign key constraint '
            '"fk_patients_hospital_id_hospitals"'
        ),
    )


@pytest.fixture
def patients() -> AsyncMock:
    """Mocked :class:`PatientRepository`."""
    return AsyncMock(spec=PatientRepository)


@pytest.fixture
def mrn_service() -> AsyncMock:
    """Mocked :class:`MRNService` that issues sequential MRNs."""
    service = AsyncMock(spec=MRNService)
    service.next.side_effect = [f"MRN-2026-{n:05d}" for n in range(1, 50)]
    return service


@pytest.fixture
def service(
    patients: AsyncMock,
    mrn_service: AsyncMock,
    fake_session: FakeSession,
    audit_sink: RecordingAuditSink,
) -> PatientService:
    """The service under test, wired to doubles."""
    # FakeSession implements only the two members PatientService touches
    # (``begin_nested`` and ``commit``), so it is not a structural AsyncSession.
    # The cast documents that narrowing rather than widening the production
    # signature to accommodate a test double.
    return PatientService(patients, mrn_service, cast("AsyncSession", fake_session), audit_sink)


class TestRegisterPatient:
    """Registration (module spec §5.1)."""

    async def test_register_patient_persists_and_returns_the_new_record(
        self,
        service: PatientService,
        patients: AsyncMock,
        fake_session: FakeSession,
    ) -> None:
        created = build_patient_model(hospital_id=HOSPITAL_ID, mrn="MRN-2026-00001")
        patients.create_patient.return_value = created

        response = await service.register_patient(
            HOSPITAL_ID, build_create_patient_request(), actor_id=ACTOR_ID
        )

        assert response.mrn == "MRN-2026-00001"
        assert response.first_name == "Ananya"
        assert fake_session.commits == 1

    async def test_register_patient_scopes_the_insert_to_the_caller_hospital(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        patients.create_patient.return_value = build_patient_model(hospital_id=HOSPITAL_ID)

        await service.register_patient(HOSPITAL_ID, build_create_patient_request())

        assert patients.create_patient.await_args.kwargs["hospital_id"] == HOSPITAL_ID

    async def test_register_patient_records_the_acting_user(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        patients.create_patient.return_value = build_patient_model()

        await service.register_patient(
            HOSPITAL_ID, build_create_patient_request(), actor_id=ACTOR_ID
        )

        assert patients.create_patient.await_args.kwargs["created_by"] == ACTOR_ID

    async def test_register_patient_never_accepts_a_generated_mrn_from_the_payload(
        self,
        service: PatientService,
        patients: AsyncMock,
        mrn_service: AsyncMock,
    ) -> None:
        # The MRN handed to the repository must come from MRNService, not from
        # anything the caller supplied.
        patients.create_patient.return_value = build_patient_model()

        await service.register_patient(HOSPITAL_ID, build_create_patient_request())

        mrn_service.next.assert_awaited_once_with(HOSPITAL_ID)
        assert patients.create_patient.await_args.kwargs["mrn"] == "MRN-2026-00001"

    async def test_register_patient_writes_an_audit_event(
        self,
        service: PatientService,
        patients: AsyncMock,
        audit_sink: RecordingAuditSink,
    ) -> None:
        created = build_patient_model(hospital_id=HOSPITAL_ID)
        patients.create_patient.return_value = created

        await service.register_patient(
            HOSPITAL_ID, build_create_patient_request(), actor_id=ACTOR_ID
        )

        event = audit_sink.last()
        assert event.action == "patient.created"
        assert event.hospital_id == HOSPITAL_ID
        assert event.target_id == created.id
        assert event.actor_id == ACTOR_ID

    async def test_register_patient_passes_structured_history_through_as_json(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        patients.create_patient.return_value = build_patient_model()

        await service.register_patient(HOSPITAL_ID, build_create_patient_request())

        kwargs = patients.create_patient.await_args.kwargs
        assert kwargs["allergies"] == [
            {"name": "Penicillin", "severity": "moderate", "reaction": None, "noted_on": None}
        ]
        # date and enum columns must arrive as Python objects, not JSON strings.
        assert isinstance(kwargs["date_of_birth"], date)
        assert kwargs["gender"] == Gender.FEMALE

    async def test_register_patient_rejects_a_future_date_of_birth(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        # Built with model_construct to skip Pydantic and reach the service
        # guard directly — the rule must hold for non-HTTP callers too.
        payload = CreatePatientRequest.model_construct(
            first_name="Ravi",
            last_name="Rao",
            date_of_birth=date(utc_today().year + 1, 1, 1),
            gender=Gender.MALE,
            phone=None,
            allergies=[],
            chronic_conditions=[],
            current_medications=[],
        )

        with pytest.raises(ValidationError, match="failed validation"):
            await service.register_patient(HOSPITAL_ID, payload)

        patients.create_patient.assert_not_awaited()

    async def test_register_patient_rejects_a_non_e164_phone_from_a_non_http_caller(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        payload = CreatePatientRequest.model_construct(
            first_name="Ravi",
            last_name="Rao",
            date_of_birth=date(1990, 1, 1),
            gender=Gender.MALE,
            phone="9812345678",
            allergies=[],
            chronic_conditions=[],
            current_medications=[],
        )

        with pytest.raises(ValidationError) as exc_info:
            await service.register_patient(HOSPITAL_ID, payload)

        assert exc_info.value.detail["errors"][0]["field"] == "phone"
        patients.create_patient.assert_not_awaited()

    async def test_register_patient_does_not_commit_when_validation_fails(
        self,
        service: PatientService,
        fake_session: FakeSession,
    ) -> None:
        payload = CreatePatientRequest.model_construct(
            first_name="Ravi",
            last_name="Rao",
            date_of_birth=date(utc_today().year + 1, 1, 1),
            gender=Gender.MALE,
            phone=None,
            allergies=[],
            chronic_conditions=[],
            current_medications=[],
        )

        with pytest.raises(ValidationError):
            await service.register_patient(HOSPITAL_ID, payload)

        assert fake_session.commits == 0


class TestRegisterPatientMrnCollision:
    """Duplicate-MRN handling (module spec §14)."""

    async def test_register_patient_retries_with_a_fresh_mrn_after_a_collision(
        self,
        service: PatientService,
        patients: AsyncMock,
        mrn_service: AsyncMock,
        fake_session: FakeSession,
    ) -> None:
        created = build_patient_model(mrn="MRN-2026-00002")
        patients.create_patient.side_effect = [_mrn_integrity_error(), created]

        response = await service.register_patient(HOSPITAL_ID, build_create_patient_request())

        assert response.mrn == "MRN-2026-00002"
        assert mrn_service.next.await_count == 2
        # The failed attempt rolled back to its savepoint rather than aborting
        # the whole transaction.
        assert fake_session.savepoints_rolled_back == 1
        assert fake_session.commits == 1

    async def test_register_patient_raises_after_exhausting_retries(
        self,
        service: PatientService,
        patients: AsyncMock,
        mrn_service: AsyncMock,
        fake_session: FakeSession,
    ) -> None:
        patients.create_patient.side_effect = [
            _mrn_integrity_error() for _ in range(MAX_MRN_ATTEMPTS)
        ]

        with pytest.raises(DuplicateMrnError):
            await service.register_patient(HOSPITAL_ID, build_create_patient_request())

        assert mrn_service.next.await_count == MAX_MRN_ATTEMPTS
        assert fake_session.commits == 0

    async def test_register_patient_propagates_an_unrelated_integrity_error(
        self,
        service: PatientService,
        patients: AsyncMock,
        mrn_service: AsyncMock,
    ) -> None:
        # A bad hospital_id is a bug, not a collision. Retrying it four more
        # times would hide the cause and quadruple the log noise.
        patients.create_patient.side_effect = _unrelated_integrity_error()

        with pytest.raises(IntegrityError):
            await service.register_patient(HOSPITAL_ID, build_create_patient_request())

        assert mrn_service.next.await_count == 1


class TestGetPatientDetails:
    """Single-record retrieval."""

    async def test_get_patient_details_returns_the_record(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        patient = build_patient_model(hospital_id=HOSPITAL_ID)
        patients.get_patient_by_id.return_value = patient

        response = await service.get_patient_details(HOSPITAL_ID, patient.id)

        assert response.id == patient.id
        assert response.mrn == patient.mrn

    async def test_get_patient_details_raises_when_absent(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        patients.get_patient_by_id.return_value = None

        with pytest.raises(PatientNotFoundError):
            await service.get_patient_details(HOSPITAL_ID, uuid.uuid4())

    async def test_get_patient_details_scopes_the_lookup_to_the_caller_hospital(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        # A patient in another tenant must be a 404, not a 403 — distinguishing
        # them would confirm that the record exists somewhere.
        patients.get_patient_by_id.return_value = None
        patient_id = uuid.uuid4()

        with pytest.raises(PatientNotFoundError):
            await service.get_patient_details(OTHER_HOSPITAL_ID, patient_id)

        patients.get_patient_by_id.assert_awaited_once_with(
            OTHER_HOSPITAL_ID, patient_id, include_deleted=False
        )

    async def test_get_patient_details_excludes_deactivated_records_by_default(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        patients.get_patient_by_id.return_value = build_patient_model()

        await service.get_patient_details(HOSPITAL_ID, uuid.uuid4())

        assert patients.get_patient_by_id.await_args.kwargs["include_deleted"] is False


class TestUpdatePatient:
    """Partial update (module spec §5.2)."""

    async def test_update_patient_applies_only_the_fields_that_were_sent(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        existing = build_patient_model(phone="+919812345678", first_name="Ananya")
        patients.get_patient_by_id.return_value = existing
        patients.update_patient.return_value = build_patient_model(phone="+919812349999")

        await service.update_patient(
            HOSPITAL_ID,
            existing.id,
            build_update_patient_request(phone="+919812349999"),
            actor_id=ACTOR_ID,
        )

        kwargs = patients.update_patient.await_args.kwargs
        assert kwargs["phone"] == "+919812349999"
        assert "first_name" not in kwargs

    async def test_update_patient_records_the_acting_user(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        existing = build_patient_model(occupation="Teacher")
        patients.get_patient_by_id.return_value = existing
        patients.update_patient.return_value = existing

        await service.update_patient(
            HOSPITAL_ID,
            existing.id,
            build_update_patient_request(occupation="Engineer"),
            actor_id=ACTOR_ID,
        )

        assert patients.update_patient.await_args.kwargs["updated_by"] == ACTOR_ID

    async def test_update_patient_writes_an_audit_event_with_a_before_and_after_diff(
        self,
        service: PatientService,
        patients: AsyncMock,
        audit_sink: RecordingAuditSink,
    ) -> None:
        # AC-5: every write produces an audit entry with actor and diff.
        existing = build_patient_model(occupation="Teacher", hospital_id=HOSPITAL_ID)
        patients.get_patient_by_id.return_value = existing
        patients.update_patient.return_value = existing

        await service.update_patient(
            HOSPITAL_ID,
            existing.id,
            build_update_patient_request(occupation="Engineer"),
            actor_id=ACTOR_ID,
        )

        event = audit_sink.last()
        assert event.action == "patient.updated"
        assert event.actor_id == ACTOR_ID
        assert event.changes == {"occupation": {"before": "Teacher", "after": "Engineer"}}

    async def test_update_patient_ignores_a_field_set_to_its_current_value(
        self,
        service: PatientService,
        patients: AsyncMock,
        audit_sink: RecordingAuditSink,
        fake_session: FakeSession,
    ) -> None:
        # Writing a no-op row would produce an audit entry implying an edit
        # that never happened.
        existing = build_patient_model(occupation="Teacher")
        patients.get_patient_by_id.return_value = existing

        await service.update_patient(
            HOSPITAL_ID, existing.id, build_update_patient_request(occupation="Teacher")
        )

        patients.update_patient.assert_not_awaited()
        assert audit_sink.events == []
        assert fake_session.commits == 0

    async def test_update_patient_can_clear_an_optional_field(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        existing = build_patient_model(phone="+919812345678")
        patients.get_patient_by_id.return_value = existing
        patients.update_patient.return_value = build_patient_model(phone=None)

        await service.update_patient(
            HOSPITAL_ID, existing.id, build_update_patient_request(phone=None)
        )

        assert patients.update_patient.await_args.kwargs["phone"] is None

    async def test_update_patient_replaces_the_medical_history_list(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        existing = build_patient_model(allergies=[])
        patients.get_patient_by_id.return_value = existing
        patients.update_patient.return_value = existing

        await service.update_patient(
            HOSPITAL_ID,
            existing.id,
            build_update_patient_request(allergies=[{"name": "Latex", "severity": "severe"}]),
        )

        allergies = patients.update_patient.await_args.kwargs["allergies"]
        assert allergies[0]["name"] == "Latex"
        assert allergies[0]["severity"] == "severe"

    async def test_update_patient_raises_when_absent(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        patients.get_patient_by_id.return_value = None

        with pytest.raises(PatientNotFoundError):
            await service.update_patient(
                HOSPITAL_ID, uuid.uuid4(), build_update_patient_request(occupation="Engineer")
            )

    async def test_update_patient_commits_once(
        self,
        service: PatientService,
        patients: AsyncMock,
        fake_session: FakeSession,
    ) -> None:
        existing = build_patient_model(occupation="Teacher")
        patients.get_patient_by_id.return_value = existing
        patients.update_patient.return_value = existing

        await service.update_patient(
            HOSPITAL_ID, existing.id, build_update_patient_request(occupation="Engineer")
        )

        assert fake_session.commits == 1


class TestPatientLifecycle:
    """Deactivate and reactivate (module spec §4, rule 4)."""

    async def test_deactivate_patient_soft_deletes_and_records_the_actor(
        self,
        service: PatientService,
        patients: AsyncMock,
        audit_sink: RecordingAuditSink,
    ) -> None:
        existing = build_patient_model(hospital_id=HOSPITAL_ID)
        patients.get_patient_by_id.return_value = existing
        patients.delete_patient.return_value = build_patient_model(
            id=existing.id, deleted_at=date(2026, 7, 27)
        )

        response = await service.deactivate_patient(HOSPITAL_ID, existing.id, actor_id=ACTOR_ID)

        assert patients.delete_patient.await_args.kwargs["deleted_by"] == ACTOR_ID
        assert response.status == "inactive"
        assert audit_sink.last().action == "patient.deactivated"

    async def test_deactivate_patient_never_hard_deletes(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        # Appointments and invoices reference patients; a hard delete would
        # orphan clinical history.
        existing = build_patient_model()
        patients.get_patient_by_id.return_value = existing
        patients.delete_patient.return_value = existing

        await service.deactivate_patient(HOSPITAL_ID, existing.id)

        patients.hard_delete.assert_not_awaited()

    async def test_deactivate_patient_rejects_an_already_deactivated_record(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        patients.get_patient_by_id.return_value = build_patient_model(deleted_at=date(2026, 7, 1))

        with pytest.raises(PatientNotDeactivatedError):
            await service.deactivate_patient(HOSPITAL_ID, uuid.uuid4())

        patients.delete_patient.assert_not_awaited()

    async def test_deactivate_patient_raises_when_absent(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        patients.get_patient_by_id.return_value = None

        with pytest.raises(PatientNotFoundError):
            await service.deactivate_patient(HOSPITAL_ID, uuid.uuid4())

    async def test_activate_patient_clears_the_soft_delete(
        self,
        service: PatientService,
        patients: AsyncMock,
        audit_sink: RecordingAuditSink,
    ) -> None:
        deactivated = build_patient_model(deleted_at=date(2026, 7, 1))
        patients.get_patient_by_id.return_value = deactivated
        patients.restore_patient.return_value = build_patient_model(id=deactivated.id)

        response = await service.activate_patient(HOSPITAL_ID, deactivated.id, actor_id=ACTOR_ID)

        assert response.status == "active"
        assert patients.restore_patient.await_args.kwargs["updated_by"] == ACTOR_ID
        assert audit_sink.last().action == "patient.activated"

    async def test_activate_patient_rejects_an_already_active_record(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        patients.get_patient_by_id.return_value = build_patient_model(deleted_at=None)

        with pytest.raises(PatientAlreadyActiveError):
            await service.activate_patient(HOSPITAL_ID, uuid.uuid4())

        patients.restore_patient.assert_not_awaited()

    async def test_lifecycle_lookups_include_deactivated_records(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        # Reactivation must be able to find the record it is reactivating.
        patients.get_patient_by_id.return_value = build_patient_model(deleted_at=date(2026, 7, 1))
        patients.restore_patient.return_value = build_patient_model()

        await service.activate_patient(HOSPITAL_ID, uuid.uuid4())

        assert patients.get_patient_by_id.await_args.kwargs["include_deleted"] is True


class TestListPatients:
    """Paginated listing."""

    async def test_list_patients_returns_a_page_with_totals(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        patients.list_patients.return_value = [build_patient_model() for _ in range(3)]
        patients.count_patients.return_value = 137

        page = await service.list_patients(
            HOSPITAL_ID, pagination=PaginationParams(page=2, page_size=25)
        )

        assert len(page.items) == 3
        assert (page.page, page.total_records, page.total_pages) == (2, 137, 6)

    async def test_list_patients_translates_the_page_number_to_an_offset(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        patients.list_patients.return_value = []
        patients.count_patients.return_value = 0

        await service.list_patients(HOSPITAL_ID, pagination=PaginationParams(page=3, page_size=20))

        kwargs = patients.list_patients.await_args.kwargs
        assert (kwargs["skip"], kwargs["limit"]) == (40, 20)

    async def test_list_patients_excludes_deactivated_records_by_default(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        # Module spec §14: list views exclude soft-deleted patients.
        patients.list_patients.return_value = []
        patients.count_patients.return_value = 0

        await service.list_patients(HOSPITAL_ID)

        assert patients.list_patients.await_args.kwargs["include_deleted"] is False

    async def test_list_patients_counts_with_the_same_scope_it_lists_with(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        # A total computed under different filters than the page produces
        # pagination that never reaches its last page.
        patients.list_patients.return_value = []
        patients.count_patients.return_value = 0

        await service.list_patients(HOSPITAL_ID, include_inactive=True)

        assert patients.count_patients.await_args.kwargs["include_deleted"] is True


class TestSearchPatients:
    """Search (module spec §5.5)."""

    async def test_search_patients_passes_the_term_to_the_repository(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        patients.search_patients.return_value = [build_patient_model()]
        patients.count_patients.return_value = 1

        page = await service.search_patients(HOSPITAL_ID, SearchPatientRequest(q="rao"))

        assert patients.search_patients.await_args.kwargs["term"] == "rao"
        assert len(page.items) == 1

    async def test_search_patients_converts_a_minimum_age_to_a_latest_birth_date(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        # age >= 40 means born on or before today minus 40 years.
        patients.search_patients.return_value = []
        patients.count_patients.return_value = 0

        await service.search_patients(HOSPITAL_ID, SearchPatientRequest(age_gte=40))

        kwargs = patients.search_patients.await_args.kwargs
        assert kwargs["born_on_or_before"] == subtract_years(utc_today(), 40)
        assert kwargs["born_on_or_after"] is None

    async def test_search_patients_converts_a_maximum_age_to_an_earliest_birth_date(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        # age <= 40 means born strictly after today minus 41 years, i.e. on or
        # after the following day — someone born exactly 41 years ago is 41.
        patients.search_patients.return_value = []
        patients.count_patients.return_value = 0

        await service.search_patients(HOSPITAL_ID, SearchPatientRequest(age_lte=40))

        expected = subtract_years(utc_today(), 41) + timedelta(days=1)
        assert patients.search_patients.await_args.kwargs["born_on_or_after"] == expected

    async def test_search_patients_leaves_age_bounds_unset_when_not_requested(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        patients.search_patients.return_value = []
        patients.count_patients.return_value = 0

        await service.search_patients(HOSPITAL_ID, SearchPatientRequest(q="rao"))

        kwargs = patients.search_patients.await_args.kwargs
        assert kwargs["born_on_or_after"] is None
        assert kwargs["born_on_or_before"] is None

    async def test_search_patients_counts_with_the_same_filters_it_searches_with(
        self,
        service: PatientService,
        patients: AsyncMock,
    ) -> None:
        patients.search_patients.return_value = []
        patients.count_patients.return_value = 0

        await service.search_patients(
            HOSPITAL_ID, SearchPatientRequest(q="rao", gender=Gender.FEMALE)
        )

        search_kwargs = patients.search_patients.await_args.kwargs
        count_kwargs = patients.count_patients.await_args.kwargs
        for name in ("term", "gender", "date_of_birth", "born_on_or_after", "born_on_or_before"):
            assert search_kwargs[name] == count_kwargs[name]

    async def test_search_patients_audits_the_search_without_recording_the_term(
        self,
        service: PatientService,
        patients: AsyncMock,
        audit_sink: RecordingAuditSink,
    ) -> None:
        # The search term is frequently a patient's name or phone number, so it
        # must not reach the audit payload (docs/07-SECURITY.md rule 10).
        patients.search_patients.return_value = []
        patients.count_patients.return_value = 0

        await service.search_patients(
            HOSPITAL_ID, SearchPatientRequest(q="Ananya"), actor_id=ACTOR_ID
        )

        event = audit_sink.last()
        assert event.action == "patient.searched"
        assert event.actor_id == ACTOR_ID
        assert "Ananya" not in str(event.context)
        assert event.context["filters_used"] == ["term"]

    async def test_search_patients_does_not_commit(
        self,
        service: PatientService,
        patients: AsyncMock,
        fake_session: FakeSession,
    ) -> None:
        # A read has nothing to commit.
        patients.search_patients.return_value = []
        patients.count_patients.return_value = 0

        await service.search_patients(HOSPITAL_ID, SearchPatientRequest(q="rao"))

        assert fake_session.commits == 0


class TestValidatePatientData:
    """Business-rule validation reachable from any caller."""

    def test_validate_patient_data_accepts_a_valid_payload(
        self,
        service: PatientService,
    ) -> None:
        service.validate_patient_data(build_create_patient_request())

    def test_validate_patient_data_reports_every_broken_rule_at_once(
        self,
        service: PatientService,
    ) -> None:
        # Returning one error at a time makes a receptionist fix a form four
        # times instead of once.
        payload = CreatePatientRequest.model_construct(
            first_name="  ",
            last_name="Rao",
            date_of_birth=date(utc_today().year + 1, 1, 1),
            gender=Gender.MALE,
            phone="98123",
            allergies=[],
            chronic_conditions=[],
            current_medications=[],
        )

        with pytest.raises(ValidationError) as exc_info:
            service.validate_patient_data(payload)

        fields = {error["field"] for error in exc_info.value.detail["errors"]}
        assert fields == {"first_name", "date_of_birth", "phone"}

    def test_validate_patient_data_accepts_an_update_that_omits_everything_it_checks(
        self,
        service: PatientService,
    ) -> None:
        service.validate_patient_data(build_update_patient_request(occupation="Engineer"))
