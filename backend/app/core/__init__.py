"""Aetheris Core — configuration, security, logging, and foundational types.

This package contains cross-cutting concerns used by every other layer:

- :mod:`~app.core.config` — Pydantic Settings loaded from environment variables
- :mod:`~app.core.constants` — global constants and enums
- :mod:`~app.core.error_codes` — the ``error_code`` catalog
- :mod:`~app.core.envelope` — standard response envelope builders
- :mod:`~app.core.exceptions` — base exception hierarchy
- :mod:`~app.core.logging` — structured logging setup (structlog)
- :mod:`~app.core.lifecycle` — application startup/shutdown handlers
"""

from app.core.config import settings
from app.core.constants import (
    APP_ENV_DEVELOPMENT,
    APP_ENV_PRODUCTION,
    APP_ENV_STAGING,
    DATABASE_MODEL_NAMING_CONVENTION,
)
from app.core.envelope import error_envelope, paginated_envelope, success_envelope
from app.core.error_codes import ErrorCode
from app.core.exceptions import (
    AetherisError,
    BusinessRuleError,
    ConfigurationError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)

__all__ = [
    "settings",
    "APP_ENV_DEVELOPMENT",
    "APP_ENV_PRODUCTION",
    "APP_ENV_STAGING",
    "DATABASE_MODEL_NAMING_CONVENTION",
    "ErrorCode",
    "error_envelope",
    "paginated_envelope",
    "success_envelope",
    "AetherisError",
    "BusinessRuleError",
    "ConfigurationError",
    "NotFoundError",
    "PermissionDeniedError",
    "ValidationError",
]
