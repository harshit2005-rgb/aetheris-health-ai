"""Database seed data — permissions, roles, and demo data.

Usage::

    from app.seeds.seed import seed_database

    await seed_database()

Or from the command line::

    python -m app.seeds.seed

See :mod:`app.seeds.seed` for the full seed implementation.
"""

from app.seeds.seed import seed_database

__all__ = [
    "seed_database",
]
