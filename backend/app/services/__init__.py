"""Business logic layer — one service per aggregate.

Services enforce business rules, orchestrate across repositories, and own
transactions. A repository never calls another repository; a service composes
them.

Placement rule (``docs/09-PROJECT_STRUCTURE.md``): a new service goes in
``app/services/<domain>_service.py`` and is wired for DI in
``app/api/dependencies/services.py``.
"""
