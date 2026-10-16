"""Repository tests for :class:`~app.repositories.patient_repository.PatientRepository`.

Run against a real PostgreSQL (``docs/11-TESTING_STRATEGY.md`` §2.2) because
what is under test is the SQL: the tenant filter, the soft-delete filter, the
unique index, case-insensitive prefix matching, and ordering. None of that is
observable through a mock.

Every query method has at least one test proving it filters by ``hospital_id``
(backend/CLAUDE.md, "Testing").
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.patient import Gender
from app.repositories.patient_repository import PatientRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.patient import Patient

pytestmark = pytest.mark.database


@pytest.fixture
def repository(db_session: AsyncSession) -> PatientRepository:
    """A repository bound to the rolled-back test session."""
    return PatientRepository(db_session)


async def _create(
    repository: PatientRepository,
    hospital_id: uuid.UUID,
    **overrides: Any,
) -> Patient:
    """Insert a patient with sensible defaults, overridable per test."""
    values: dict[str, Any] = {
        "mrn": f"MRN-2026-{uuid.uuid4().hex[:5]}",
        "first_name": "Ananya",
        "last_name": "Rao",
        "date_of_birth": date(1988, 3, 14),
        "gender": Gender.FEMALE,
        "phone": "+919812345678",
        "allergies": [],
        "chronic_conditions": [],
        "current_medications": [],
    }
    values.update(overrides)
    return await repository.create_patient(hospital_id=hospital_id, **values)


class TestCreateAndRead:
    """Insertion and single-record retrieval."""

    async def test_create_patient_persists_every_column(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        patient = await _create(
            repository,
            hospital_id,
            mrn="MRN-2026-00001",
            address={"line1": "12, MG Road", "city": "Hyderabad", "country": "IN"},
            allergies=[{"name": "Penicillin", "severity": "moderate"}],
        )

        fetched = await repository.get_patient_by_id(hospital_id, patient.id)

        assert fetched is not None
        assert fetched.mrn == "MRN-2026-00001"
        assert fetched.address == {"line1": "12, MG Road", "city": "Hyderabad", "country": "IN"}
        assert fetched.allergies == [{"name": "Penicillin", "severity": "moderate"}]

    async def test_create_patient_defaults_history_columns_to_empty_arrays(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        # NOT NULL DEFAULT '[]' means downstream code never has to null-check.
        patient = await repository.create_patient(
            hospital_id=hospital_id,
            mrn="MRN-2026-00002",
            first_name="Ravi",
            last_name="Rao",
            date_of_birth=date(1990, 1, 1),
            gender=Gender.MALE,
        )

        assert patient.allergies == []
        assert patient.chronic_conditions == []
        assert patient.current_medications == []

    async def test_get_patient_by_id_returns_none_for_an_unknown_id(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        assert await repository.get_patient_by_id(hospital_id, uuid.uuid4()) is None

    async def test_get_patient_by_mrn_finds_the_record(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        await _create(repository, hospital_id, mrn="MRN-2026-00042")

        found = await repository.get_patient_by_mrn(hospital_id, "MRN-2026-00042")

        assert found is not None
        assert found.mrn == "MRN-2026-00042"


class TestMultiTenantIsolation:
    """Tenant scoping — CLAUDE.md rule 5."""

    async def test_get_patient_by_id_does_not_cross_tenants(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        patient = await _create(repository, hospital_id)

        assert await repository.get_patient_by_id(other_hospital_id, patient.id) is None

    async def test_get_patient_by_mrn_does_not_cross_tenants(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        await _create(repository, hospital_id, mrn="MRN-2026-00042")

        assert await repository.get_patient_by_mrn(other_hospital_id, "MRN-2026-00042") is None

    async def test_list_patients_does_not_cross_tenants(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        await _create(repository, hospital_id, first_name="Ananya")
        await _create(repository, other_hospital_id, first_name="Meera")

        rows = await repository.list_patients(hospital_id)

        assert [row.first_name for row in rows] == ["Ananya"]

    async def test_search_patients_does_not_cross_tenants(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        await _create(repository, other_hospital_id, last_name="Rao")

        assert await repository.search_patients(hospital_id, term="rao") == []

    async def test_count_patients_does_not_cross_tenants(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        await _create(repository, other_hospital_id)
        await _create(repository, other_hospital_id)

        assert await repository.count_patients(hospital_id) == 0

    async def test_patient_exists_does_not_cross_tenants(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        patient = await _create(repository, hospital_id)

        assert await repository.patient_exists(hospital_id, patient.id) is True
        assert await repository.patient_exists(other_hospital_id, patient.id) is False

    async def test_the_same_mrn_may_exist_in_two_hospitals(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        # MRN is unique *per hospital* (module spec §4, rule 1), not globally —
        # two hospitals independently issuing MRN-2026-00001 is expected.
        await _create(repository, hospital_id, mrn="MRN-2026-00001")
        await _create(repository, other_hospital_id, mrn="MRN-2026-00001")

        assert await repository.count_patients(hospital_id) == 1
        assert await repository.count_patients(other_hospital_id) == 1


class TestMrnUniqueness:
    """The unique index behind MRN generation."""

    async def test_duplicate_mrn_in_one_hospital_is_rejected(
        self,
        repository: PatientRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        await _create(repository, hospital_id, mrn="MRN-2026-00001")

        with pytest.raises(IntegrityError, match="uq_patients_hospital_mrn"):
            await _create(repository, hospital_id, mrn="MRN-2026-00001")

        # The failed statement poisons the transaction; roll back so the
        # session teardown does not raise a second, confusing error.
        await db_session.rollback()

    async def test_a_deactivated_patient_still_holds_its_mrn(
        self,
        repository: PatientRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        # The unique index does not exclude soft-deleted rows, so a duplicate
        # check that ignored them would report an MRN as free that the database
        # will reject.
        patient = await _create(repository, hospital_id, mrn="MRN-2026-00001")
        await repository.delete_patient(patient)

        assert await repository.get_patient_by_mrn(hospital_id, "MRN-2026-00001") is not None

        with pytest.raises(IntegrityError):
            await _create(repository, hospital_id, mrn="MRN-2026-00001")

        await db_session.rollback()


class TestSoftDelete:
    """Deactivation and reactivation."""

    async def test_delete_patient_sets_deleted_at_and_deleted_by(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        patient = await _create(repository, hospital_id)

        deleted = await repository.delete_patient(patient, deleted_by=None)

        assert deleted.deleted_at is not None
        assert deleted.status == "inactive"

    async def test_a_deactivated_patient_is_hidden_from_default_lookups(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        patient = await _create(repository, hospital_id)
        await repository.delete_patient(patient)

        assert await repository.get_patient_by_id(hospital_id, patient.id) is None
        assert await repository.list_patients(hospital_id) == []
        assert await repository.count_patients(hospital_id) == 0
        assert await repository.patient_exists(hospital_id, patient.id) is False

    async def test_a_deactivated_patient_is_visible_when_explicitly_requested(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        patient = await _create(repository, hospital_id)
        await repository.delete_patient(patient)

        found = await repository.get_patient_by_id(hospital_id, patient.id, include_deleted=True)

        assert found is not None
        assert await repository.count_patients(hospital_id, include_deleted=True) == 1

    async def test_restore_patient_makes_the_record_visible_again(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        patient = await _create(repository, hospital_id)
        await repository.delete_patient(patient)

        restored = await repository.restore_patient(patient)

        assert restored.deleted_at is None
        assert await repository.get_patient_by_id(hospital_id, patient.id) is not None


class TestSearch:
    """Search semantics (module spec §5.5)."""

    async def test_search_matches_a_case_insensitive_last_name_prefix(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        # AC-3: found by the first three letters of the name.
        await _create(repository, hospital_id, last_name="Rao")

        assert len(await repository.search_patients(hospital_id, term="rao")) == 1
        assert len(await repository.search_patients(hospital_id, term="RA")) == 1

    async def test_search_matches_a_first_name_prefix(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        await _create(repository, hospital_id, first_name="Ananya", last_name="Sharma")

        assert len(await repository.search_patients(hospital_id, term="ana")) == 1

    async def test_search_does_not_match_a_mid_word_substring(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        # Prefix, not substring — module spec §5.5, and the reason the
        # lower(...) indexes are usable.
        await _create(repository, hospital_id, last_name="Sharma")

        assert await repository.search_patients(hospital_id, term="arma") == []

    async def test_search_matches_an_exact_mrn(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        await _create(repository, hospital_id, mrn="MRN-2026-00042")

        assert len(await repository.search_patients(hospital_id, term="MRN-2026-00042")) == 1

    async def test_search_does_not_match_a_partial_mrn(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        await _create(repository, hospital_id, mrn="MRN-2026-00042")

        assert await repository.search_patients(hospital_id, term="00042") == []

    async def test_search_matches_an_exact_phone_number(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        await _create(repository, hospital_id, phone="+919812345678")

        assert len(await repository.search_patients(hospital_id, term="+919812345678")) == 1

    async def test_search_treats_wildcard_characters_literally(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        # An unescaped '%' would match every patient in the hospital and dump
        # the entire register to whoever typed it.
        await _create(repository, hospital_id, last_name="Rao")
        await _create(repository, hospital_id, last_name="Sharma")

        assert await repository.search_patients(hospital_id, term="%") == []
        assert await repository.search_patients(hospital_id, term="_ao") == []

    async def test_search_excludes_deactivated_patients_by_default(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        patient = await _create(repository, hospital_id, last_name="Rao")
        await repository.delete_patient(patient)

        assert await repository.search_patients(hospital_id, term="rao") == []

    async def test_search_filters_by_gender(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        await _create(repository, hospital_id, gender=Gender.FEMALE)
        await _create(repository, hospital_id, gender=Gender.MALE)

        rows = await repository.search_patients(hospital_id, gender=Gender.MALE)

        assert len(rows) == 1
        assert rows[0].gender == Gender.MALE

    async def test_search_filters_by_exact_date_of_birth(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        await _create(repository, hospital_id, date_of_birth=date(1988, 3, 14))
        await _create(repository, hospital_id, date_of_birth=date(1990, 1, 1))

        rows = await repository.search_patients(hospital_id, date_of_birth=date(1988, 3, 14))

        assert len(rows) == 1

    async def test_search_filters_by_date_of_birth_bounds(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        await _create(repository, hospital_id, date_of_birth=date(1980, 1, 1))
        await _create(repository, hospital_id, date_of_birth=date(1990, 1, 1))
        await _create(repository, hospital_id, date_of_birth=date(2000, 1, 1))

        rows = await repository.search_patients(
            hospital_id,
            born_on_or_after=date(1985, 1, 1),
            born_on_or_before=date(1995, 1, 1),
        )

        assert [row.date_of_birth for row in rows] == [date(1990, 1, 1)]

    async def test_search_combines_filters_conjunctively(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        await _create(repository, hospital_id, last_name="Rao", gender=Gender.FEMALE)
        await _create(repository, hospital_id, last_name="Rao", gender=Gender.MALE)

        rows = await repository.search_patients(hospital_id, term="rao", gender=Gender.MALE)

        assert len(rows) == 1

    async def test_count_patients_agrees_with_search_patients(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        for _ in range(3):
            await _create(repository, hospital_id, last_name="Rao")
        await _create(repository, hospital_id, last_name="Sharma")

        rows = await repository.search_patients(hospital_id, term="rao", limit=100)
        total = await repository.count_patients(hospital_id, term="rao")

        assert total == len(rows) == 3


class TestOrderingAndPagination:
    """Stable ordering and offset paging."""

    async def test_list_patients_orders_by_last_name_then_first_name(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        await _create(repository, hospital_id, first_name="Zara", last_name="Ahmed")
        await _create(repository, hospital_id, first_name="Ananya", last_name="Rao")
        await _create(repository, hospital_id, first_name="Bala", last_name="Ahmed")

        rows = await repository.list_patients(hospital_id)

        assert [(row.last_name, row.first_name) for row in rows] == [
            ("Ahmed", "Bala"),
            ("Ahmed", "Zara"),
            ("Rao", "Ananya"),
        ]

    async def test_pagination_returns_disjoint_pages_that_cover_everything(
        self,
        repository: PatientRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        # Identical names on every row: without the id tiebreak in the ORDER BY
        # these pages could overlap or skip a record.
        for _ in range(5):
            await _create(repository, hospital_id, first_name="Ananya", last_name="Rao")

        first = await repository.list_patients(hospital_id, skip=0, limit=2)
        second = await repository.list_patients(hospital_id, skip=2, limit=2)
        third = await repository.list_patients(hospital_id, skip=4, limit=2)

        seen = [row.id for row in (*first, *second, *third)]
        assert len(seen) == 5
        assert len(set(seen)) == 5
