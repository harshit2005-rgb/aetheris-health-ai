"""Factories for patient test data.

Every factory returns a *valid* object by default. Tests that need an invalid
one override exactly the field under test, so the failure a test asserts on is
unambiguously the one it set up.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from app.models.patient import Gender, Patient
from app.schemas.patient import CreatePatientRequest, UpdatePatientRequest

__all__ = [
    "build_create_patient_request",
    "build_patient_model",
    "build_patient_payload",
    "build_update_patient_request",
]

#: Fixed date of birth so age-dependent assertions are stable across runs.
DEFAULT_DATE_OF_BIRTH = date(1988, 3, 14)


def build_patient_payload(**overrides: Any) -> dict[str, Any]:
    """Build a valid ``POST /patients`` body as a plain dict.

    Use this when the test needs to exercise validation itself (passing the
    dict through ``model_validate``). Use
    :func:`build_create_patient_request` when the test needs a validated
    object.

    :param overrides: Field values to replace. A value of ``None`` sets the
        field to ``None``; to *remove* a field, pop it from the result.
    :returns: A dict suitable for ``CreatePatientRequest.model_validate``.
    """
    payload: dict[str, Any] = {
        "first_name": "Ananya",
        "last_name": "Rao",
        "date_of_birth": DEFAULT_DATE_OF_BIRTH.isoformat(),
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
    }
    payload.update(overrides)
    return payload


def build_create_patient_request(**overrides: Any) -> CreatePatientRequest:
    """Build a validated :class:`CreatePatientRequest`.

    :param overrides: Field values to replace in the default payload.
    :returns: The validated request model.
    """
    return CreatePatientRequest.model_validate(build_patient_payload(**overrides))


def build_patient_model(**overrides: Any) -> Patient:
    """Build an unattached :class:`~app.models.patient.Patient` ORM instance.

    Columns whose values normally come from the database (``id``, timestamps,
    JSONB defaults) are populated explicitly, because an instance that has
    never been flushed has ``None`` for all of them and would fail response
    serialization for reasons that have nothing to do with the test.

    :param overrides: Column values to replace.
    :returns: A detached Patient suitable for unit tests.
    """
    now = datetime(2026, 7, 27, 9, 0, tzinfo=UTC)
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "hospital_id": uuid.uuid4(),
        "mrn": "MRN-2026-00001",
        "first_name": "Ananya",
        "last_name": "Rao",
        "date_of_birth": DEFAULT_DATE_OF_BIRTH,
        "gender": Gender.FEMALE,
        "blood_group": "B+",
        "phone": "+919812345678",
        "email": "ananya@example.com",
        "address": {"line1": "12, MG Road", "city": "Hyderabad", "country": "IN"},
        "emergency_contact": {"name": "Ravi Rao", "phone": "+919812340001", "relation": "husband"},
        "marital_status": None,
        "occupation": None,
        "allergies": [],
        "chronic_conditions": [],
        "current_medications": [],
        "notes": None,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    values.update(overrides)
    return Patient(**values)


def build_update_patient_request(**fields: Any) -> UpdatePatientRequest:
    """Build a validated :class:`UpdatePatientRequest` with exactly ``fields`` set.

    Only the fields passed here count as "sent by the client", which is what
    ``PATCH`` semantics turn on — so a test that patches one field really does
    patch one field.

    :param fields: The fields the request sets. At least one is required.
    :returns: The validated request model.
    """
    return UpdatePatientRequest.model_validate(fields)
