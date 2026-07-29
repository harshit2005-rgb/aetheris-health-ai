"""Repository tests for the per-hospital MRN counter.

The claim under test is that ``advance`` hands out each sequence value exactly
once, even when two registrations run at the same time
(``docs/modules/03-patient-management.md`` §8). That claim is about a database
row lock, so it can only be tested against a real database with genuinely
concurrent transactions.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hospital import Hospital
from app.models.patient import MrnSequence
from app.repositories.mrn_sequence_repository import MrnSequenceRepository
from app.utils.mrn import DEFAULT_MRN_TEMPLATE

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.database


@pytest.fixture
def repository(db_session: AsyncSession) -> MrnSequenceRepository:
    """A repository bound to the rolled-back test session."""
    return MrnSequenceRepository(db_session)


class TestAdvance:
    """Reserving sequence values."""

    async def test_advance_creates_the_counter_on_first_use(
        self,
        repository: MrnSequenceRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        # A hospital has no counter row until it registers its first patient.
        assert await repository.get_for_hospital(hospital_id) is None

        value, template = await repository.advance(hospital_id)

        assert value == 1
        assert template == DEFAULT_MRN_TEMPLATE

    async def test_advance_increments_monotonically(
        self,
        repository: MrnSequenceRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        values = [(await repository.advance(hospital_id))[0] for _ in range(5)]

        assert values == [1, 2, 3, 4, 5]

    async def test_advance_keeps_a_separate_counter_per_hospital(
        self,
        repository: MrnSequenceRepository,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        # MRN is unique per hospital, so counters must not be shared.
        await repository.advance(hospital_id)
        await repository.advance(hospital_id)

        value, _ = await repository.advance(other_hospital_id)

        assert value == 1

    async def test_advance_persists_the_new_value(
        self,
        repository: MrnSequenceRepository,
        hospital_id: uuid.UUID,
    ) -> None:
        await repository.advance(hospital_id)
        await repository.advance(hospital_id)

        row = await repository.get_for_hospital(hospital_id)

        assert row is not None
        assert row.current_value == 2

    async def test_advance_honours_a_custom_template(
        self,
        repository: MrnSequenceRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        # Module spec §4 rule 2: format is configurable per hospital.
        db_session.add(
            MrnSequence(
                hospital_id=hospital_id,
                current_value=0,
                format_template="AH/{year}/{seq:04d}",
            )
        )
        await db_session.flush()

        _, template = await repository.advance(hospital_id)

        assert template == "AH/{year}/{seq:04d}"


class TestAdvanceConcurrency:
    """The row lock that makes MRN generation safe under load."""

    async def test_advance_never_hands_the_same_value_to_two_transactions(
        self,
        db_engine: AsyncEngine,
    ) -> None:
        # This test deliberately does not use the rolled-back ``db_session``
        # fixture: proving that transactions serialize requires them to be
        # genuinely separate and to really commit. It cleans up after itself.
        hospital_id = uuid.uuid4()
        slug = f"concurrency-{uuid.uuid4().hex[:12]}"

        async with AsyncSession(db_engine) as setup:
            setup.add(
                Hospital(
                    id=hospital_id,
                    name="Concurrency Test Hospital",
                    slug=slug,
                    address={"line1": "1 Test Road", "city": "Hyderabad", "country": "IN"},
                    settings={},
                )
            )
            await setup.commit()

        async def take_one() -> int:
            """Reserve one value in its own transaction, holding the lock briefly."""
            async with AsyncSession(db_engine) as session, session.begin():
                value, _ = await MrnSequenceRepository(session).advance(hospital_id)
                # Yield control while still holding the row lock, so the other
                # tasks actually reach the lock and have to wait. Without this
                # the tasks could run end-to-end one after another and the test
                # would pass without ever exercising contention.
                await asyncio.sleep(0.05)
                return value

        try:
            values = await asyncio.gather(take_one(), take_one(), take_one())

            # No duplicates and no gaps: the lock serialized all three.
            assert sorted(values) == [1, 2, 3]
        finally:
            async with AsyncSession(db_engine) as cleanup:
                await cleanup.execute(
                    delete(MrnSequence).where(MrnSequence.hospital_id == hospital_id)
                )
                await cleanup.execute(delete(Hospital).where(Hospital.id == hospital_id))
                await cleanup.commit()
