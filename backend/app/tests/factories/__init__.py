"""Test data factories.

``docs/11-TESTING_STRATEGY.md`` §4.1: never hand-roll patient JSON in tests.
Build payloads through a factory so that adding a required field breaks one
factory rather than fifty test cases.

Hand-written rather than ``polyfactory``-generated: ``polyfactory`` is not a
project dependency, and new dependencies are a review decision (CLAUDE.md,
"What NOT to Do").
"""

from app.tests.factories.department import (
    build_create_department_request,
    build_department_model,
    build_department_payload,
    build_update_department_request,
)
from app.tests.factories.doctor import (
    build_availability_model,
    build_availability_payload,
    build_create_doctor_request,
    build_doctor_model,
    build_doctor_payload,
    build_leave_model,
    build_leave_payload,
    build_leave_request,
    build_set_availability_request,
    build_update_doctor_request,
)
from app.tests.factories.patient import (
    build_create_patient_request,
    build_patient_payload,
    build_update_patient_request,
)

__all__ = [
    "build_availability_model",
    "build_availability_payload",
    "build_create_department_request",
    "build_create_doctor_request",
    "build_doctor_model",
    "build_doctor_payload",
    "build_leave_model",
    "build_leave_payload",
    "build_leave_request",
    "build_set_availability_request",
    "build_update_doctor_request",
    "build_create_patient_request",
    "build_department_model",
    "build_department_payload",
    "build_patient_payload",
    "build_update_department_request",
    "build_update_patient_request",
]
