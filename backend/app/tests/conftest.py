"""Shared pytest fixtures for the backend test suite.

``asyncio_mode = "auto"`` is set in ``pyproject.toml``, so ``async def`` tests
need no decorator.

Two families of fixtures live here:

**Database fixtures** (``db_engine``, ``db_session``, ``hospital_id``) require a
real PostgreSQL, because the schema uses JSONB, native enums, partial indexes,
and ``SELECT ... FOR UPDATE`` — none of which SQLite emulates
(``docs/11-TESTING_STRATEGY.md`` §2.2). When no database is reachable they skip
rather than fail, so unit tests still run on a laptop with no Docker. Point
them at a database with ``TEST_DATABASE_URL``; the default is the configured
development URL with a ``_test`` suffix.

**Test doubles** (:class:`FakeSession`, :class:`RecordingAuditSink`) let unit
tests exercise the service layer with no database at all.

Each database test runs inside an outer transaction that is rolled back on
teardown, so tests never see each other's rows and ordering never matters
(``docs/11-TESTING_STRATEGY.md`` §4.3).
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import TYPE_CHECKING, Self

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from types import TracebackType

    from sqlalchemy.ext.asyncio import AsyncEngine

    from app.core.audit import AuditEvent

__all__ = ["FakeSession", "RecordingAuditSink"]


def pytest_configure(config: pytest.Config) -> None:
    """Register the suite's custom markers."""
    config.addinivalue_line(
        "markers",
        "database: test requires a reachable PostgreSQL instance.",
    )


# ── Test doubles ────────────────────────────────────────────────────────────


class _FakeNestedTransaction:
    """Stand-in for the object ``AsyncSession.begin_nested()`` returns.

    Rolls nothing back — unit tests assert on repository calls, not on database
    state. Returning ``False`` from ``__aexit__`` lets exceptions propagate,
    which is what a real savepoint does after rolling back.
    """

    def __init__(self, session: FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> Self:
        self._session.savepoints_opened += 1
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if exc_type is not None:
            self._session.savepoints_rolled_back += 1
        return False


class FakeSession:
    """Minimal :class:`~sqlalchemy.ext.asyncio.AsyncSession` stand-in.

    :class:`~app.services.patient_service.PatientService` holds a session only
    to own the transaction boundary, so a double that counts commits and
    savepoints is enough to assert the boundary is respected — and it makes the
    assertions readable, which mock call-chain inspection does not.
    """

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.savepoints_opened = 0
        self.savepoints_rolled_back = 0

    def begin_nested(self) -> _FakeNestedTransaction:
        """Open a fake savepoint."""
        return _FakeNestedTransaction(self)

    async def commit(self) -> None:
        """Record a commit."""
        self.commits += 1

    async def rollback(self) -> None:
        """Record a rollback."""
        self.rollbacks += 1


class RecordingAuditSink:
    """:class:`~app.core.audit.AuditSink` that keeps events in memory.

    Lets tests assert that every mutation produced the right audit event —
    required by the backend Definition of Done and AC-5 of the module spec.
    """

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def record(self, event: AuditEvent) -> None:
        """Store the event for later assertion."""
        self.events.append(event)

    def actions(self) -> list[str]:
        """Return the action name of every recorded event, in order."""
        return [event.action for event in self.events]

    def last(self) -> AuditEvent:
        """Return the most recent event.

        :raises AssertionError: If no event was recorded — a clearer failure
            than an ``IndexError`` three frames deep.
        """
        assert self.events, "Expected at least one audit event, but none were recorded."
        return self.events[-1]


@pytest.fixture
def fake_session() -> FakeSession:
    """Provide a fresh :class:`FakeSession` for a unit test."""
    return FakeSession()


@pytest.fixture
def audit_sink() -> RecordingAuditSink:
    """Provide a fresh :class:`RecordingAuditSink` for a unit test."""
    return RecordingAuditSink()


# ── Database fixtures ───────────────────────────────────────────────────────


def _test_database_url() -> str:
    """Return the URL of the test database.

    ``TEST_DATABASE_URL`` wins. Otherwise the configured development URL is
    reused with a ``_test`` suffix on the database name, so a misconfigured run
    cannot write to a developer's working data.
    """
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        return explicit
    base, _, database = settings.DATABASE_URL.rpartition("/")
    return f"{base}/{database}_test"


def _run_migrations(database_url: str) -> None:
    """Apply every Alembic migration to the test database.

    Tests run against the migrated schema rather than
    ``Base.metadata.create_all`` so that a migration which does not match the
    models fails the suite instead of passing it
    (``docs/11-TESTING_STRATEGY.md`` §4.2).

    Alembic's ``env.py`` drives an async engine through :func:`asyncio.run`,
    which cannot run inside an already-running event loop — hence the call from
    a worker thread via :func:`asyncio.to_thread`.
    """
    from alembic import command
    from alembic.config import Config

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    # migrations/env.py prefers DB_URL from the environment over the ini value.
    previous = os.environ.get("DB_URL")
    os.environ["DB_URL"] = database_url
    try:
        command.upgrade(config, "head")
    finally:
        if previous is None:
            os.environ.pop("DB_URL", None)
        else:
            os.environ["DB_URL"] = previous


@pytest_asyncio.fixture(scope="session")
async def db_engine() -> AsyncGenerator[AsyncEngine]:
    """Session-scoped engine bound to the migrated test database.

    Skips every database-backed test when PostgreSQL is unreachable.
    """
    url = _test_database_url()
    engine = create_async_engine(url)

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — any connection failure means "no database"
        await engine.dispose()
        pytest.skip(f"PostgreSQL is not reachable at {url}: {exc}")

    await asyncio.to_thread(_run_migrations, url)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """Provide a session whose writes are discarded when the test ends.

    The session joins an outer transaction that is rolled back on teardown.
    ``join_transaction_mode="create_savepoint"`` means a ``commit()`` inside the
    code under test releases a savepoint rather than committing for real, so
    services can own their transaction boundary honestly and the test still
    leaves no rows behind.
    """
    async with db_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


async def _create_hospital(session: AsyncSession, *, slug: str) -> uuid.UUID:
    """Insert a minimal hospital row and return its UUID."""
    from app.models.hospital import Hospital

    hospital = Hospital(
        id=uuid.uuid4(),
        name=f"Test Hospital {slug}",
        slug=slug,
        address={"line1": "1 Test Road", "city": "Hyderabad", "country": "IN"},
        settings={},
    )
    session.add(hospital)
    await session.flush()
    return hospital.id


@pytest_asyncio.fixture
async def hospital_id(db_session: AsyncSession) -> uuid.UUID:
    """Create a hospital and return its UUID.

    Every patient row needs a real ``hospital_id``: the foreign key is
    ``NOT NULL`` with ``ON DELETE RESTRICT``.
    """
    return await _create_hospital(db_session, slug=f"test-{uuid.uuid4().hex[:12]}")


@pytest_asyncio.fixture
async def other_hospital_id(db_session: AsyncSession) -> uuid.UUID:
    """Create a second hospital, for multi-tenant isolation tests."""
    return await _create_hospital(db_session, slug=f"other-{uuid.uuid4().hex[:12]}")


@pytest_asyncio.fixture
async def actor_id(db_session: AsyncSession, hospital_id: uuid.UUID) -> uuid.UUID:
    """Create a user to act as the caller, and return its UUID.

    The audit columns (``created_by``, ``updated_by``, ``deleted_by``) are real
    foreign keys to ``users.id``, so an actor UUID that does not exist as a row
    fails the insert. Tests that pass an actor must use this fixture.
    """
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        hospital_id=hospital_id,
        email=f"actor-{uuid.uuid4().hex[:12]}@hospital.test",
        # Not a credential — the column is NOT NULL and nothing under test
        # reads it. Real hashing is the auth module's concern.
        password_hash="test-placeholder-not-a-hash",
        first_name="Test",
        last_name="Actor",
    )
    db_session.add(user)
    await db_session.flush()
    return user.id
