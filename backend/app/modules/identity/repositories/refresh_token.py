"""Repository for the :class:`RefreshToken` model.

Supports token rotation detection, bulk revocation, and
expired-token cleanup. Repositories should not contain
business logic like rotation validation — that belongs
in the service layer.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for type hints
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select, update

from app.modules.identity.models import RefreshToken
from app.shared.repositories import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """Repository for refresh token CRUD and lifecycle operations.

    :param session: An active async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RefreshToken, session)

    async def create(  # type: ignore[override]
        self,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        **kwargs: object,
    ) -> RefreshToken:
        """Create a new refresh token record.

        :param user_id: UUID of the token owner.
        :param token_hash: SHA-256 hash of the opaque refresh token.
        :param expires_at: Token expiration timestamp (UTC).
        :param kwargs: Additional optional fields (device_info, ip_address).
        :returns: The created refresh token instance.
        """
        return await super().create(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            **kwargs,
        )

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        """Retrieve a token by its hash (O(1) lookup).

        :param token_hash: The SHA-256 hash of the token.
        :returns: The token instance, or ``None``.
        """
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def revoke(
        self,
        token: RefreshToken,
        rotated_by_id: uuid.UUID | None = None,
    ) -> RefreshToken:
        """Revoke a refresh token.

        When used as part of token rotation, provide ``rotated_by_id``
        to link this revocation to the replacement token.

        :param token: The token instance to revoke.
        :param rotated_by_id: Optional UUID of the replacement token.
        :returns: The revoked token instance.
        """
        now = datetime.now(UTC)
        return await self.update(
            token,
            is_revoked=True,
            revoked_at=now,
            rotated_by_token_id=rotated_by_id,
        )

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
        """Revoke ALL tokens for a user (used on token theft detection).

        :param user_id: The user's UUID.
        :returns: The number of revoked tokens.
        """
        now = datetime.now(UTC)
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked.is_(False),
            )
            .values(is_revoked=True, revoked_at=now)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount  # type: ignore[attr-defined, no-any-return]

    async def delete_expired(self) -> int:
        """Delete all expired refresh tokens.

        :returns: The number of deleted tokens.
        """
        now = datetime.now(UTC)
        stmt = select(RefreshToken).where(RefreshToken.expires_at < now)
        result = await self._session.execute(stmt)
        tokens = list(result.unique().scalars().all())
        for token in tokens:
            await self._session.delete(token)
        await self._session.flush()
        return len(tokens)

    async def list_valid_by_user(self, user_id: uuid.UUID) -> list[RefreshToken]:
        """List all non-revoked, non-expired tokens for a user.

        :param user_id: The user's UUID.
        :returns: List of valid token instances.
        """
        now = datetime.now(UTC)
        stmt = (
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked.is_(False),
                RefreshToken.expires_at > now,
            )
            .order_by(RefreshToken.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.unique().scalars().all())

    async def count_valid_for_user(self, user_id: uuid.UUID) -> int:
        """Count valid (non-revoked, non-expired) tokens for a user.

        :param user_id: The user's UUID.
        :returns: Token count.
        """
        now = datetime.now(UTC)
        stmt = (
            select(func.count())
            .select_from(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked.is_(False),
                RefreshToken.expires_at > now,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
