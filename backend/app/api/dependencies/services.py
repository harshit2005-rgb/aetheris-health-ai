"""Dependency injection wiring for every service.

One provider per service, each composing the repositories it needs. Routes
depend on these — never on repositories directly.

Placement rule (``docs/09-PROJECT_STRUCTURE.md``): every new service added
under ``app/services/`` gets a provider in this module.

Empty until the first service lands; see ``app/api/dependencies/repositories.py``
for the provider pattern to follow.
"""

from __future__ import annotations

__all__: list[str] = []
