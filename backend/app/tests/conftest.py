"""Shared pytest fixtures for the backend test suite.

``asyncio_mode = "auto"`` is set in ``pyproject.toml``, so ``async def`` tests
need no decorator.

Fixtures that belong here as the suite grows:

- ``db_engine`` / ``db_session`` — a transactional session rolled back per test
- ``client`` — an ``httpx.AsyncClient`` bound to the app with DB overrides
- ``auth_headers`` — test JWT minting for authenticated API tests

They are deliberately not stubbed out yet: the first test that needs one
defines it, so no fixture exists without a caller to validate it.
"""

from __future__ import annotations
