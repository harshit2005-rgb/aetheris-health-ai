"""Unit tests for the department Pydantic DTOs.

Covers every validation rule in ``docs/modules/14-hospital-settings.md`` §11.
No database, no service — these assert that a malformed payload never reaches
the service layer (``docs/07-SECURITY.md``, rule 5).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.department import (
    CreateDepartmentRequest,
    DepartmentResponse,
    DepartmentSummaryResponse,
    SearchDepartmentRequest,
    UpdateDepartmentRequest,
)
from app.tests.factories import build_department_model, build_department_payload

# ── code ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("raw", ["card", "Card", "  card  ", "CARD"])
def test_code_is_uppercased_and_trimmed(raw: str) -> None:
    """Case and surrounding whitespace never create a distinct code."""
    request = CreateDepartmentRequest.model_validate(build_department_payload(code=raw))
    assert request.code == "CARD"


@pytest.mark.parametrize(
    "bad",
    [
        "C",  # too short
        "",  # empty
        "-CARD",  # must start alphanumeric
        "CA RD",  # space
        "CARD!",  # punctuation
        "C" * 21,  # too long
    ],
)
def test_invalid_code_is_rejected(bad: str) -> None:
    """Codes outside the documented pattern are refused."""
    with pytest.raises(PydanticValidationError):
        CreateDepartmentRequest.model_validate(build_department_payload(code=bad))


@pytest.mark.parametrize("ok", ["CARD", "C1", "A_B", "X-Y", "ICU2"])
def test_valid_code_shapes_are_accepted(ok: str) -> None:
    """Letters, digits, hyphens, and underscores are all allowed after the first char."""
    assert CreateDepartmentRequest.model_validate(build_department_payload(code=ok)).code == ok


# ── name ────────────────────────────────────────────────────────────────────


def test_name_is_trimmed() -> None:
    """Surrounding whitespace is stripped rather than stored."""
    request = CreateDepartmentRequest.model_validate(
        build_department_payload(name="  Cardiology  ")
    )
    assert request.name == "Cardiology"


@pytest.mark.parametrize("bad", ["", " ", "A", "  X  ", "N" * 151])
def test_invalid_name_is_rejected(bad: str) -> None:
    """A blank, single-character, or over-long name is refused."""
    with pytest.raises(PydanticValidationError):
        CreateDepartmentRequest.model_validate(build_department_payload(name=bad))


# ── email ───────────────────────────────────────────────────────────────────


def test_email_is_lowercased() -> None:
    """Addresses are normalised so two casings are not two inboxes."""
    request = CreateDepartmentRequest.model_validate(
        build_department_payload(email="Cardio@Hospital.TEST")
    )
    assert request.email == "cardio@hospital.test"


def test_blank_email_becomes_none() -> None:
    """ "Cleared" and "never set" must be the same stored state."""
    request = CreateDepartmentRequest.model_validate(build_department_payload(email="   "))
    assert request.email is None


@pytest.mark.parametrize("bad", ["not-an-email", "a@b", "a b@c.co", "@hospital.test"])
def test_invalid_email_is_rejected(bad: str) -> None:
    """Malformed addresses are refused at the boundary."""
    with pytest.raises(PydanticValidationError):
        CreateDepartmentRequest.model_validate(build_department_payload(email=bad))


# ── phone_extension ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("ok", ["204", "1-204", "0"])
def test_valid_extension_accepted(ok: str) -> None:
    """Digits and hyphens are the whole allowed alphabet."""
    request = CreateDepartmentRequest.model_validate(build_department_payload(phone_extension=ok))
    assert request.phone_extension == ok


@pytest.mark.parametrize("bad", ["ext204", "+919812345678", "20 4", "1234567890123"])
def test_invalid_extension_rejected(bad: str) -> None:
    """An extension is not a phone number and is not free text."""
    with pytest.raises(PydanticValidationError):
        CreateDepartmentRequest.model_validate(build_department_payload(phone_extension=bad))


# ── create: unknown fields ──────────────────────────────────────────────────


def test_unknown_field_is_rejected() -> None:
    """``extra="forbid"`` turns a typo or a smuggled column into a 422."""
    with pytest.raises(PydanticValidationError):
        CreateDepartmentRequest.model_validate(build_department_payload(hospital_id="x"))


def test_optional_fields_may_be_omitted() -> None:
    """Only code and name are required."""
    request = CreateDepartmentRequest.model_validate({"code": "ICU", "name": "Intensive Care"})
    assert request.description is None
    assert request.email is None
    assert request.location is None


# ── update ──────────────────────────────────────────────────────────────────


def test_empty_patch_is_rejected() -> None:
    """A PATCH with no fields is always a client bug."""
    with pytest.raises(PydanticValidationError):
        UpdateDepartmentRequest.model_validate({})


@pytest.mark.parametrize("field", ["code", "name"])
def test_explicit_null_on_non_nullable_column_is_rejected(field: str) -> None:
    """An explicit ``null`` on a NOT NULL column is a 422, not a 500."""
    with pytest.raises(PydanticValidationError) as exc:
        UpdateDepartmentRequest.model_validate({field: None})
    assert field in str(exc.value)


def test_changed_fields_returns_only_sent_fields() -> None:
    """Omitted and explicitly-set fields are different requests."""
    request = UpdateDepartmentRequest.model_validate({"location": "Block C"})
    assert request.changed_fields() == {"location": "Block C"}


def test_changed_fields_preserves_explicit_null_on_nullable_column() -> None:
    """Clearing a nullable field is a real instruction and must survive."""
    request = UpdateDepartmentRequest.model_validate({"email": None})
    assert request.changed_fields() == {"email": None}


def test_update_normalises_code_too() -> None:
    """The PATCH path applies the same normalisation as create."""
    assert UpdateDepartmentRequest.model_validate({"code": "ortho"}).code == "ORTHO"


# ── search ──────────────────────────────────────────────────────────────────


def test_blank_search_term_is_treated_as_absent() -> None:
    """A whitespace-only ``q`` is not a filter."""
    assert SearchDepartmentRequest.model_validate({"q": "   "}).q is None


def test_search_term_is_trimmed() -> None:
    """Surrounding whitespace does not change what is matched."""
    assert SearchDepartmentRequest.model_validate({"q": "  cardio "}).q == "cardio"


def test_search_defaults_exclude_inactive() -> None:
    """Deactivated departments stay out unless explicitly requested."""
    assert SearchDepartmentRequest().include_inactive is False


# ── responses ───────────────────────────────────────────────────────────────


def test_response_derives_active_status() -> None:
    """A live department reports ``active``."""
    assert DepartmentResponse.from_model(build_department_model()).status == "active"


def test_response_derives_inactive_status() -> None:
    """A soft-deleted department reports ``inactive``."""
    from datetime import UTC, datetime

    model = build_department_model(deleted_at=datetime(2026, 7, 29, tzinfo=UTC))
    assert DepartmentResponse.from_model(model).status == "inactive"


def test_summary_response_omits_detail_fields() -> None:
    """The list shape carries identity only — no description or contact detail."""
    summary = DepartmentSummaryResponse.from_model(build_department_model())
    assert set(summary.model_dump()) == {"id", "code", "name", "location", "status"}
