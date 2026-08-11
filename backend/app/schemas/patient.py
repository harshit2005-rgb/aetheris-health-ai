"""Pydantic DTOs for the Patient Management module.

Request models validate everything listed in
``docs/modules/03-patient-management.md`` §11 before a service ever sees it
(``docs/07-SECURITY.md``, rule 5). Response models are the only patient shapes
that cross the API boundary — SQLAlchemy models never do
(``docs/03-ARCHITECTURE.md`` §15, rule 7).

Structured medical history (allergies, chronic conditions, medications) is
typed here rather than accepted as free text, per module spec §4 rule 5.

Usage::

    from app.schemas.patient import CreatePatientRequest, PatientResponse

    payload = CreatePatientRequest.model_validate(body)
    response = PatientResponse.from_model(patient)
"""

from __future__ import annotations

import re

# NOTE: ``date``, ``datetime``, and ``UUID`` must be imported at runtime, not
# under TYPE_CHECKING. Pydantic resolves field annotations against the module's
# real globals when it builds each model, so a TYPE_CHECKING-only import raises
# NameError at import time. This is the same constraint the models and API
# layers carry (see backend/CLAUDE.md, "Common Pitfalls").
from datetime import date, datetime  # noqa: TC003
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any, Self
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.models.patient import BloodGroup, Gender, PatientStatus
from app.schemas.common import Page
from app.utils.datetime import age, utc_today
from app.utils.phone import is_e164, normalize

if TYPE_CHECKING:
    from app.models.patient import Patient

__all__ = [
    "MAX_PATIENT_AGE_YEARS",
    "Address",
    "Allergy",
    "AllergySeverity",
    "BloodGroup",
    "ChronicCondition",
    "CreatePatientRequest",
    "EmergencyContact",
    "Gender",
    "Medication",
    "PatientListResponse",
    "PatientResponse",
    "PatientStatus",
    "PatientSummaryResponse",
    "SearchPatientRequest",
    "UpdatePatientRequest",
]

#: Upper bound on patient age (module spec §11). A DOB further back than this
#: is a data-entry error, not a supercentenarian.
MAX_PATIENT_AGE_YEARS = 130

#: Pragmatic RFC 5322 subset: one ``@``, no spaces, a dotted domain with a
#: 2+ character TLD. Deliberately not the full grammar — the full grammar
#: accepts addresses no mail system will deliver to.
#:
#: ``pydantic.EmailStr`` would be the obvious choice, but it needs the
#: ``email-validator`` package, and new dependencies are a review decision
#: (CLAUDE.md, "What NOT to Do"). Swapping to ``EmailStr`` once that package is
#: approved is a one-line change here.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")

#: Maximum stored phone length — matches ``patients.phone VARCHAR(20)``
#: (``docs/05-DATABASE_DESIGN.md`` §2.7). Kept here rather than in
#: ``app.utils.phone`` because it is a column constraint, not a phone-format fact.
PHONE_MAX_LENGTH = 20

#: Reusable constrained string for 1–100 character names (module spec §11).
PersonName = Annotated[str, Field(min_length=1, max_length=100)]

#: Update fields whose columns are ``NOT NULL``. They are declared optional on
#: :class:`UpdatePatientRequest` so a PATCH can omit them, but sending an
#: explicit ``null`` is rejected — see
#: :meth:`UpdatePatientRequest._reject_null_for_non_nullable_columns`.
_NON_NULLABLE_UPDATE_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "date_of_birth",
        "gender",
        "allergies",
        "chronic_conditions",
        "current_medications",
    }
)


class AllergySeverity(StrEnum):
    """Clinical severity of a recorded allergy."""

    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"


def _validate_optional_email(value: str | None) -> str | None:
    """Normalize and validate an optional email address.

    Blank strings become ``None`` so that "cleared" and "never set" are the
    same state in the database rather than two states that sort differently.

    :param value: The raw email value.
    :returns: The lowercased, trimmed address, or ``None``.
    :raises ValueError: If the value is non-blank and not a valid address.
    """
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    if len(cleaned) > 200:
        msg = "Email must be at most 200 characters."
        raise ValueError(msg)
    if not _EMAIL_PATTERN.match(cleaned):
        msg = "Email is not a valid address."
        raise ValueError(msg)
    return cleaned


def _validate_optional_phone(value: str | None) -> str | None:
    """Normalize and validate an optional E.164 phone number.

    :param value: The raw phone value, possibly containing separators.
    :returns: The normalized E.164 number, or ``None`` when blank.
    :raises ValueError: If the value is non-blank and not valid E.164.
    """
    if value is None:
        return None
    if not value.strip():
        # Genuinely blank: the field was left empty. Module spec §11 allows it.
        return None
    cleaned = normalize(value)
    if not cleaned:
        # Non-blank input that normalizes to nothing ("not-a-phone") is a typo,
        # not an omission. Returning None here would silently discard what the
        # user typed and report success.
        msg = "Phone must be in E.164 format, e.g. +919812345678."
        raise ValueError(msg)
    if not is_e164(cleaned):
        msg = "Phone must be in E.164 format, e.g. +919812345678."
        raise ValueError(msg)
    if len(cleaned) > PHONE_MAX_LENGTH:
        msg = f"Phone must be at most {PHONE_MAX_LENGTH} characters."
        raise ValueError(msg)
    return cleaned


def _validate_date_of_birth(value: date) -> date:
    """Validate a date of birth against the module's bounds.

    :param value: The date of birth.
    :returns: The same value when valid.
    :raises ValueError: If the date is in the future or implies an age above
        :data:`MAX_PATIENT_AGE_YEARS`.
    """
    today = utc_today()
    if value > today:
        msg = "Date of birth cannot be in the future."
        raise ValueError(msg)
    if age(value, today) > MAX_PATIENT_AGE_YEARS:
        msg = f"Date of birth cannot be more than {MAX_PATIENT_AGE_YEARS} years ago."
        raise ValueError(msg)
    return value


# ── Nested value objects ────────────────────────────────────────────────────


class Address(BaseModel):
    """Structured postal address stored as JSONB."""

    model_config = ConfigDict(extra="forbid")

    line1: str = Field(min_length=1, max_length=200, description="Street address, line 1.")
    line2: str | None = Field(default=None, max_length=200, description="Street address, line 2.")
    city: str = Field(min_length=1, max_length=100, description="City or town.")
    state: str | None = Field(
        default=None, max_length=100, description="State, province, or region."
    )
    postal_code: str | None = Field(default=None, max_length=20, description="Postal or ZIP code.")
    country: str = Field(
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code, e.g. 'IN'.",
    )

    @field_validator("country")
    @classmethod
    def _uppercase_country(cls, value: str) -> str:
        """Normalize the country code to uppercase."""
        normalized = value.strip().upper()
        if not normalized.isalpha():
            msg = "Country must be a two-letter ISO 3166-1 alpha-2 code."
            raise ValueError(msg)
        return normalized


class EmergencyContact(BaseModel):
    """Next-of-kin contact stored as JSONB (module spec §2)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200, description="Contact's full name.")
    phone: str = Field(description="Contact phone number in E.164 form.")
    relation: str = Field(
        min_length=1,
        max_length=50,
        description="Relationship to the patient, e.g. 'husband', 'mother'.",
    )

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str) -> str:
        """Require a valid E.164 number — an emergency contact with no reachable number is useless."""
        cleaned = _validate_optional_phone(value)
        if cleaned is None:
            msg = "Emergency contact phone is required and must be in E.164 format."
            raise ValueError(msg)
        return cleaned


class Allergy(BaseModel):
    """A recorded allergy (module spec §4, rule 5)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200, description="Allergen, e.g. 'Penicillin'.")
    severity: AllergySeverity = Field(
        default=AllergySeverity.MODERATE,
        description="Clinical severity: mild, moderate, or severe.",
    )
    reaction: str | None = Field(
        default=None, max_length=500, description="Observed reaction, e.g. 'hives'."
    )
    noted_on: date | None = Field(default=None, description="Date the allergy was recorded.")


class ChronicCondition(BaseModel):
    """A long-term diagnosis carried on the patient record."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1, max_length=200, description="Condition, e.g. 'Type 2 Diabetes'."
    )
    since_year: int | None = Field(
        default=None,
        ge=1900,
        description="Calendar year of onset or diagnosis.",
    )
    notes: str | None = Field(default=None, max_length=1000, description="Additional context.")

    @field_validator("since_year")
    @classmethod
    def _not_in_future(cls, value: int | None) -> int | None:
        """Reject an onset year later than the current year."""
        if value is not None and value > utc_today().year:
            msg = "Condition onset year cannot be in the future."
            raise ValueError(msg)
        return value


class Medication(BaseModel):
    """A medication the patient is currently taking."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1, max_length=200, description="Medication name, e.g. 'Metformin'."
    )
    dosage: str | None = Field(default=None, max_length=100, description="Dose, e.g. '500mg'.")
    frequency: str | None = Field(
        default=None, max_length=100, description="Schedule, e.g. 'twice daily'."
    )
    started_on: date | None = Field(default=None, description="Date the medication was started.")


# ── Requests ────────────────────────────────────────────────────────────────


class CreatePatientRequest(BaseModel):
    """Payload for ``POST /api/v1/patients`` (module spec §9).

    ``mrn`` is deliberately absent: it is generated server-side per hospital
    (module spec §4, rule 1) and must not be client-supplied.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "first_name": "Ananya",
                "last_name": "Rao",
                "date_of_birth": "1988-03-14",
                "gender": "female",
                "phone": "+919812345678",
                "email": "ananya@example.com",
                "blood_group": "B+",
                "address": {
                    "line1": "12, MG Road",
                    "city": "Hyderabad",
                    "state": "TS",
                    "postal_code": "500001",
                    "country": "IN",
                },
                "emergency_contact": {
                    "name": "Ravi Rao",
                    "phone": "+919812340001",
                    "relation": "husband",
                },
                "allergies": [{"name": "Penicillin", "severity": "moderate"}],
                "chronic_conditions": [{"name": "Type 2 Diabetes", "since_year": 2019}],
                "current_medications": [
                    {"name": "Metformin", "dosage": "500mg", "frequency": "twice daily"}
                ],
            },
        },
    )

    first_name: PersonName = Field(description="Patient's given name.")
    last_name: PersonName = Field(description="Patient's family name.")
    date_of_birth: date = Field(description="Date of birth (ISO 8601 date).")
    gender: Gender = Field(description="male, female, other, or unspecified.")
    blood_group: BloodGroup | None = Field(default=None, description="ABO/Rh blood group.")
    phone: str | None = Field(default=None, description="Contact phone in E.164 form.")
    email: str | None = Field(default=None, description="Contact email address.")
    address: Address | None = Field(default=None, description="Structured postal address.")
    emergency_contact: EmergencyContact | None = Field(
        default=None, description="Next-of-kin contact."
    )
    marital_status: str | None = Field(default=None, max_length=20, description="Marital status.")
    occupation: str | None = Field(
        default=None, max_length=100, description="Patient's occupation."
    )
    allergies: list[Allergy] = Field(default_factory=list, description="Known allergies.")
    chronic_conditions: list[ChronicCondition] = Field(
        default_factory=list, description="Chronic conditions."
    )
    current_medications: list[Medication] = Field(
        default_factory=list, description="Current medications."
    )
    notes: str | None = Field(
        default=None,
        max_length=5000,
        description="Administrative notes. Not clinical documentation.",
    )

    @field_validator("date_of_birth")
    @classmethod
    def _check_dob(cls, value: date) -> date:
        """Reject a future date of birth or an implausible age (module spec §11)."""
        return _validate_date_of_birth(value)

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        """Normalize to E.164 and reject anything else."""
        return _validate_optional_phone(value)

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str | None) -> str | None:
        """Normalize to lowercase and reject malformed addresses."""
        return _validate_optional_email(value)

    @field_validator("first_name", "last_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        """Trim surrounding whitespace and reject names that are only whitespace."""
        stripped = value.strip()
        if not stripped:
            msg = "Name must not be blank."
            raise ValueError(msg)
        return stripped


class UpdatePatientRequest(BaseModel):
    """Payload for ``PATCH /api/v1/patients/{id}`` (module spec §9).

    Every field is optional; only fields actually present in the request body
    are applied. ``mrn`` and ``hospital_id`` are immutable and are not
    accepted — ``extra="forbid"`` turns an attempt to set them into a 422
    rather than a silent no-op.
    """

    model_config = ConfigDict(extra="forbid")

    first_name: PersonName | None = Field(default=None, description="Patient's given name.")
    last_name: PersonName | None = Field(default=None, description="Patient's family name.")
    date_of_birth: date | None = Field(default=None, description="Date of birth (ISO 8601 date).")
    gender: Gender | None = Field(default=None, description="male, female, other, or unspecified.")
    blood_group: BloodGroup | None = Field(default=None, description="ABO/Rh blood group.")
    phone: str | None = Field(default=None, description="Contact phone in E.164 form.")
    email: str | None = Field(default=None, description="Contact email address.")
    address: Address | None = Field(default=None, description="Structured postal address.")
    emergency_contact: EmergencyContact | None = Field(
        default=None, description="Next-of-kin contact."
    )
    marital_status: str | None = Field(default=None, max_length=20, description="Marital status.")
    occupation: str | None = Field(
        default=None, max_length=100, description="Patient's occupation."
    )
    allergies: list[Allergy] | None = Field(default=None, description="Replaces the allergy list.")
    chronic_conditions: list[ChronicCondition] | None = Field(
        default=None, description="Replaces the chronic condition list."
    )
    current_medications: list[Medication] | None = Field(
        default=None, description="Replaces the medication list."
    )
    notes: str | None = Field(default=None, max_length=5000, description="Administrative notes.")

    @field_validator("date_of_birth")
    @classmethod
    def _check_dob(cls, value: date | None) -> date | None:
        """Reject a future date of birth or an implausible age (module spec §11)."""
        return _validate_date_of_birth(value) if value is not None else None

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        """Normalize to E.164 and reject anything else."""
        return _validate_optional_phone(value)

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str | None) -> str | None:
        """Normalize to lowercase and reject malformed addresses."""
        return _validate_optional_email(value)

    @field_validator("first_name", "last_name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        """Trim surrounding whitespace and reject names that are only whitespace."""
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            msg = "Name must not be blank."
            raise ValueError(msg)
        return stripped

    @model_validator(mode="after")
    def _reject_empty_patch(self) -> Self:
        """Reject a PATCH body with no fields — it is always a client bug."""
        if not self.model_fields_set:
            msg = "Update request must contain at least one field."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _reject_null_for_non_nullable_columns(self) -> Self:
        """Reject an explicit ``null`` on a column the database requires.

        Every field here is ``| None`` so that it can be *omitted*, but the
        underlying columns are ``NOT NULL``. Without this check,
        ``PATCH {"first_name": null}`` would reach the database and come back
        as a 500 IntegrityError instead of a 422 naming the field.
        """
        offenders = sorted(
            name
            for name in _NON_NULLABLE_UPDATE_FIELDS & self.model_fields_set
            if getattr(self, name) is None
        )
        if offenders:
            msg = f"These fields cannot be set to null: {', '.join(offenders)}."
            raise ValueError(msg)
        return self

    def changed_fields(self) -> dict[str, Any]:
        """Return only the fields the client actually sent.

        Nested models are dumped to JSON-compatible primitives so the result can
        be written straight into JSONB columns.

        :returns: Mapping of column name to new value, for set fields only.
        """
        return self.model_dump(exclude_unset=True, mode="json")


class SearchPatientRequest(BaseModel):
    """Query parameters for ``GET /api/v1/patients`` (module spec §9).

    ``q`` is the single free-text term: it prefix-matches first and last name
    case-insensitively, and exact-matches MRN and phone (module spec §5.5).
    """

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(
        default=None,
        max_length=100,
        description="Free-text term: name prefix, exact MRN, or exact phone.",
    )
    gender: Gender | None = Field(default=None, description="Filter by gender.")
    date_of_birth: date | None = Field(default=None, description="Filter by exact date of birth.")
    age_gte: int | None = Field(
        default=None, ge=0, le=MAX_PATIENT_AGE_YEARS, description="Minimum age in years."
    )
    age_lte: int | None = Field(
        default=None, ge=0, le=MAX_PATIENT_AGE_YEARS, description="Maximum age in years."
    )
    include_inactive: bool = Field(
        default=False,
        description="Include deactivated (soft-deleted) patients. Requires patient.delete.",
    )

    @field_validator("q")
    @classmethod
    def _strip_q(cls, value: str | None) -> str | None:
        """Trim the search term and treat a blank term as absent."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def _check_age_range(self) -> Self:
        """Reject an inverted age range rather than silently returning nothing."""
        if self.age_gte is not None and self.age_lte is not None and self.age_gte > self.age_lte:
            msg = "age_gte must be less than or equal to age_lte."
            raise ValueError(msg)
        return self


# ── Responses ───────────────────────────────────────────────────────────────


class PatientSummaryResponse(BaseModel):
    """Compact patient shape for list views and cross-module references.

    Carries no medical history — list endpoints and other modules do not need
    it, and not sending it keeps clinical data out of responses that only
    needed an identity.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Patient UUID.")
    mrn: str = Field(description="Medical Record Number, unique per hospital.")
    first_name: str = Field(description="Patient's given name.")
    last_name: str = Field(description="Patient's family name.")
    full_name: str = Field(description="Convenience concatenation of first and last name.")
    date_of_birth: date = Field(description="Date of birth.")
    age: int = Field(description="Age in completed years, computed at response time.")
    gender: Gender = Field(description="Patient gender.")
    phone: str | None = Field(description="Contact phone in E.164 form.")
    status: PatientStatus = Field(description="active or inactive (derived from soft delete).")

    @classmethod
    def from_model(cls, patient: Patient) -> Self:
        """Build a summary DTO from an ORM instance.

        :param patient: The ORM instance to convert.
        :returns: The populated DTO.
        """
        return cls(
            id=patient.id,
            mrn=patient.mrn,
            first_name=patient.first_name,
            last_name=patient.last_name,
            full_name=patient.full_name,
            date_of_birth=patient.date_of_birth,
            age=age(patient.date_of_birth),
            gender=patient.gender,
            phone=patient.phone,
            status=patient.status,
        )


class PatientResponse(BaseModel):
    """Full patient record returned by create, get, and update (module spec §9)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Patient UUID.")
    hospital_id: UUID = Field(description="Owning hospital (tenant) UUID.")
    mrn: str = Field(description="Medical Record Number, unique per hospital.")
    first_name: str = Field(description="Patient's given name.")
    last_name: str = Field(description="Patient's family name.")
    date_of_birth: date = Field(description="Date of birth.")
    gender: Gender = Field(description="Patient gender.")
    blood_group: str | None = Field(description="ABO/Rh blood group.")
    phone: str | None = Field(description="Contact phone in E.164 form.")
    email: str | None = Field(description="Contact email address.")
    address: dict[str, Any] | None = Field(description="Structured postal address.")
    emergency_contact: dict[str, Any] | None = Field(description="Next-of-kin contact.")
    marital_status: str | None = Field(description="Marital status.")
    occupation: str | None = Field(description="Patient's occupation.")
    allergies: list[dict[str, Any]] = Field(description="Known allergies.")
    chronic_conditions: list[dict[str, Any]] = Field(description="Chronic conditions.")
    current_medications: list[dict[str, Any]] = Field(description="Current medications.")
    notes: str | None = Field(description="Administrative notes.")
    status: PatientStatus = Field(description="active or inactive (derived from soft delete).")
    created_at: datetime = Field(description="Creation timestamp (UTC).")
    updated_at: datetime = Field(description="Last update timestamp (UTC).")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def full_name(self) -> str:
        """Convenience concatenation of first and last name."""
        return f"{self.first_name} {self.last_name}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def age(self) -> int:
        """Age in completed years, computed at response time."""
        return age(self.date_of_birth)

    @classmethod
    def from_model(cls, patient: Patient) -> Self:
        """Build a full DTO from an ORM instance.

        :param patient: The ORM instance to convert.
        :returns: The populated DTO.
        """
        return cls.model_validate(patient)


#: One page of patient summaries — the body of a list or search response.
PatientListResponse = Page[PatientSummaryResponse]
