"""Identity module repositories.

Each repository encapsulates all database access for its model.
Repositories inherit from :class:`BaseRepository` and are
instantiated with an :class:`AsyncSession`.
"""

from app.modules.identity.repositories.hospital import HospitalRepository
from app.modules.identity.repositories.permission import PermissionRepository
from app.modules.identity.repositories.refresh_token import RefreshTokenRepository
from app.modules.identity.repositories.role import RoleRepository
from app.modules.identity.repositories.user import UserRepository

__all__ = [
    "HospitalRepository",
    "UserRepository",
    "RoleRepository",
    "PermissionRepository",
    "RefreshTokenRepository",
]
