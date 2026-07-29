"""Unit tests for :class:`~app.services.mrn_service.MRNService`.

The counter repository is mocked here; that the counter is actually locked and
monotonic under concurrency is proven against a real database in
``app/tests/repository/test_mrn_sequence_repository.py``.
"""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ConfigurationError
from app.repositories.mrn_sequence_repository import MrnSequenceRepository
from app.services.mrn_service import MRNService
from app.utils.mrn import DEFAULT_MRN_TEMPLATE

HOSPITAL_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def sequences() -> AsyncMock:
    """Mocked :class:`MrnSequenceRepository`."""
    repository = AsyncMock(spec=MrnSequenceRepository)
    repository.advance.return_value = (42, DEFAULT_MRN_TEMPLATE)
    return repository


@pytest.fixture
def service(sequences: AsyncMock) -> MRNService:
    """The service under test."""
    return MRNService(sequences)


class TestMrnServiceNext:
    """Reserving and rendering the next MRN."""

    async def test_next_renders_the_reserved_sequence_value(
        self,
        service: MRNService,
    ) -> None:
        assert await service.next(HOSPITAL_ID, issued_on=date(2026, 3, 1)) == "MRN-2026-00042"

    async def test_next_advances_the_counter_for_the_requested_hospital(
        self,
        service: MRNService,
        sequences: AsyncMock,
    ) -> None:
        await service.next(HOSPITAL_ID)

        sequences.advance.assert_awaited_once_with(HOSPITAL_ID)

    async def test_next_uses_the_hospitals_configured_template(
        self,
        service: MRNService,
        sequences: AsyncMock,
    ) -> None:
        # Module spec §4 rule 2: the format is configurable per hospital.
        sequences.advance.return_value = (7, "AH/{year}/{seq:04d}")

        assert await service.next(HOSPITAL_ID, issued_on=date(2026, 1, 1)) == "AH/2026/0007"

    async def test_next_takes_the_year_from_the_issue_date(
        self,
        service: MRNService,
    ) -> None:
        assert await service.next(HOSPITAL_ID, issued_on=date(2027, 1, 1)) == "MRN-2027-00042"

    async def test_next_reports_a_broken_template_as_a_configuration_error(
        self,
        service: MRNService,
        sequences: AsyncMock,
    ) -> None:
        # A misconfigured hospital template is an operator problem, not the
        # receptionist's — it must not surface as "your input is invalid".
        sequences.advance.return_value = (1, "MRN-{seq.__class__}")

        with pytest.raises(ConfigurationError):
            await service.next(HOSPITAL_ID)

    async def test_next_reports_an_overlong_render_as_a_configuration_error(
        self,
        service: MRNService,
        sequences: AsyncMock,
    ) -> None:
        sequences.advance.return_value = (1, "A-VERY-LONG-HOSPITAL-PREFIX-{year}-{seq:05d}")

        with pytest.raises(ConfigurationError):
            await service.next(HOSPITAL_ID)

    async def test_next_does_not_leak_the_template_in_the_error_message(
        self,
        service: MRNService,
        sequences: AsyncMock,
    ) -> None:
        # docs/06-API_STANDARDS.md and the module spec both require that
        # internal exception details never reach the client.
        sequences.advance.return_value = (1, "MRN-{seq!r}")

        with pytest.raises(ConfigurationError) as exc_info:
            await service.next(HOSPITAL_ID)

        assert "seq!r" not in exc_info.value.message
        assert exc_info.value.detail == {"hospital_id": str(HOSPITAL_ID)}
