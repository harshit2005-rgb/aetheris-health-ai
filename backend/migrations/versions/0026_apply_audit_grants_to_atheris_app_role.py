"""apply the audit-log grants to the atheris_app role

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-12 12:00:00.000000

The product name is spelled "Atheris". The deployed application role is
therefore ``atheris_app``, but migration 0010 restricted the audit trail for a
role named with the earlier spelling, so on a database whose role carries the
new name the trail was never made append-only for it.

This applies the same rule (``docs/modules/12-audit-logs.md`` §8) to
``atheris_app``: it may insert and read ``audit_logs`` and may never update or
delete a row. Migration 0010 is left as merged; a database that still has the
old role keeps the restriction 0010 gave it.

Guarded on role existence, exactly as 0010 is, so a database without the
deployed role (local dev, CI) migrates cleanly and this is a no-op there.

``downgrade`` does nothing: withdrawing the restriction would make the audit
trail rewritable, which no earlier revision of the schema ever allowed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Make ``audit_logs`` append-only for ``atheris_app``, where that role exists."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'atheris_app') THEN
                REVOKE UPDATE, DELETE ON audit_logs FROM atheris_app;
                GRANT INSERT, SELECT ON audit_logs TO atheris_app;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Leave the grants in place: the audit trail stays append-only."""
