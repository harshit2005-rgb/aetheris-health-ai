"""Test data factories.

``docs/11-TESTING_STRATEGY.md`` §4.1: never hand-roll patient JSON in tests.
Build payloads through a factory so that adding a required field breaks one
factory rather than fifty test cases.

Hand-written rather than ``polyfactory``-generated: ``polyfactory`` is not a
project dependency, and new dependencies are a review decision (CLAUDE.md,
"What NOT to Do").
"""

from app.tests.factories.patient import (
    build_create_patient_request,
    build_patient_payload,
    build_update_patient_request,
)

__all__ = [
    "build_create_patient_request",
    "build_patient_payload",
    "build_update_patient_request",
]
