"""encrypt mfa secrets at rest

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-06 20:00:00.000000

A data migration — no schema change. ``users.mfa_secret`` stays ``TEXT``; its
contents change from the plaintext base32 TOTP secret to a Fernet token
(``app/core/security.py``, "MFA secret encryption at rest").

**This migration needs the encryption key when, and only when, there is a
plaintext secret to convert.**

- A database with no MFA secrets — every fresh database, and any existing one
  where nobody has enrolled — upgrades without a key.
- A database that holds plaintext secrets refuses to upgrade until
  ``MFA_ENCRYPTION_KEY`` is provided. It does not skip the rows, blank them, or
  write a placeholder: skipping would leave plaintext behind, and blanking
  would silently switch MFA off for those users.

Idempotent: a value that is already a Fernet token is left alone, so the
migration can be re-run and can follow a partial manual conversion.

``downgrade`` restores the plaintext, because the previous application version
reads the column as plaintext and would otherwise lock every MFA user out. It
needs the same key. Run it only as part of rolling the application back.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Every Fernet token starts this way (version byte + timestamp, base64). A
#: base32 TOTP secret — upper-case letters and 2-7 — never does.
_FERNET_TOKEN_PREFIX = "gAAAAA"  # noqa: S105 — a format marker, not a credential

_users = sa.table(
    "users",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("mfa_secret", sa.Text),
)


def _configured_keys() -> list[bytes]:
    """Return the current key followed by any retired keys, from configuration.

    Read through the application settings so the key comes from the same place
    the running application takes it: the environment, or ``backend/.env`` in
    local development.
    """
    from app.core.config import settings

    return [
        *settings.mfa_encryption_keys("MFA_ENCRYPTION_KEY"),
        *settings.mfa_encryption_keys("MFA_ENCRYPTION_PREVIOUS_KEYS"),
    ]


def _stored_secrets(connection: Connection) -> list[tuple[object, str]]:
    rows = connection.execute(
        sa.select(_users.c.id, _users.c.mfa_secret).where(_users.c.mfa_secret.is_not(None))
    )
    return [(row.id, row.mfa_secret) for row in rows]


def encrypt_plaintext_secrets(connection: Connection, keys: list[bytes]) -> int:
    """Encrypt every plaintext MFA secret under the current key.

    :param connection: The migration's connection.
    :param keys: Configured keys, current key first. May be empty.
    :returns: How many secrets were encrypted.
    :raises RuntimeError: If a plaintext secret exists and no key is configured.
    """
    plaintext = [
        (user_id, secret)
        for user_id, secret in _stored_secrets(connection)
        if not secret.startswith(_FERNET_TOKEN_PREFIX)
    ]
    if not plaintext:
        return 0
    if not keys:
        msg = (
            f"{len(plaintext)} MFA secret(s) are stored in plaintext and MFA_ENCRYPTION_KEY "
            "is not set. Provide the key and run the migration again; nothing was changed."
        )
        raise RuntimeError(msg)

    cipher = Fernet(keys[0])
    for user_id, secret in plaintext:
        connection.execute(
            sa.update(_users)
            .where(_users.c.id == user_id)
            .values(mfa_secret=cipher.encrypt(secret.encode("utf-8")).decode("ascii"))
        )
    return len(plaintext)


def decrypt_encrypted_secrets(connection: Connection, keys: list[bytes]) -> int:
    """Restore every encrypted MFA secret to plaintext (rollback only).

    :param connection: The migration's connection.
    :param keys: Configured keys, current key first. May be empty.
    :returns: How many secrets were decrypted.
    :raises RuntimeError: If an encrypted secret exists and no key is
        configured, or a secret does not decrypt under any configured key.
        Nothing is changed in either case.
    """
    encrypted = [
        (user_id, secret)
        for user_id, secret in _stored_secrets(connection)
        if secret.startswith(_FERNET_TOKEN_PREFIX)
    ]
    if not encrypted:
        return 0
    if not keys:
        msg = (
            f"{len(encrypted)} MFA secret(s) are encrypted and MFA_ENCRYPTION_KEY is not set. "
            "The downgrade needs the key that encrypted them; nothing was changed."
        )
        raise RuntimeError(msg)

    cipher = MultiFernet([Fernet(key) for key in keys])
    decrypted: list[tuple[object, str]] = []
    for user_id, secret in encrypted:
        try:
            decrypted.append((user_id, cipher.decrypt(secret.encode("utf-8")).decode("utf-8")))
        except InvalidToken:
            msg = (
                "An MFA secret does not decrypt under any configured key. "
                "The downgrade needs the key that encrypted it; nothing was changed."
            )
            raise RuntimeError(msg) from None

    for user_id, secret in decrypted:
        connection.execute(
            sa.update(_users).where(_users.c.id == user_id).values(mfa_secret=secret)
        )
    return len(decrypted)


def upgrade() -> None:
    encrypt_plaintext_secrets(op.get_bind(), _configured_keys())


def downgrade() -> None:
    decrypt_encrypted_secrets(op.get_bind(), _configured_keys())
