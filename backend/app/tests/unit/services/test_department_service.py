"""Unit tests for :class:`~app.services.department_service.DepartmentService`.

Repositories are mocked; no database is involved
(``docs/11-TESTING_STRATEGY.md`` §2.1). Every service method gets a happy path
and an error path, and every mutation asserts the audit event fired — both
required by the backend Definition of Done.

The deactivation guard (module spec §4, rule 13) is tested through a stub
:class:`~app.services.department_service.DepartmentUsageSource` in **both**
directions: assigned doctors block, no assigned doctors let it through. When
Doctor Management supplies the real source it swaps the stub, and these tests
keep their meaning unchanged.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ValidationError
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
from app.tests.conftest import FakeSession, RecordingAuditSink
from app.tests.factories import (
    build_create_department_request,
    build_department_model,
    build_update_department_request,
)

if TYPE_CHECKING:
    from app.models.department import Department

HOSPITAL_ID = uuid.uuid4()
ACTOR_ID = uuid.uuid4()


class StubUsageSource:
    """A :class:`DepartmentUsageSource` returning a fixed assignment count.

    Stands in for the Doctor Management adapter that does not exist yet. The
    count is whatever the test needs, which is how both branches of rule 13
    become reachable before ``doctors`` is a table.
    """

    def __init__(self, count: int) -> None:
        self.count = count
        self.calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def active_doctor_count(self, hospital_id: uuid.UUID, department_id: uuid.UUID) -> int:
        """Record the call and return the configured count."""
        self.calls.append((hospital_id, department_id))
        return self.count


def _make_service(
    repo: AsyncMock,
    *,
    assigned_doctors: int = 0,
) -> tuple[DepartmentService, FakeSession, RecordingAuditSink, StubUsageSource]:
    """Assemble a service over mocked collaborators.

    :param repo: The mocked department repository.
    :param assigned_doctors: What the usage source should report.
    :returns: The service plus the doubles the tests assert against.
    """
    session = FakeSession()
    audit = RecordingAuditSink()
    usage = StubUsageSource(assigned_doctors)
    service = DepartmentService(repo, session, audit, usage)  # type: ignore[arg-type]
    return service, session, audit, usage


@pytest.fixture
def repo() -> AsyncMock:
    """A mocked department repository with no-collision defaults."""
    mock = AsyncMock()
    mock.get_department_by_code.return_value = None
    mock.get_department_by_name.return_value = None
    return mock


# ── create_department ───────────────────────────────────────────────────────


async def test_create_department_persists_and_audits(repo: AsyncMock) -> None:
    """Happy path: the row is written, committed, and audited."""
    created = build_department_model(hospital_id=HOSPITAL_ID)
    repo.create_department.return_value = created
    service, session, audit, _ = _make_service(repo)

    result = await service.create_department(
        HOSPITAL_ID, build_create_department_request(), actor_id=ACTOR_ID
    )

    assert result.code == "CARD"
    assert result.name == "Cardiology"
    assert session.commits == 1
    assert audit.actions() == ["department.created"]
    assert audit.last().target_id == created.id
    assert audit.last().actor_id == ACTOR_ID


async def test_create_department_uppercases_code(repo: AsyncMock) -> None:
    """A lowercase code is normalised before it reaches the repository."""
    repo.create_department.return_value = build_department_model(hospital_id=HOSPITAL_ID)
    service, _, _, _ = _make_service(repo)

    await service.create_department(
        HOSPITAL_ID, build_create_department_request(code="ortho"), actor_id=ACTOR_ID
    )

    assert repo.create_department.await_args.kwargs["code"] == "ORTHO"


async def test_create_department_rejects_duplicate_code(repo: AsyncMock) -> None:
    """An existing code is a 409, and nothing is written."""
    repo.get_department_by_code.return_value = build_department_model()
    service, session, audit, _ = _make_service(repo)

    with pytest.raises(DuplicateDepartmentCodeError):
        await service.create_department(HOSPITAL_ID, build_create_department_request())

    repo.create_department.assert_not_awaited()
    assert session.commits == 0
    assert audit.events == []


async def test_create_department_rejects_duplicate_name(repo: AsyncMock) -> None:
    """An existing name is a 409 even when the code is free."""
    repo.get_department_by_name.return_value = build_department_model()
    service, session, _, _ = _make_service(repo)

    with pytest.raises(DuplicateDepartmentNameError):
        await service.create_department(HOSPITAL_ID, build_create_department_request())

    repo.create_department.assert_not_awaited()
    assert session.commits == 0


async def test_create_department_rejects_bad_code_at_service_layer(repo: AsyncMock) -> None:
    """The service re-asserts validation for non-HTTP callers.

    The schema would normally catch this, so the payload is built valid and
    then mutated — simulating a seed script or background job constructing the
    request object directly.
    """
    payload = build_create_department_request()
    object.__setattr__(payload, "code", "bad code")
    service, _, _, _ = _make_service(repo)

    with pytest.raises(ValidationError) as exc:
        await service.create_department(HOSPITAL_ID, payload)

    assert exc.value.detail["errors"][0]["field"] == "code"


# ── update_department ───────────────────────────────────────────────────────


async def test_update_department_applies_only_sent_fields(repo: AsyncMock) -> None:
    """PATCH touches exactly the fields the client sent."""
    existing = build_department_model(hospital_id=HOSPITAL_ID)
    repo.get_department_by_id.return_value = existing
    repo.update_department.return_value = existing
    service, session, audit, _ = _make_service(repo)

    await service.update_department(
        HOSPITAL_ID,
        existing.id,
        build_update_department_request(location="Block C"),
        actor_id=ACTOR_ID,
    )

    assert set(repo.update_department.await_args.kwargs) == {"location", "updated_by"}
    assert session.commits == 1
    assert audit.actions() == ["department.updated"]


async def test_update_department_noop_does_not_write_or_audit(repo: AsyncMock) -> None:
    """Re-sending an unchanged value is not an edit."""
    existing = build_department_model(hospital_id=HOSPITAL_ID, location="Block B, 3rd Floor")
    repo.get_department_by_id.return_value = existing
    service, session, audit, _ = _make_service(repo)

    await service.update_department(
        HOSPITAL_ID,
        existing.id,
        build_update_department_request(location="Block B, 3rd Floor"),
    )

    repo.update_department.assert_not_awaited()
    assert session.commits == 0
    assert audit.events == []


async def test_update_department_allows_resubmitting_own_code(repo: AsyncMock) -> None:
    """A department's own code must not collide with itself.

    The uniqueness lookup would find this very row, so the service must skip
    the check when the value has not moved.
    """
    existing = build_department_model(hospital_id=HOSPITAL_ID, code="CARD")
    repo.get_department_by_id.return_value = existing
    repo.update_department.return_value = existing
    service, _, _, _ = _make_service(repo)

    await service.update_department(
        HOSPITAL_ID, existing.id, build_update_department_request(code="CARD", name="Cardio Care")
    )

    repo.get_department_by_code.assert_not_awaited()


async def test_update_department_rejects_duplicate_code_on_change(repo: AsyncMock) -> None:
    """Moving to a taken code is a 409."""
    existing = build_department_model(hospital_id=HOSPITAL_ID, code="CARD")
    repo.get_department_by_id.return_value = existing
    repo.get_department_by_code.return_value = build_department_model(code="ORTHO")
    service, session, _, _ = _make_service(repo)

    with pytest.raises(DuplicateDepartmentCodeError):
        await service.update_department(
            HOSPITAL_ID, existing.id, build_update_department_request(code="ORTHO")
        )

    assert session.commits == 0


async def test_update_department_missing_raises_not_found(repo: AsyncMock) -> None:
    """A department in another tenant is indistinguishable from a miss."""
    repo.get_department_by_id.return_value = None
    service, _, _, _ = _make_service(repo)

    with pytest.raises(DepartmentNotFoundError):
        await service.update_department(
            HOSPITAL_ID, uuid.uuid4(), build_update_department_request(location="X")
        )


# ── deactivate_department: the rule 13 guard, both branches ─────────────────


async def test_deactivate_department_succeeds_when_no_doctors_assigned(
    repo: AsyncMock,
) -> None:
    """Guard clears: with zero assignments the soft delete goes through."""
    existing = build_department_model(hospital_id=HOSPITAL_ID)
    repo.get_department_by_id.return_value = existing
    repo.delete_department.return_value = existing
    service, session, audit, usage = _make_service(repo, assigned_doctors=0)

    await service.deactivate_department(HOSPITAL_ID, existing.id, actor_id=ACTOR_ID)

    assert usage.calls == [(HOSPITAL_ID, existing.id)]
    repo.delete_department.assert_awaited_once()
    assert session.commits == 1
    assert audit.actions() == ["department.deactivated"]


async def test_deactivate_department_blocked_when_doctors_assigned(repo: AsyncMock) -> None:
    """Guard triggers: assigned doctors make deactivation a 409.

    Nothing is written and nothing is audited — a refused deactivation is not
    a mutation.
    """
    existing = build_department_model(hospital_id=HOSPITAL_ID)
    repo.get_department_by_id.return_value = existing
    service, session, audit, usage = _make_service(repo, assigned_doctors=3)

    with pytest.raises(DepartmentInUseError) as exc:
        await service.deactivate_department(HOSPITAL_ID, existing.id, actor_id=ACTOR_ID)

    assert exc.value.detail["assigned_doctors"] == 3
    assert exc.value.status_code == 409
    assert usage.calls == [(HOSPITAL_ID, existing.id)]
    repo.delete_department.assert_not_awaited()
    assert session.commits == 0
    assert audit.events == []


async def test_deactivate_department_already_deactivated(repo: AsyncMock) -> None:
    """Deactivating twice is a business-rule error, not a silent success."""
    from datetime import UTC, datetime

    existing = build_department_model(
        hospital_id=HOSPITAL_ID, deleted_at=datetime(2026, 7, 29, tzinfo=UTC)
    )
    repo.get_department_by_id.return_value = existing
    service, session, _, _ = _make_service(repo)

    with pytest.raises(DepartmentNotDeactivatedError):
        await service.deactivate_department(HOSPITAL_ID, existing.id)

    assert session.commits == 0


async def test_deactivate_department_missing_raises_not_found(repo: AsyncMock) -> None:
    """An absent department is a 404."""
    repo.get_department_by_id.return_value = None
    service, _, _, _ = _make_service(repo)

    with pytest.raises(DepartmentNotFoundError):
        await service.deactivate_department(HOSPITAL_ID, uuid.uuid4())


async def test_null_usage_source_reports_no_assignments() -> None:
    """The interim source reports zero, which is what makes the guard inert today."""
    assert await NullDepartmentUsageSource().active_doctor_count(HOSPITAL_ID, uuid.uuid4()) == 0


# ── activate_department ─────────────────────────────────────────────────────


async def test_activate_department_restores_and_audits(repo: AsyncMock) -> None:
    """Reactivation clears the soft delete and records an audit event."""
    from datetime import UTC, datetime

    existing = build_department_model(
        hospital_id=HOSPITAL_ID, deleted_at=datetime(2026, 7, 29, tzinfo=UTC)
    )
    repo.get_department_by_id.return_value = existing
    repo.restore_department.return_value = build_department_model(hospital_id=HOSPITAL_ID)
    service, session, audit, _ = _make_service(repo)

    await service.activate_department(HOSPITAL_ID, existing.id, actor_id=ACTOR_ID)

    repo.restore_department.assert_awaited_once()
    assert session.commits == 1
    assert audit.actions() == ["department.activated"]


async def test_activate_department_already_active(repo: AsyncMock) -> None:
    """Reactivating a live department is a business-rule error."""
    repo.get_department_by_id.return_value = build_department_model(hospital_id=HOSPITAL_ID)
    service, session, _, _ = _make_service(repo)

    with pytest.raises(DepartmentAlreadyActiveError):
        await service.activate_department(HOSPITAL_ID, uuid.uuid4())

    assert session.commits == 0


# ── Queries ─────────────────────────────────────────────────────────────────


async def test_get_department_details_returns_dto(repo: AsyncMock) -> None:
    """A found department is returned as a DTO, never as an ORM model."""
    existing = build_department_model(hospital_id=HOSPITAL_ID)
    repo.get_department_by_id.return_value = existing
    service, _, _, _ = _make_service(repo)

    result = await service.get_department_details(HOSPITAL_ID, existing.id)

    assert result.id == existing.id
    assert result.status == "active"


async def test_get_department_details_missing_raises_not_found(repo: AsyncMock) -> None:
    """An absent department is a 404 carrying the requested id."""
    repo.get_department_by_id.return_value = None
    service, _, _, _ = _make_service(repo)
    missing = uuid.uuid4()

    with pytest.raises(DepartmentNotFoundError) as exc:
        await service.get_department_details(HOSPITAL_ID, missing)

    assert exc.value.detail["department_id"] == str(missing)


async def test_list_departments_paginates(repo: AsyncMock) -> None:
    """The page carries the repository's rows and total."""
    rows: list[Department] = [
        build_department_model(code="CARD", name="Cardiology"),
        build_department_model(code="ORTHO", name="Orthopaedics"),
    ]
    repo.list_departments.return_value = rows
    repo.count_departments.return_value = 2
    service, _, _, _ = _make_service(repo)

    page = await service.list_departments(HOSPITAL_ID)

    assert [d.code for d in page.items] == ["CARD", "ORTHO"]
    assert page.total_records == 2
    assert page.total_pages == 1


async def test_list_departments_does_not_audit(repo: AsyncMock) -> None:
    """Listing is not searching — a page view must not litter the audit trail."""
    repo.list_departments.return_value = []
    repo.count_departments.return_value = 0
    service, _, audit, _ = _make_service(repo)

    await service.list_departments(HOSPITAL_ID)

    assert audit.events == []


async def test_search_departments_audits_filter_names_only(repo: AsyncMock) -> None:
    """Search is audited, but the term itself is not recorded."""
    from app.schemas.department import SearchDepartmentRequest

    repo.search_departments.return_value = [build_department_model()]
    repo.count_departments.return_value = 1
    service, _, audit, _ = _make_service(repo)

    await service.search_departments(
        HOSPITAL_ID, SearchDepartmentRequest(q="cardio"), actor_id=ACTOR_ID
    )

    event = audit.last()
    assert event.action == "department.searched"
    assert event.context["result_count"] == 1
    assert "term" in event.context["filters_used"]
    # The term's value must not appear anywhere in the event.
    assert "cardio" not in str(event.context)
