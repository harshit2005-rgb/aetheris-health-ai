"""RefreshToken model — server-side refresh token store with rotation support.

Backs the short-lived-access-token + rotating-refresh-token scheme described in
``docs/07-SECURITY.md``, including reuse detection.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Mapped[uuid.UUID] resolution
from datetime import (  # noqa: TC003 — needed at runtime for Mapped[datetime] resolution
    UTC,
    datetime,
)
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Server-side refresh token store with rotation support.

    Supports the token rotation pattern:
    1. Client presents refresh token → server hashes it and looks up by hash.
    2. If found and not revoked → issue new pair, revoke old token,
       set ``rotated_by_token_id`` to the new token's ID.
    3. If found and already revoked → **reuse detection**: invalidate
       ALL tokens for this user (token theft suspected).
    4. If not found → reject.

    Expired and revoked tokens are cleaned up by a background job.
    """

    __tablename__ = "refresh_tokens"

    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="UUID of the token owner.",
    )
    token_hash: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="SHA-256 hash of the opaque refresh token. Used for O(1) lookup.",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        comment="Token expiration timestamp (UTC). Default 7 days from issuance.",
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="Whether this token has been revoked.",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp when this token was revoked.",
    )
    rotated_by_token_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
        comment="UUID of the replacement token. NULL = current token. Enables rotation chain tracking.",
    )
    device_info: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="User-agent or device description at issuance.",
    )
    ip_address: Mapped[str | None] = mapped_column(
        INET, nullable=True,
        comment="IP address at token issuance.",
    )

    # ── Relationships ───────────────────────────────────────────────────
    # `user_id` is the token owner; the audit columns also point at users.id.
    user: Mapped[User] = relationship(
        "User",
        back_populates="refresh_tokens",
        foreign_keys="RefreshToken.user_id",
        lazy="joined",
    )
    rotated_by: Mapped[RefreshToken | None] = relationship(
        "RefreshToken",
        remote_side="RefreshToken.id",
        foreign_keys=[rotated_by_token_id],
        lazy="joined",
        uselist=False,
    )

    @property
    def is_expired(self) -> bool:
        """True if the token has passed its expiration time."""
        return datetime.now(UTC) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """True if the token is not revoked and not expired."""
        return not self.is_revoked and not self.is_expired

    def __repr__(self) -> str:
        return (
            f"<RefreshToken id={self.id!s:.8} "
            f"user={self.user_id!s:.8} "
            f"revoked={self.is_revoked}>"
        )
