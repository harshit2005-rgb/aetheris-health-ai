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

import re
from enum import StrEnum
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
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


#: Shape of a model identifier accepted from configuration or echoed by a provider.
MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}$")

#: Hosts a plain-``http`` AI base URL may point at (a local stub only).
_LOCAL_HTTP_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


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
        # A validation error must not print the rejected value: it can be a
        # credential (a key, or a password inside a URL) and the error lands in
        # the startup traceback. The error still names the setting.
        hide_input_in_errors=True,
    )

    # ── App ────────────────────────────────────────────────────────────────
    APP_NAME: str = Field(
        default="Aetheris Health AI", description="Human-readable application name"
    )
    APP_ENV: AppEnv = Field(default=AppEnv.DEVELOPMENT, description="Deployment environment")
    APP_DEBUG: bool = Field(
        default=True, description="Enable debug mode (stack traces in responses)"
    )
    APP_BASE_URL: str = Field(
        default="http://localhost:8000", description="Public base URL of the API"
    )
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
    DATABASE_POOL_SIZE: int = Field(
        default=20, ge=1, le=100, description="Maximum connections in the pool"
    )
    DATABASE_MAX_OVERFLOW: int = Field(
        default=10, ge=0, description="Max overflow connections beyond pool_size"
    )
    DATABASE_ECHO: bool = Field(
        default=False, description="Log all SQL statements (development only)"
    )

    # ── Redis ──────────────────────────────────────────────────────────────
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")

    # ── Logging ────────────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(
        default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    LOG_FORMAT: LogFormat = Field(
        default=LogFormat.JSON, description="Log output format: json or console"
    )

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

    # ── JWT / Auth ─────────────────────────────────────────────────────────
    JWT_PRIVATE_KEY: str | None = Field(
        default=None,
        description="RSA private key for JWT signing (PEM). If None, uses HS256 with APP_SECRET_KEY.",
    )
    JWT_PUBLIC_KEY: str | None = Field(
        default=None,
        description="RSA public key for JWT verification (PEM). If None, uses HS256 with APP_SECRET_KEY.",
    )
    JWT_ISSUER: str = Field(default="aetheris", description="JWT issuer claim (iss)")
    JWT_ACCESS_TTL_SECONDS: int = Field(
        default=900, ge=60, le=86400, description="Access token TTL in seconds (default 15 min)"
    )
    JWT_REFRESH_TTL_SECONDS: int = Field(
        default=604800,
        ge=3600,
        le=2592000,
        description="Refresh token TTL in seconds (default 7 days)",
    )
    JWT_LEEWAY_SECONDS: int = Field(
        default=60, description="Clock skew leeway for JWT validation (seconds)"
    )

    # ── Auth Policy ─────────────────────────────────────────────────────────
    PASSWORD_MIN_LENGTH: int = Field(
        default=12, ge=8, le=128, description="Minimum password length"
    )
    MAX_FAILED_LOGIN_ATTEMPTS: int = Field(
        default=5, ge=1, le=20, description="Max failed attempts before lockout"
    )
    ACCOUNT_LOCKOUT_MINUTES: int = Field(
        default=30, ge=1, le=1440, description="Account lockout duration in minutes"
    )
    PASSWORD_RESET_TOKEN_TTL_MINUTES: int = Field(
        default=30, ge=5, le=1440, description="Password reset token lifetime in minutes"
    )
    INVITE_TOKEN_TTL_HOURS: int = Field(
        default=72, ge=1, le=720, description="Invitation token lifetime in hours (B6 invite seam)"
    )

    # ── Email (Notifications module) ───────────────────────────────────────
    # Email is OFF unless SMTP_HOST is set. With no host, a queued email is
    # marked failed with a clear reason and nothing leaves the process — the
    # safe default for a development database whose seeded staff addresses are
    # not on a reserved test domain.
    SMTP_HOST: str | None = Field(
        default=None, description="SMTP server host. Unset disables outbound email."
    )
    SMTP_PORT: int = Field(default=587, ge=1, le=65535, description="SMTP server port")
    SMTP_USER: str | None = Field(
        default=None, description="SMTP username, if the server needs one"
    )
    SMTP_PASSWORD: str | None = Field(default=None, description="SMTP password")
    SMTP_STARTTLS: bool = Field(default=True, description="Upgrade the connection with STARTTLS")
    EMAIL_FROM: str = Field(
        default="noreply@aetheris.health", description="From address for outbound email"
    )
    FRONTEND_BASE_URL: str = Field(
        default="http://localhost:5173",
        description="Public base URL of the web app, used to build links in emails",
    )

    # ── Rate Limiting ──────────────────────────────────────────────────────
    RATE_LIMIT_ANON_PER_MIN: int = Field(
        default=60, ge=1, description="Anonymous requests per minute"
    )
    RATE_LIMIT_USER_PER_MIN: int = Field(
        default=300, ge=1, description="Authenticated requests per minute"
    )
    RATE_LIMIT_AI_PER_MIN: int = Field(
        default=30, ge=1, description="AI endpoint requests per minute"
    )
    RATE_LIMIT_HOSPITAL_PER_MIN: int = Field(
        default=1000, ge=1, description="Requests per minute per hospital (tenant)"
    )
    RATE_LIMIT_TRUST_PROXY_HEADER: bool = Field(
        default=False,
        description="Trust X-Forwarded-For for the client IP. Enable ONLY behind a proxy that overwrites the header, otherwise clients can spoof it and evade the anonymous limit.",
    )

    # ── AI runtime ─────────────────────────────────────────────────────────
    # AI is OFF unless GROQ_API_KEY is set (and AI_ENABLED is not false). With
    # no key the application starts normally and every non-AI module works.
    GROQ_API_KEY: SecretStr | None = Field(
        default=None,
        description="Groq API key. Unset, empty or whitespace-only means AI is not configured.",
    )
    AI_ENABLED: bool | None = Field(
        default=None,
        description="AI kill switch. Unset = on when a key is present; false = off even with a key.",
    )
    GROQ_BASE_URL: str = Field(
        default="https://api.groq.com/openai/v1",
        description="Base URL of Groq's OpenAI-compatible API.",
    )
    AI_FAST_MODEL: str | None = Field(
        default=None,
        description="Model the 'fast' hint resolves to. Unset = the repository mapping.",
    )
    AI_REQUEST_TIMEOUT_SECONDS: float = Field(
        default=8.0, gt=0, le=30, description="Total deadline for one model call, in seconds."
    )
    GROQ_STRICT_JSON_SCHEMA: bool = Field(
        default=True,
        description=(
            "Send a strict JSON Schema as response_format so the model is structurally "
            "limited to the offered values. Turn off for a model that rejects it; the "
            "server validates the reply either way."
        ),
    )
    AI_MAX_CONCURRENT_CALLS: int = Field(
        default=4, ge=1, le=64, description="Provider calls this process may have in flight."
    )

    @field_validator("GROQ_API_KEY", mode="before")
    @classmethod
    def _blank_api_key_is_unset(cls, value: object) -> object:
        """Treat an empty or whitespace-only key as "not configured".

        Must never raise: a pydantic validation error prints its input value,
        which would put the key in the startup traceback. The key's characters
        are checked by the AI runtime, where a bad key disables AI instead.
        """
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("AI_ENABLED", mode="before")
    @classmethod
    def _blank_ai_enabled_is_unset(cls, value: object) -> object:
        """Read an empty ``AI_ENABLED=`` as unset rather than a boolean parse error."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("AI_FAST_MODEL", mode="before")
    @classmethod
    def _validate_fast_model(cls, value: object) -> object:
        """Strip the model id, treat blank as unset, and reject an odd shape."""
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            return None
        if MODEL_ID_PATTERN.fullmatch(stripped) is None:
            msg = "AI_FAST_MODEL is not a valid model identifier."
            raise ValueError(msg)
        return stripped

    @field_validator("GROQ_BASE_URL", mode="before")
    @classmethod
    def _validate_groq_base_url(cls, value: object) -> object:
        """Validate the base URL on its parsed form, never by string prefix.

        A prefix test would accept ``http://localhost.attacker.tld`` and
        ``http://localhost@attacker.tld``. The bearer key is therefore never
        sent over plain HTTP to a remote host, to a URL carrying credentials,
        or to one with a query or fragment.
        """
        if not isinstance(value, str):
            return value
        cleaned = value.strip().rstrip("/")
        message = (
            "GROQ_BASE_URL must be an https URL (or http to localhost) with a host and "
            "no credentials, query or fragment."
        )
        try:
            parts = urlsplit(cleaned)
            hostname = parts.hostname
            has_userinfo = parts.username is not None or parts.password is not None
        except ValueError:
            raise ValueError(message) from None
        valid = (
            parts.scheme in {"https", "http"}
            and bool(hostname)
            and not has_userinfo
            and parts.query == ""
            and parts.fragment == ""
            and "?" not in cleaned
            and "#" not in cleaned
            and (parts.scheme == "https" or hostname in _LOCAL_HTTP_HOSTS)
        )
        if not valid:
            raise ValueError(message)
        return cleaned

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
