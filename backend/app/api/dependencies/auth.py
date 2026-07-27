"""Authentication and authorization dependencies.

Reserved for ``get_current_user`` and ``require_permission(...)`` — the two
dependencies every non-public endpoint declares (``docs/07-SECURITY.md``,
rules 3 and 4).

Implemented alongside the authentication module
(``docs/modules/01-authentication.md``); it depends on ``app/core/security.py``,
which does not exist yet. This module is intentionally empty until then so the
structural map in ``docs/09-PROJECT_STRUCTURE.md`` has a home for it.
"""

from __future__ import annotations

__all__: list[str] = []
