"""Shared repository infrastructure.

Provides the generic :class:`BaseRepository` that all business-module
repositories should inherit from.

Usage::

    from app.shared.repositories import BaseRepository
    from app.modules.identity.models import User

    class UserRepository(BaseRepository[User]):
        ...
"""

from app.shared.repositories.base import BaseRepository

__all__ = [
    "BaseRepository",
]
