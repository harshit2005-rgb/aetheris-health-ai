"""Unit tests for :mod:`app.core.audit`.

Every other test in the suite injects the ``RecordingAuditSink`` double, so the
real :class:`~app.core.audit.StructlogAuditSink` needs its own coverage —
particularly the PII guarantee it exists to provide.

``docs/07-SECURITY.md`` rule 10 requires PII to be redacted or omitted from
logs, and a patient diff is almost entirely PII. The sink therefore logs the
*names* of changed fields and never their values. That is the property under
test here: it is a security control, not a formatting preference.
"""

from __future__ import annotations

import uuid

import pytest
from structlog.testing import capture_logs

from app.core.audit import AuditEvent, AuditSink, StructlogAuditSink

HOSPITAL_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
TARGET_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
ACTOR_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture
def sink() -> StructlogAuditSink:
    """The sink under test."""
    return StructlogAuditSink()


class TestStructlogAuditSink:
    """Emission and redaction behaviour."""

    def test_the_sink_satisfies_the_audit_sink_protocol(
        self,
        sink: StructlogAuditSink,
    ) -> None:
        # AuditSink is what services depend on; the concrete class has to
        # remain substitutable for it when the durable AuditService lands.
        assert isinstance(sink, AuditSink)

    async def test_record_emits_the_event_with_its_identifiers(
        self,
        sink: StructlogAuditSink,
    ) -> None:
        with capture_logs() as entries:
            await sink.record(
                AuditEvent(
                    action="patient.created",
                    hospital_id=HOSPITAL_ID,
                    target_type="patient",
                    target_id=TARGET_ID,
                    actor_id=ACTOR_ID,
                )
            )

        assert len(entries) == 1
        entry = entries[0]
        assert entry["event"] == "patient.created"
        assert entry["hospital_id"] == str(HOSPITAL_ID)
        assert entry["target_type"] == "patient"
        assert entry["target_id"] == str(TARGET_ID)
        assert entry["actor_id"] == str(ACTOR_ID)

    async def test_record_logs_changed_field_names_but_never_their_values(
        self,
        sink: StructlogAuditSink,
    ) -> None:
        # The PII guarantee (docs/07-SECURITY.md rule 10). The field names tell
        # an operator what was touched; the values are patient data and belong
        # only in the access-controlled audit_logs table.
        with capture_logs() as entries:
            await sink.record(
                AuditEvent(
                    action="patient.updated",
                    hospital_id=HOSPITAL_ID,
                    target_type="patient",
                    target_id=TARGET_ID,
                    actor_id=ACTOR_ID,
                    changes={
                        "phone": {"before": "+919812345678", "after": "+919812349999"},
                        "email": {"before": "ananya@example.com", "after": "a.rao@example.com"},
                    },
                )
            )

        entry = entries[0]
        assert entry["changed_fields"] == ["email", "phone"]

        # Nothing anywhere in the emitted entry carries a value.
        rendered = repr(entry)
        for secret in (
            "+919812345678",
            "+919812349999",
            "ananya@example.com",
            "a.rao@example.com",
        ):
            assert secret not in rendered

    async def test_record_passes_non_pii_context_through(
        self,
        sink: StructlogAuditSink,
    ) -> None:
        with capture_logs() as entries:
            await sink.record(
                AuditEvent(
                    action="patient.searched",
                    hospital_id=HOSPITAL_ID,
                    target_type="patient",
                    actor_id=ACTOR_ID,
                    context={"filters_used": ["term"], "result_count": 3},
                )
            )

        entry = entries[0]
        assert entry["filters_used"] == ["term"]
        assert entry["result_count"] == 3

    async def test_record_tolerates_a_system_action_with_no_actor_or_target(
        self,
        sink: StructlogAuditSink,
    ) -> None:
        # Background jobs and migrations act with no user behind them.
        with capture_logs() as entries:
            await sink.record(
                AuditEvent(
                    action="patient.searched",
                    hospital_id=HOSPITAL_ID,
                    target_type="patient",
                )
            )

        entry = entries[0]
        assert entry["actor_id"] is None
        assert entry["target_id"] is None
        assert entry["changed_fields"] == []
