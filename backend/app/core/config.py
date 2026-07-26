"""Application configuration via Pydantic Settings v2.

All configuration values are loaded from environment variables.
Secrets are never hardcoded — every sensitive value comes from
.env or the process environment.

Usage::

    from app.core.config import settings

    db_url = settings.DATABASE_URL
    debug = settings.APP_DEBUG
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    """Valid deployment environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogFormat(StrEnum):
    """Supported structured-logging output formats."""

    JSON = "json"
    CONSOLE = "console"


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Values are populated from (in order of precedence):
    1. Environment variables (highest)
    2. .env file
    3. Default values defined below
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )

    # ── App ────────────────────────────────────────────────────────────────
    APP_NAME: str = Field(default="Aetheris Health AI", description="Human-readable application name")
    APP_ENV: AppEnv = Field(default=AppEnv.DEVELOPMENT, description="Deployment environment")
    APP_DEBUG: bool = Field(default=True, description="Enable debug mode (stack traces in responses)")
    APP_BASE_URL: str = Field(default="http://localhost:8000", description="Public base URL of the API")
    APP_SECRET_KEY: str = Field(
        default="change-me-to-a-long-random-string-in-production",
        description="Secret key for signing internal tokens and encryption",
        min_length=32,
    )

    # ── Database ───────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://aetheris:aetheris@localhost:5432/aetheris",
        description="Async PostgreSQL connection string (asyncpg driver)",
    )
    DATABASE_POOL_SIZE: int = Field(default=20, ge=1, le=100, description="Maximum connections in the pool")
    DATABASE_MAX_OVERFLOW: int = Field(default=10, ge=0, description="Max overflow connections beyond pool_size")
    DATABASE_ECHO: bool = Field(default=False, description="Log all SQL statements (development only)")

    # ── Redis ──────────────────────────────────────────────────────────────
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")

    # ── Logging ────────────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)")
    LOG_FORMAT: LogFormat = Field(default=LogFormat.JSON, description="Log output format: json or console")

    # ── CORS ───────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins (JSON array string from env)",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        """Parse CORS_ORIGINS from a JSON string or pass through a list."""
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            import json

            try:
                result = json.loads(value)
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return []

    # ── Rate Limiting ──────────────────────────────────────────────────────
    RATE_LIMIT_ANON_PER_MIN: int = Field(default=60, ge=1, description="Anonymous requests per minute")
    RATE_LIMIT_USER_PER_MIN: int = Field(default=300, ge=1, description="Authenticated requests per minute")
    RATE_LIMIT_AI_PER_MIN: int = Field(default=30, ge=1, description="AI endpoint requests per minute")

    @property
    def is_development(self) -> bool:
        """True when running in development mode."""
        return self.APP_ENV == AppEnv.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        """True when running in production mode."""
        return self.APP_ENV == AppEnv.PRODUCTION


# Singleton — import this, don't instantiate Settings yourself.
settings = Settings()
