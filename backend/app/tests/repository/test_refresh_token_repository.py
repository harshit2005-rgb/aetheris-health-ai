"""Repository tests for :class:`~app.repositories.refresh_token_repository.RefreshTokenRepository`.

Run against a real PostgreSQL (``docs/11-TESTING_STRATEGY.md`` §2.2) because
what is under test is the SQL behind token rotation: the rotation chain,
revoke-all, and expiry filtering. The Week 1 handoff (A3) calls these out
explicitly.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.refresh_token import RefreshToken

pytestmark = pytest.mark.database


@pytest.fixture
def repository(db_session: AsyncSession) -> RefreshTokenRepository:
    """A repository bound to the rolled-back test session."""
    return RefreshTokenRepository(db_session)


async def _create_user(db_session: AsyncSession, hospital_id: uuid.UUID) -> uuid.UUID:
    """Insert a user row and return its UUID."""
    user = User(
        id=uuid.uuid4(),
        hospital_id=hospital_id,
        email=f"token-owner-{uuid.uuid4().hex[:12]}@hospital.test",
        password_hash="test-placeholder-not-a-hash",
        first_name="Token",
        last_name="Owner",
    )
    db_session.add(user)
    await db_session.flush()
    return user.id


async def _create_token(
    repository: RefreshTokenRepository,
    user_id: uuid.UUID,
    *,
    expires_in: timedelta = timedelta(days=7),
) -> RefreshToken:
    """Insert a refresh token valid until ``expires_in`` from now."""
    return await repository.create(
        user_id=user_id,
        token_hash=f"hash-{uuid.uuid4().hex}",
        expires_at=datetime.now(UTC) + expires_in,
    )


class TestRotationChain:
    """``rotated_by_token_id`` links a token to its replacement."""

    async def test_revoke_links_the_replacement(
        self,
        repository: RefreshTokenRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        """Rotating revokes the old token and records the replacement id."""
        user_id = await _create_user(db_session, hospital_id)
        old = await _create_token(repository, user_id)
        replacement = await _create_token(repository, user_id)

        revoked = await repository.revoke(old, rotated_by_id=replacement.id)

        assert revoked.is_revoked is True
        assert revoked.revoked_at is not None
        assert revoked.rotated_by_token_id == replacement.id

    async def test_rotated_token_is_no_longer_valid(
        self,
        repository: RefreshTokenRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        """A rotated (revoked) token must fail the validity check."""
        user_id = await _create_user(db_session, hospital_id)
        token = await _create_token(repository, user_id)
        # The replacement must be a real row: rotated_by_token_id is a
        # self-referencing foreign key, so a synthetic UUID fails the insert.
        replacement = await _create_token(repository, user_id)
        await repository.revoke(token, rotated_by_id=replacement.id)

        assert token.is_revoked is True
        assert token.is_valid is False


class TestRevokeAll:
    """Bulk revocation used by logout-all and security responses."""

    async def test_revoke_all_for_user_revokes_every_token(
        self,
        repository: RefreshTokenRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        """All of one user's tokens are revoked in one statement."""
        user_id = await _create_user(db_session, hospital_id)
        await _create_token(repository, user_id)
        await _create_token(repository, user_id)
        await _create_token(repository, user_id)

        count = await repository.revoke_all_for_user(user_id)

        assert count == 3
        assert await repository.count_valid_for_user(user_id) == 0

    async def test_revoke_all_spares_other_users(
        self,
        repository: RefreshTokenRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        """Bulk revocation never touches another user's sessions."""
        user_a = await _create_user(db_session, hospital_id)
        user_b = await _create_user(db_session, hospital_id)
        await _create_token(repository, user_a)
        kept = await _create_token(repository, user_b)

        await repository.revoke_all_for_user(user_a)

        assert kept.is_revoked is False
        assert await repository.count_valid_for_user(user_b) == 1


class TestExpiry:
    """Expiry filtering and cleanup."""

    async def test_expired_token_is_not_valid(
        self,
        repository: RefreshTokenRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        """An expired token fails ``is_expired`` and ``is_valid``."""
        user_id = await _create_user(db_session, hospital_id)
        token = await _create_token(repository, user_id, expires_in=timedelta(seconds=-10))

        assert token.is_expired is True
        assert token.is_valid is False

    async def test_valid_list_excludes_revoked_and_expired(
        self,
        repository: RefreshTokenRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        """``list_valid_by_user`` returns only live tokens."""
        user_id = await _create_user(db_session, hospital_id)
        live = await _create_token(repository, user_id)
        await _create_token(repository, user_id, expires_in=timedelta(seconds=-10))
        revoked = await _create_token(repository, user_id)
        await repository.revoke(revoked)

        valid = await repository.list_valid_by_user(user_id)

        assert {t.id for t in valid} == {live.id}

    async def test_delete_expired_removes_only_stale_rows(
        self,
        repository: RefreshTokenRepository,
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
    ) -> None:
        """Cleanup removes expired rows and keeps live ones."""
        user_id = await _create_user(db_session, hospital_id)
        await _create_token(repository, user_id)
        await _create_token(repository, user_id, expires_in=timedelta(seconds=-10))

        deleted = await repository.delete_expired()

        assert deleted == 1
        assert await repository.count_valid_for_user(user_id) == 1
