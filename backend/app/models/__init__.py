"""SQLAlchemy ORM models — one module per aggregate.

Importing this package registers every model with :attr:`Base.metadata`.
Alembic's ``migrations/env.py`` and any code that needs the full metadata
should import from here rather than from individual modules, so that no
mapper is left unconfigured.

Placement rule (``docs/09-PROJECT_STRUCTURE.md``): a new model goes in
``app/models/<domain>.py`` and is re-exported below.
"""

from app.models.base import (
    Base,
    CommonColumnsMixin,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.models.hospital import Hospital
from app.models.patient import BloodGroup, Gender, MrnSequence, Patient, PatientStatus
from app.models.permission import Permission
from app.models.refresh_token import RefreshToken
from app.models.role import Role, RolePermission
from app.models.user import User, UserRole, UserStatus

__all__ = [
    # Base + mixins
    "Base",
    "CommonColumnsMixin",
    "SoftDeleteMixin",
    "TenantMixin",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    # Identity
    "Hospital",
    "Permission",
    "RefreshToken",
    "Role",
    "RolePermission",
    "User",
    "UserRole",
    "UserStatus",
    # Patient
    "BloodGroup",
    "Gender",
    "MrnSequence",
    "Patient",
    "PatientStatus",
]
