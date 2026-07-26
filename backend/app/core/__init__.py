"""Aetheris Core — Application configuration, security, logging, and foundational types.

This package contains cross-cutting concerns used by every other layer:

- :attr:`config`: Pydantic Settings loaded from environment variables.
- :attr:`constants`: Global constants, enums, and status codes.
- :attr:`exceptions`: Base exception hierarchy for the entire application.
- :attr:`logging`: Structured logging setup (structlog).
- :attr:`lifecycle`: Application startup/shutdown event handlers.
"""

from app.core.config import settings
from app.core.constants import (
    APP_ENV_DEVELOPMENT,
    APP_ENV_PRODUCTION,
    APP_ENV_STAGING,
    DATABASE_MODEL_NAMING_CONVENTION,
)
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
    "AetherisError",
    "BusinessRuleError",
    "ConfigurationError",
    "NotFoundError",
    "PermissionDeniedError",
    "ValidationError",
]
