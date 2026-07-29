"""Unit tests for :mod:`app.schemas.patient`.

These cover the validation rules in ``docs/modules/03-patient-management.md``
§11 at the API boundary. The same rules are re-asserted in the service layer;
see ``test_patient_service.py`` for those.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.common import Page, PaginationParams
from app.schemas.patient import (
    MAX_PATIENT_AGE_YEARS,
    CreatePatientRequest,
    PatientResponse,
    PatientStatus,
    PatientSummaryResponse,
    SearchPatientRequest,
    UpdatePatientRequest,
)
from app.tests.factories import build_patient_payload
from app.tests.factories.patient import build_patient_model
from app.utils.datetime import utc_today


class TestCreatePatientRequest:
    """Registration payload validation."""

    def test_create_request_accepts_a_complete_payload(self) -> None:
        request = CreatePatientRequest.model_validate(build_patient_payload())
        assert request.first_name == "Ananya"
        assert request.gender == "female"

    def test_create_request_accepts_only_the_mandatory_fields(self) -> None:
        # Module spec §4 rule 3: names, DOB, and gender are the required set.
        request = CreatePatientRequest.model_validate(
            {
                "first_name": "Ravi",
                "last_name": "Rao",
                "date_of_birth": "1990-01-01",
                "gender": "male",
            }
        )
        assert request.phone is None
        assert request.allergies == []

    @pytest.mark.parametrize(
        "missing",
        ["first_name", "last_name", "date_of_birth", "gender"],
    )
    def test_create_request_rejects_a_missing_mandatory_field(self, missing: str) -> None:
        payload = build_patient_payload()
        del payload[missing]
        with pytest.raises(ValidationError) as exc_info:
            CreatePatientRequest.model_validate(payload)
        assert missing in str(exc_info.value)

    def test_create_request_rejects_a_client_supplied_mrn(self) -> None:
        # MRN is generated server-side (module spec §4 rule 1). Accepting one
        # from the client would let a caller collide with an existing record.
        with pytest.raises(ValidationError, match="mrn"):
            CreatePatientRequest.model_validate(build_patient_payload(mrn="MRN-2026-00001"))

    def test_create_request_rejects_a_client_supplied_hospital_id(self) -> None:
        # Tenancy comes from the authenticated context, never the body.
        with pytest.raises(ValidationError, match="hospital_id"):
            CreatePatientRequest.model_validate(
                build_patient_payload(hospital_id="00000000-0000-0000-0000-000000000001")
            )

    def test_create_request_rejects_a_future_date_of_birth(self) -> None:
        tomorrow = (utc_today() + timedelta(days=1)).isoformat()
        with pytest.raises(ValidationError, match="future"):
            CreatePatientRequest.model_validate(build_patient_payload(date_of_birth=tomorrow))

    def test_create_request_accepts_a_date_of_birth_of_today(self) -> None:
        # A newborn registered on the day of birth is a real workflow.
        request = CreatePatientRequest.model_validate(
            build_patient_payload(date_of_birth=utc_today().isoformat())
        )
        assert request.date_of_birth == utc_today()

    def test_create_request_rejects_an_implausible_age(self) -> None:
        ancient = date(utc_today().year - MAX_PATIENT_AGE_YEARS - 1, 1, 1).isoformat()
        with pytest.raises(ValidationError, match=str(MAX_PATIENT_AGE_YEARS)):
            CreatePatientRequest.model_validate(build_patient_payload(date_of_birth=ancient))

    def test_create_request_normalizes_a_formatted_phone_number(self) -> None:
        request = CreatePatientRequest.model_validate(
            build_patient_payload(phone="+91 98123-45678")
        )
        assert request.phone == "+919812345678"

    def test_create_request_promotes_a_bare_indian_mobile_to_e164(self) -> None:
        # app.utils.phone.normalize is India-aware: a bare 10-digit mobile is a
        # valid entry at an Indian hospital reception desk, so it is promoted to
        # +91 rather than rejected.
        request = CreatePatientRequest.model_validate(build_patient_payload(phone="9812345678"))
        assert request.phone == "+919812345678"

    @pytest.mark.parametrize(
        "phone",
        ["12345", "098123456780000", "not-a-phone"],
        ids=["too_short", "too_long", "letters"],
    )
    def test_create_request_rejects_a_phone_that_cannot_be_normalized(self, phone: str) -> None:
        with pytest.raises(ValidationError, match="E.164"):
            CreatePatientRequest.model_validate(build_patient_payload(phone=phone))

    def test_create_request_treats_a_blank_phone_as_absent(self) -> None:
        # Module spec §11: "E.164 or blank". Blank must land as NULL, not "".
        request = CreatePatientRequest.model_validate(build_patient_payload(phone="   "))
        assert request.phone is None

    def test_create_request_lowercases_email(self) -> None:
        request = CreatePatientRequest.model_validate(
            build_patient_payload(email="Ananya@Example.COM")
        )
        assert request.email == "ananya@example.com"

    @pytest.mark.parametrize(
        "email",
        ["not-an-email", "missing@domain", "two@@at.com", "spaces in@example.com"],
        ids=["no_at", "no_tld", "double_at", "internal_space"],
    )
    def test_create_request_rejects_a_malformed_email(self, email: str) -> None:
        with pytest.raises(ValidationError, match="valid address"):
            CreatePatientRequest.model_validate(build_patient_payload(email=email))

    def test_create_request_rejects_a_blank_name(self) -> None:
        with pytest.raises(ValidationError):
            CreatePatientRequest.model_validate(build_patient_payload(first_name="   "))

    def test_create_request_trims_surrounding_whitespace_from_names(self) -> None:
        request = CreatePatientRequest.model_validate(build_patient_payload(first_name="  Ananya "))
        assert request.first_name == "Ananya"

    def test_create_request_rejects_a_name_over_one_hundred_characters(self) -> None:
        with pytest.raises(ValidationError):
            CreatePatientRequest.model_validate(build_patient_payload(first_name="A" * 101))

    def test_create_request_accepts_a_unicode_name(self) -> None:
        # Module spec §14: long and non-Latin names are explicitly allowed.
        request = CreatePatientRequest.model_validate(build_patient_payload(first_name="अनन्या"))
        assert request.first_name == "अनन्या"

    @pytest.mark.parametrize("gender", ["male", "female", "other", "unspecified"])
    def test_create_request_accepts_every_approved_gender(self, gender: str) -> None:
        request = CreatePatientRequest.model_validate(build_patient_payload(gender=gender))
        assert request.gender == gender

    def test_create_request_rejects_an_unapproved_gender(self) -> None:
        with pytest.raises(ValidationError):
            CreatePatientRequest.model_validate(build_patient_payload(gender="f"))

    def test_create_request_rejects_an_unapproved_blood_group(self) -> None:
        with pytest.raises(ValidationError):
            CreatePatientRequest.model_validate(build_patient_payload(blood_group="C+"))

    def test_create_request_uppercases_the_country_code(self) -> None:
        payload = build_patient_payload()
        payload["address"]["country"] = "in"
        request = CreatePatientRequest.model_validate(payload)
        assert request.address is not None
        assert request.address.country == "IN"

    def test_create_request_rejects_an_emergency_contact_without_a_valid_phone(self) -> None:
        payload = build_patient_payload()
        payload["emergency_contact"]["phone"] = "98123"
        with pytest.raises(ValidationError, match="E.164"):
            CreatePatientRequest.model_validate(payload)

    def test_create_request_rejects_an_allergy_without_a_name(self) -> None:
        # Structured history means typed objects, not free text (spec §4 rule 5).
        with pytest.raises(ValidationError):
            CreatePatientRequest.model_validate(
                build_patient_payload(allergies=[{"severity": "severe"}])
            )

    def test_create_request_rejects_an_allergy_with_an_unknown_severity(self) -> None:
        with pytest.raises(ValidationError):
            CreatePatientRequest.model_validate(
                build_patient_payload(allergies=[{"name": "Penicillin", "severity": "fatal"}])
            )

    def test_create_request_defaults_allergy_severity_to_moderate(self) -> None:
        request = CreatePatientRequest.model_validate(
            build_patient_payload(allergies=[{"name": "Penicillin"}])
        )
        assert request.allergies[0].severity == "moderate"

    def test_create_request_rejects_a_condition_starting_in_the_future(self) -> None:
        with pytest.raises(ValidationError, match="future"):
            CreatePatientRequest.model_validate(
                build_patient_payload(
                    chronic_conditions=[{"name": "Asthma", "since_year": utc_today().year + 1}]
                )
            )

    def test_create_request_rejects_an_unknown_field(self) -> None:
        # extra="forbid" turns a typo'd field into a 422 rather than a silently
        # ignored value the caller believes was saved.
        with pytest.raises(ValidationError):
            CreatePatientRequest.model_validate(build_patient_payload(favourite_colour="blue"))


class TestUpdatePatientRequest:
    """Partial-update payload validation."""

    def test_update_request_records_only_the_fields_that_were_sent(self) -> None:
        request = UpdatePatientRequest.model_validate({"phone": "+919812349999"})
        assert request.changed_fields() == {"phone": "+919812349999"}

    def test_update_request_distinguishes_an_explicit_null_from_an_absent_field(self) -> None:
        # Clearing a phone number and not mentioning it are different requests.
        cleared = UpdatePatientRequest.model_validate({"phone": None})
        assert cleared.changed_fields() == {"phone": None}

        untouched = UpdatePatientRequest.model_validate({"first_name": "Ravi"})
        assert "phone" not in untouched.changed_fields()

    def test_update_request_rejects_an_empty_body(self) -> None:
        with pytest.raises(ValidationError, match="at least one field"):
            UpdatePatientRequest.model_validate({})

    @pytest.mark.parametrize(
        "field",
        [
            "first_name",
            "last_name",
            "date_of_birth",
            "gender",
            "allergies",
            "chronic_conditions",
            "current_medications",
        ],
    )
    def test_update_request_rejects_an_explicit_null_on_a_required_column(self, field: str) -> None:
        # These columns are NOT NULL. Letting the null through would surface as
        # a 500 IntegrityError instead of a 422 naming the offending field.
        with pytest.raises(ValidationError, match="cannot be set to null"):
            UpdatePatientRequest.model_validate({field: None})

    @pytest.mark.parametrize("field", ["phone", "email", "address", "blood_group", "notes"])
    def test_update_request_allows_an_explicit_null_on_an_optional_column(self, field: str) -> None:
        # Clearing a phone number or address is a legitimate edit.
        request = UpdatePatientRequest.model_validate({field: None})
        assert request.changed_fields() == {field: None}

    def test_update_request_rejects_a_change_to_mrn(self) -> None:
        # MRN is immutable: appointments, invoices, and lab reports cite it.
        with pytest.raises(ValidationError, match="mrn"):
            UpdatePatientRequest.model_validate({"mrn": "MRN-2026-99999"})

    def test_update_request_rejects_a_change_to_hospital_id(self) -> None:
        with pytest.raises(ValidationError, match="hospital_id"):
            UpdatePatientRequest.model_validate(
                {"hospital_id": "00000000-0000-0000-0000-000000000001"}
            )

    def test_update_request_rejects_a_future_date_of_birth(self) -> None:
        tomorrow = (utc_today() + timedelta(days=1)).isoformat()
        with pytest.raises(ValidationError, match="future"):
            UpdatePatientRequest.model_validate({"date_of_birth": tomorrow})

    def test_update_request_serializes_nested_objects_for_jsonb(self) -> None:
        request = UpdatePatientRequest.model_validate(
            {"allergies": [{"name": "Latex", "severity": "severe"}]}
        )
        changes = request.changed_fields()
        assert isinstance(changes["allergies"], list)
        assert changes["allergies"][0]["name"] == "Latex"


class TestSearchPatientRequest:
    """Search filter validation."""

    def test_search_request_defaults_to_active_patients_only(self) -> None:
        assert SearchPatientRequest().include_inactive is False

    def test_search_request_trims_the_term(self) -> None:
        assert SearchPatientRequest(q="  rao  ").q == "rao"

    def test_search_request_treats_a_blank_term_as_absent(self) -> None:
        assert SearchPatientRequest(q="   ").q is None

    def test_search_request_rejects_an_inverted_age_range(self) -> None:
        # Silently returning nothing would look like "no such patient".
        with pytest.raises(ValidationError, match="age_gte"):
            SearchPatientRequest(age_gte=60, age_lte=30)

    def test_search_request_accepts_an_equal_age_range(self) -> None:
        assert SearchPatientRequest(age_gte=30, age_lte=30).age_gte == 30


class TestPaginationParams:
    """Pagination bounds (``docs/06-API_STANDARDS.md`` §9)."""

    def test_pagination_defaults_to_page_one_of_twenty_five(self) -> None:
        params = PaginationParams()
        assert (params.page, params.page_size, params.offset) == (1, 25, 0)

    def test_pagination_offset_follows_the_page_number(self) -> None:
        assert PaginationParams(page=3, page_size=20).offset == 40

    def test_pagination_rejects_page_zero(self) -> None:
        with pytest.raises(ValidationError):
            PaginationParams(page=0)

    def test_pagination_rejects_a_page_size_above_the_cap(self) -> None:
        with pytest.raises(ValidationError):
            PaginationParams(page_size=101)


class TestPage:
    """Page metadata arithmetic."""

    def test_page_rounds_total_pages_up(self) -> None:
        page: Page[int] = Page[int](items=[], page=1, page_size=25, total_records=137)
        assert page.total_pages == 6

    def test_page_reports_zero_pages_for_no_records(self) -> None:
        page: Page[int] = Page[int](items=[], page=1, page_size=25, total_records=0)
        assert page.total_pages == 0


class TestPatientResponses:
    """Response DTO construction from ORM instances."""

    def test_patient_response_derives_status_from_soft_delete(self) -> None:
        active = PatientResponse.from_model(build_patient_model())
        assert active.status == PatientStatus.ACTIVE

    def test_patient_response_reports_a_soft_deleted_patient_as_inactive(self) -> None:
        deleted = build_patient_model(deleted_at=date(2026, 7, 1))
        assert PatientResponse.from_model(deleted).status == PatientStatus.INACTIVE

    def test_patient_response_computes_full_name_and_age(self) -> None:
        response = PatientResponse.from_model(build_patient_model())
        assert response.full_name == "Ananya Rao"
        assert response.age >= 38

    def test_patient_summary_omits_medical_history(self) -> None:
        # Billing staff and list views get identity, not clinical data
        # (module spec §3).
        summary = PatientSummaryResponse.from_model(build_patient_model())
        fields = set(summary.model_dump())
        assert not fields & {"allergies", "chronic_conditions", "current_medications", "notes"}
