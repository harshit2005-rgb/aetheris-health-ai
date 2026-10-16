"""Integration tests for the Department module.

Real database, real repository, real service — only the audit sink and the
doctor-usage source are doubles, so that events can be asserted on and the
rule 13 guard can be driven in both directions
(``docs/11-TESTING_STRATEGY.md`` §2.4, §5).

Covers the workflow ``docs/modules/14-hospital-settings.md`` §16 lists under
"Integration tests": create → read → update → search → deactivate →
reactivate, plus the uniqueness and tenancy guarantees that only show up once
every layer is wired together.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.repositories.department_repository import DepartmentRepository
from app.schemas.common import PaginationParams
from app.schemas.department import SearchDepartmentRequest
from app.services.department_service import (
    DepartmentAlreadyActiveError,
    DepartmentInUseError,
    DepartmentNotDeactivatedError,
    DepartmentNotFoundError,
    DepartmentService,
    DuplicateDepartmentCodeError,
    DuplicateDepartmentNameError,
    NullDepartmentUsageSource,
)
from app.tests.factories import (
    build_create_department_request,
    build_update_department_request,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.tests.conftest import RecordingAuditSink

pytestmark = pytest.mark.database


class _BusyUsageSource:
    """A usage source reporting assignments, standing in for Doctor Management."""

    def __init__(self, count: int) -> None:
        self.count = count

    async def active_doctor_count(self, hospital_id: uuid.UUID, department_id: uuid.UUID) -> int:
        """Report the configured assignment count."""
        return self.count


@pytest.fixture
def service(db_session: AsyncSession, audit_sink: RecordingAuditSink) -> DepartmentService:
    """A fully wired :class:`DepartmentService` on the transactional test session."""
    return DepartmentService(
        DepartmentRepository(db_session),
        db_session,
        audit_sink,
        NullDepartmentUsageSource(),
    )


async def test_full_lifecycle(
    service: DepartmentService,
    hospital_id: uuid.UUID,
    actor_id: uuid.UUID,
    audit_sink: RecordingAuditSink,
) -> None:
    """create → read → update → search → deactivate → reactivate, end to end.

    Asserted as one test because the value is in the *sequence*: each step
    depends on the previous one's persisted state, which is exactly what a
    per-step unit test cannot cover.
    """
    # ── Create ──────────────────────────────────────────────────────────────
    created = await service.create_department(
        hospital_id,
        build_create_department_request(code="card", name="Cardiology"),
        actor_id=actor_id,
    )
    assert created.code == "CARD"
    assert created.status == "active"
    assert created.hospital_id == hospital_id

    # ── Read back ───────────────────────────────────────────────────────────
    fetched = await service.get_department_details(hospital_id, created.id)
    assert fetched.id == created.id
    assert fetched.name == "Cardiology"
    assert fetched.email == "cardiology@hospital.test"

    # ── Update ──────────────────────────────────────────────────────────────
    updated = await service.update_department(
        hospital_id,
        created.id,
        build_update_department_request(location="Block D, 1st Floor"),
        actor_id=actor_id,
    )
    assert updated.location == "Block D, 1st Floor"
    # Untouched fields survive a partial update.
    assert updated.code == "CARD"
    assert updated.name == "Cardiology"

    # The change is durable, not just returned.
    assert (
        await service.get_department_details(hospital_id, created.id)
    ).location == "Block D, 1st Floor"

    # ── Search ──────────────────────────────────────────────────────────────
    found = await service.search_departments(
        hospital_id,
        SearchDepartmentRequest(q="cardi"),
        pagination=PaginationParams(page=1, page_size=10),
        actor_id=actor_id,
    )
    assert [d.id for d in found.items] == [created.id]
    assert found.total_records == 1

    # ── Deactivate ──────────────────────────────────────────────────────────
    deactivated = await service.deactivate_department(hospital_id, created.id, actor_id=actor_id)
    assert deactivated.status == "inactive"

    # Gone from the default list, still retrievable on request.
    listed = await service.list_departments(hospital_id)
    assert listed.items == []
    assert listed.total_records == 0
    assert (
        await service.get_department_details(hospital_id, created.id, include_inactive=True)
    ).status == "inactive"

    # ── Reactivate ──────────────────────────────────────────────────────────
    reactivated = await service.activate_department(hospital_id, created.id, actor_id=actor_id)
    assert reactivated.status == "active"

    relisted = await service.list_departments(hospital_id)
    assert [d.id for d in relisted.items] == [created.id]

    # ── The audit trail records the whole story, in order ────────────────────
    assert audit_sink.actions() == [
        "department.created",
        "department.updated",
        "department.searched",
        "department.deactivated",
        "department.activated",
    ]
    assert all(event.hospital_id == hospital_id for event in audit_sink.events)
    assert all(event.actor_id == actor_id for event in audit_sink.events)


async def test_uniqueness_survives_the_full_stack(
    service: DepartmentService, hospital_id: uuid.UUID, actor_id: uuid.UUID
) -> None:
    """Duplicate code and name are refused with the database constraint behind them."""
    await service.create_department(
        hospital_id,
        build_create_department_request(code="CARD", name="Cardiology"),
        actor_id=actor_id,
    )

    with pytest.raises(DuplicateDepartmentCodeError):
        await service.create_department(
            hospital_id,
            build_create_department_request(code="CARD", name="Cardiac Sciences"),
            actor_id=actor_id,
        )

    # Case-insensitively, per rule 11.
    with pytest.raises(DuplicateDepartmentNameError):
        await service.create_department(
            hospital_id,
            build_create_department_request(code="CARD2", name="cardiology"),
            actor_id=actor_id,
        )


async def test_deactivated_department_still_holds_its_code(
    service: DepartmentService, hospital_id: uuid.UUID, actor_id: uuid.UUID
) -> None:
    """A deactivated department keeps occupying its code.

    The unique constraint applies regardless of soft-delete state, so reporting
    the code as free would produce a 500 from the database instead of a 409.
    """
    created = await service.create_department(
        hospital_id,
        build_create_department_request(code="CARD", name="Cardiology"),
        actor_id=actor_id,
    )
    await service.deactivate_department(hospital_id, created.id, actor_id=actor_id)

    with pytest.raises(DuplicateDepartmentCodeError):
        await service.create_department(
            hospital_id,
            build_create_department_request(code="CARD", name="New Cardiology"),
            actor_id=actor_id,
        )


async def test_tenant_isolation_across_every_read_path(
    db_session: AsyncSession,
    audit_sink: RecordingAuditSink,
    hospital_id: uuid.UUID,
    other_hospital_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """One hospital's department is invisible to another through every entry point."""
    service = DepartmentService(
        DepartmentRepository(db_session), db_session, audit_sink, NullDepartmentUsageSource()
    )

    mine = await service.create_department(
        hospital_id,
        build_create_department_request(code="MINE", name="Mine"),
        actor_id=actor_id,
    )

    # Direct read by exact id.
    with pytest.raises(DepartmentNotFoundError):
        await service.get_department_details(other_hospital_id, mine.id)

    # List and search.
    assert (await service.list_departments(other_hospital_id)).total_records == 0
    assert (
        await service.search_departments(other_hospital_id, SearchDepartmentRequest(q="mine"))
    ).total_records == 0

    # Writes.
    with pytest.raises(DepartmentNotFoundError):
        await service.update_department(
            other_hospital_id, mine.id, build_update_department_request(location="Hijacked")
        )
    with pytest.raises(DepartmentNotFoundError):
        await service.deactivate_department(other_hospital_id, mine.id)

    # Both tenants may hold the same code without colliding.
    theirs = await service.create_department(
        other_hospital_id,
        build_create_department_request(code="MINE", name="Mine"),
        actor_id=None,
    )
    assert theirs.id != mine.id


async def test_lifecycle_errors_are_rejected(
    service: DepartmentService, hospital_id: uuid.UUID, actor_id: uuid.UUID
) -> None:
    """Double-deactivating and double-activating are refused."""
    created = await service.create_department(
        hospital_id, build_create_department_request(), actor_id=actor_id
    )

    with pytest.raises(DepartmentAlreadyActiveError):
        await service.activate_department(hospital_id, created.id, actor_id=actor_id)

    await service.deactivate_department(hospital_id, created.id, actor_id=actor_id)

    with pytest.raises(DepartmentNotDeactivatedError):
        await service.deactivate_department(hospital_id, created.id, actor_id=actor_id)


async def test_deactivation_guard_blocks_when_doctors_assigned(
    db_session: AsyncSession,
    audit_sink: RecordingAuditSink,
    hospital_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Rule 13 through the full stack, with a usage source reporting assignments.

    This is the shape the Doctor Management adapter will have. Asserting it now
    means the Doctors PR replaces the source and leaves this test alone.
    """
    repository = DepartmentRepository(db_session)
    created = await DepartmentService(
        repository, db_session, audit_sink, NullDepartmentUsageSource()
    ).create_department(hospital_id, build_create_department_request(), actor_id=actor_id)

    # No cast or ignore needed: `_BusyUsageSource` structurally satisfies the
    # `DepartmentUsageSource` protocol, which is the whole point of the seam —
    # Doctor Management can supply its own implementation without inheriting
    # anything from this module.
    guarded = DepartmentService(repository, db_session, audit_sink, _BusyUsageSource(2))

    with pytest.raises(DepartmentInUseError) as exc:
        await guarded.deactivate_department(hospital_id, created.id, actor_id=actor_id)

    assert exc.value.detail["assigned_doctors"] == 2

    # The refusal changed nothing: the department is still active and listed.
    assert (await guarded.get_department_details(hospital_id, created.id)).status == "active"
    assert (await guarded.list_departments(hospital_id)).total_records == 1


async def test_deactivation_guard_clears_when_no_doctors_assigned(
    service: DepartmentService, hospital_id: uuid.UUID, actor_id: uuid.UUID
) -> None:
    """Rule 13's other branch: with nothing assigned, deactivation proceeds."""
    created = await service.create_department(
        hospital_id, build_create_department_request(), actor_id=actor_id
    )

    result = await service.deactivate_department(hospital_id, created.id, actor_id=actor_id)

    assert result.status == "inactive"
