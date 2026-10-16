"""Factories for department test data.

Every factory returns a *valid* object by default. Tests that need an invalid
one override exactly the field under test, so the failure a test asserts on is
unambiguously the one it set up.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.department import Department
from app.schemas.department import CreateDepartmentRequest, UpdateDepartmentRequest

__all__ = [
    "build_create_department_request",
    "build_department_model",
    "build_department_payload",
    "build_update_department_request",
]


def build_department_payload(**overrides: Any) -> dict[str, Any]:
    """Build a valid ``POST /departments`` body as a plain dict.

    Use this when the test needs to exercise validation itself (passing the
    dict through ``model_validate``). Use
    :func:`build_create_department_request` when the test needs a validated
    object.

    :param overrides: Field values to replace. A value of ``None`` sets the
        field to ``None``; to *remove* a field, pop it from the result.
    :returns: A dict suitable for ``CreateDepartmentRequest.model_validate``.
    """
    payload: dict[str, Any] = {
        "code": "CARD",
        "name": "Cardiology",
        "description": "Diagnosis and treatment of heart conditions.",
        "phone_extension": "204",
        "email": "cardiology@hospital.test",
        "location": "Block B, 3rd Floor",
    }
    payload.update(overrides)
    return payload


def build_create_department_request(**overrides: Any) -> CreateDepartmentRequest:
    """Build a validated :class:`CreateDepartmentRequest`.

    :param overrides: Field values to replace in the default payload.
    :returns: The validated request model.
    """
    return CreateDepartmentRequest.model_validate(build_department_payload(**overrides))


def build_update_department_request(**fields: Any) -> UpdateDepartmentRequest:
    """Build a validated :class:`UpdateDepartmentRequest` with exactly ``fields`` set.

    Only the fields passed here count as "sent by the client", which is what
    ``PATCH`` semantics turn on — so a test that patches one field really does
    patch one field.

    :param fields: The fields the request sets. At least one is required.
    :returns: The validated request model.
    """
    return UpdateDepartmentRequest.model_validate(fields)


def build_department_model(**overrides: Any) -> Department:
    """Build an unattached :class:`~app.models.department.Department` instance.

    Columns whose values normally come from the database (``id``, timestamps)
    are populated explicitly, because an instance that has never been flushed
    has ``None`` for all of them and would fail response serialization for
    reasons that have nothing to do with the test.

    :param overrides: Column values to replace.
    :returns: A detached Department suitable for unit tests.
    """
    now = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "hospital_id": uuid.uuid4(),
        "code": "CARD",
        "name": "Cardiology",
        "description": "Diagnosis and treatment of heart conditions.",
        "phone_extension": "204",
        "email": "cardiology@hospital.test",
        "location": "Block B, 3rd Floor",
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    values.update(overrides)
    return Department(**values)
