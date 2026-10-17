"""Unit tests for :class:`ImportService` (module services and lookups mocked)."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import BusinessRuleError, ConflictError
from app.services.import_service import ImportService, UnknownImportKindError
from app.tests.conftest import RecordingAuditSink
from app.utils.spreadsheet import SheetData

HOSPITAL = uuid.uuid4()
ACTOR = uuid.uuid4()


def _sheet(*rows: dict[str, Any]) -> SheetData:
    headers = tuple(dict.fromkeys(k for row in rows for k in row))
    return SheetData(headers=headers, rows=tuple(enumerate(rows, start=2)))


def _service_row(code: str = "CONS", price: str = "500") -> dict[str, Any]:
    return {"code": code, "name": "Consultation", "price": price}


class _Harness:
    def __init__(self) -> None:
        self.services = AsyncMock()
        self.service_lookup = AsyncMock()
        self.service_lookup.get_service_by_code.return_value = None
        self.session = AsyncMock()
        self.audit = RecordingAuditSink()
        self.importer = ImportService(
            patients=AsyncMock(),
            services=self.services,
            medicines=AsyncMock(),
            lab_tests=AsyncMock(),
            patient_lookup=AsyncMock(),
            service_lookup=self.service_lookup,
            medicine_lookup=AsyncMock(),
            lab_test_lookup=AsyncMock(),
            session=self.session,
            audit=self.audit,
        )

    async def run(self, sheet: SheetData, *, dry_run: bool) -> Any:
        return await self.importer.run(HOSPITAL, "services", sheet, dry_run=dry_run, actor_id=ACTOR)


async def test_a_dry_run_creates_nothing_and_audits_nothing() -> None:
    h = _Harness()

    report = await h.run(_sheet(_service_row()), dry_run=True)

    assert (report.ready, report.created) == (1, 0)
    h.services.create_service.assert_not_called()
    h.session.commit.assert_not_called()
    assert h.audit.events == []


async def test_a_real_run_creates_through_the_module_service_and_audits_once() -> None:
    h = _Harness()

    report = await h.run(_sheet(_service_row("A"), _service_row("B")), dry_run=False)

    assert report.created == 2
    assert h.services.create_service.await_count == 2
    request = h.services.create_service.await_args_list[0].args[1]
    assert request.code == "A"
    assert h.services.create_service.await_args_list[0].kwargs == {"actor_id": ACTOR}
    [event] = h.audit.events
    assert event.action == "data.import.completed"
    assert event.context["created"] == 2


async def test_existing_and_repeated_rows_are_skipped() -> None:
    h = _Harness()
    h.service_lookup.get_service_by_code.side_effect = lambda _h, code: (
        object() if code == "OLD" else None
    )

    report = await h.run(
        _sheet(_service_row("OLD"), _service_row("NEW"), _service_row("new")), dry_run=False
    )

    assert report.created == 1
    assert [(s.row, s.reason) for s in report.skipped] == [
        (2, "Service OLD already exists."),
        (4, "Repeats an earlier row of this file."),
    ]


async def test_a_conflict_while_creating_is_a_skip_and_other_refusals_are_problems() -> None:
    h = _Harness()
    h.services.create_service.side_effect = [
        ConflictError(message="Code taken."),
        BusinessRuleError("Not allowed."),
        None,
    ]

    report = await h.run(
        _sheet(_service_row("A"), _service_row("B"), _service_row("C")), dry_run=False
    )

    assert report.created == 1
    assert [s.reason for s in report.skipped] == ["Code taken."]
    assert [(p.row, p.message) for p in report.problems] == [(3, "Not allowed.")]


async def test_cell_and_validation_errors_name_the_template_column() -> None:
    h = _Harness()

    report = await h.run(_sheet({"code": "A", "name": "X", "price": "free"}), dry_run=True)

    [problem] = report.problems
    assert (problem.row, problem.column) == (2, "Price")


async def test_unknown_kind() -> None:
    h = _Harness()

    with pytest.raises(UnknownImportKindError):
        await h.importer.run(HOSPITAL, "doctors", _sheet(), dry_run=True, actor_id=ACTOR)


def test_unknown_kind_has_no_template() -> None:
    with pytest.raises(UnknownImportKindError):
        ImportService.template("doctors")
