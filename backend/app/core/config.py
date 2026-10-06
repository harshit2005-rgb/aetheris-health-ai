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

import hmac
import ipaddress
import json
import re
import secrets
from enum import StrEnum
from typing import Final, Self
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pydantic import Field, PrivateAttr, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Signing keys that were once published in this repository and are therefore
#: known to everyone: the former built-in default, which
#: ``backend/.env.example`` used to ship. A token signed with one of these can
#: be forged by anyone, so none of them is ever used to sign — see
#: ``Settings._resolve_secret_key``. This is a denylist, not a default: the
#: value stays here, for good, precisely so that it keeps being refused.
#: ``.env.example`` ships no key at all, and a test holds it to that.
PUBLISHED_SECRET_KEYS: Final[frozenset[str]] = frozenset(
    {
        "change-me-to-a-long-random-string-in-production",  # noqa: S105 — public by definition
    }
)

#: Shortest acceptable signing key, in characters.
MIN_SECRET_KEY_LENGTH: Final = 32

#: Smallest failure-duration floor accepted outside development, in seconds.
#: It has to exceed the slowest genuine failure, which includes one password
#: hash.
MIN_AUTH_FAILURE_SECONDS: Final = 0.25


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

    #: Set when development generated a per-process signing key.
    _secret_key_is_ephemeral: bool = PrivateAttr(default=False)

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
    # Signs every access token and MFA ticket. There is NO built-in key: a
    # default in the repository would let anyone forge a token for any staff
    # account. Staging and production refuse to start without a private key.
    # Development with no key (or with a published one) gets a random key for
    # the life of the process — see `_resolve_secret_key`.
    APP_SECRET_KEY: SecretStr = Field(
        default=SecretStr(""),
        description=(
            "Private key that signs access tokens and MFA tickets. Required outside "
            "development. At least 32 characters; never a value from this repository."
        ),
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
    # There are no lockout settings. Wrong passwords and codes are throttled
    # by app/services/auth_throttle.py, whose numbers are constants in code so
    # that configuration cannot weaken or disable them.
    PASSWORD_RESET_TOKEN_TTL_MINUTES: int = Field(
        default=30, ge=5, le=1440, description="Password reset token lifetime in minutes"
    )
    INVITE_TOKEN_TTL_HOURS: int = Field(
        default=72, ge=1, le=720, description="Invitation token lifetime in hours (B6 invite seam)"
    )

    # A rejected login, a rejected MFA code and every forgot-password request
    # take at least this long. Without it the response time says whether an
    # email belongs to a staff account: an unknown address is answered after
    # one lookup, a real one after several writes. The work is done first and
    # the remainder is waited out, with no database connection or row lock
    # held. Set it above the slowest genuine failure; 0 disables it (tests).
    AUTH_FAILURE_MIN_SECONDS: float = Field(
        default=0.5,
        ge=0.0,
        le=5.0,
        description="Minimum duration of a failed login/MFA attempt and of forgot-password.",
    )

    # The trusted-device cookie (app/services/auth_throttle.py) is sent with
    # `Secure` and the `__Host-` name prefix, which browsers honour only over
    # HTTPS. This may be switched off for plain-HTTP local development and
    # nowhere else: the application refuses to start with it off outside
    # development.
    AUTH_DEVICE_COOKIE_SECURE: bool = Field(
        default=True,
        description="Send the trusted-device cookie as Secure with the __Host- prefix.",
    )

    # ── MFA secret encryption at rest ──────────────────────────────────────
    # TOTP secrets are stored encrypted (app/core/security.py). The key is a
    # Fernet key: 32 random bytes, url-safe base64, 44 characters. Generate one
    # with `python -c "from cryptography.fernet import Fernet;
    # print(Fernet.generate_key().decode())"` and supply it from the secrets
    # manager. There is no default: a key in the repository protects nothing.
    #
    # Unset in development means MFA is unavailable (enrol and verify answer
    # 503) while everything else works. Staging and production refuse to start
    # without it. Every API instance that shares a database must share the key.
    MFA_ENCRYPTION_KEY: SecretStr | None = Field(
        default=None,
        description="Fernet key that encrypts MFA (TOTP) secrets at rest. Required outside development.",
    )
    MFA_ENCRYPTION_PREVIOUS_KEYS: SecretStr | None = Field(
        default=None,
        description=(
            "Comma-separated retired Fernet keys, still accepted for decryption "
            "while secrets are re-encrypted under MFA_ENCRYPTION_KEY."
        ),
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
        description="Trust X-Forwarded-For for the client IP. Enable ONLY behind a proxy we operate that appends to (or overwrites) the header; the address is read from the right-hand end, never from what the client sent.",
    )
    # How many of our own proxies stand between the internet and this process.
    # The client address is that many entries from the right of
    # X-Forwarded-For; everything further left is the client's own claim.
    # Too high and a client can forge its address; too low and every user
    # appears to come from the inner proxy. Used only when the flag above is on.
    # Which socket peers count as "our proxy". X-Forwarded-For is believed
    # only on a connection that comes from one of these networks; a client
    # that reaches the application directly cannot name its own address. The
    # default is every private and loopback range, which fits a proxy on the
    # same host, pod or private network. List a public range here only if the
    # proxy really does connect from one.
    RATE_LIMIT_TRUSTED_PROXY_CIDRS: list[str] = Field(
        default=[
            "127.0.0.0/8",
            "::1/128",
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
            "fc00::/7",
        ],
        description="Networks a trusted proxy connects from (JSON array from env).",
    )
    RATE_LIMIT_TRUSTED_PROXY_HOPS: int = Field(
        default=1,
        ge=1,
        le=8,
        description="Number of trusted proxies in front of the application (see RATE_LIMIT_TRUST_PROXY_HEADER).",
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

    @field_validator("APP_SECRET_KEY", mode="before")
    @classmethod
    def _blank_secret_key_is_unset(cls, value: object) -> object:
        """Treat a whitespace-only signing key as "not configured"."""
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("MFA_ENCRYPTION_KEY", "MFA_ENCRYPTION_PREVIOUS_KEYS", mode="before")
    @classmethod
    def _blank_mfa_key_is_unset(cls, value: object) -> object:
        """Treat an empty or whitespace-only key setting as "not configured"."""
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @model_validator(mode="after")
    def _validate_mfa_encryption_keys(self) -> Self:
        """Reject an unusable MFA key configuration before the app serves traffic.

        A malformed key would otherwise surface as a failure on the first MFA
        login. The messages name the setting and never the value
        (``hide_input_in_errors`` keeps pydantic from printing it either).

        :raises ValueError: If a key is not a valid Fernet key, if retired keys
            are given without a current one, or if no key is set outside
            development.
        """
        for name in ("MFA_ENCRYPTION_KEY", "MFA_ENCRYPTION_PREVIOUS_KEYS"):
            for key in self.mfa_encryption_keys(name):
                try:
                    Fernet(key)
                except (ValueError, TypeError):
                    msg = f"{name} must be a Fernet key (url-safe base64 of 32 bytes)."
                    raise ValueError(msg) from None

        if self.MFA_ENCRYPTION_KEY is None:
            if self.MFA_ENCRYPTION_PREVIOUS_KEYS is not None:
                msg = "MFA_ENCRYPTION_PREVIOUS_KEYS is set but MFA_ENCRYPTION_KEY is not."
                raise ValueError(msg)
            if self.APP_ENV is not AppEnv.DEVELOPMENT:
                msg = f"MFA_ENCRYPTION_KEY is required when APP_ENV is {self.APP_ENV.value}."
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _device_cookie_is_secure_outside_development(self) -> Self:
        """Refuse to run outside development with the device cookie sent in the clear."""
        if self.APP_ENV != AppEnv.DEVELOPMENT and not self.AUTH_DEVICE_COOKIE_SECURE:
            msg = f"AUTH_DEVICE_COOKIE_SECURE must be true when APP_ENV is {self.APP_ENV.value}."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _proxy_topology_is_declared_outside_development(self) -> Self:
        """Refuse to run outside development until someone has said whether a proxy is in front.

        Left unsaid, every caller behind an undeclared proxy would look like
        one source. ``RATE_LIMIT_TRUST_PROXY_HEADER`` must be set, to true or
        to false; there is no safe guess.
        """
        if (
            self.APP_ENV != AppEnv.DEVELOPMENT
            and "RATE_LIMIT_TRUST_PROXY_HEADER" not in self.model_fields_set
        ):
            msg = (
                "RATE_LIMIT_TRUST_PROXY_HEADER must be set explicitly (true or false) "
                f"when APP_ENV is {self.APP_ENV.value}."
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _failures_are_padded_outside_development(self) -> Self:
        """Refuse to run outside development with the failure-duration floor switched off.

        A throttled attempt does no password hashing and an evaluated one
        does; only the floor makes the two take the same time. Zero is for
        test suites.
        """
        if (
            self.APP_ENV != AppEnv.DEVELOPMENT
            and self.AUTH_FAILURE_MIN_SECONDS < MIN_AUTH_FAILURE_SECONDS
        ):
            msg = (
                f"AUTH_FAILURE_MIN_SECONDS must be at least {MIN_AUTH_FAILURE_SECONDS} "
                f"when APP_ENV is {self.APP_ENV.value}."
            )
            raise ValueError(msg)
        return self

    @field_validator("RATE_LIMIT_TRUSTED_PROXY_CIDRS", mode="before")
    @classmethod
    def _parse_trusted_proxy_cidrs(cls, value: object) -> object:
        """Accept a JSON array string from the environment, and insist on real networks."""
        parsed = json.loads(value) if isinstance(value, str) else value
        if not isinstance(parsed, list):
            msg = "RATE_LIMIT_TRUSTED_PROXY_CIDRS must be a list of networks."
            raise ValueError(msg)  # noqa: TRY004 — pydantic reports ValueError, not TypeError
        networks = []
        for network in parsed:
            try:
                networks.append(ipaddress.ip_network(str(network), strict=False))
            except ValueError:
                msg = "RATE_LIMIT_TRUSTED_PROXY_CIDRS contains a value that is not a network."
                raise ValueError(msg) from None
        # "Everyone is our proxy" is the same as believing whatever address a
        # caller claims — whether written as one network or as several that
        # add up to one.
        v4 = [network for network in networks if isinstance(network, ipaddress.IPv4Network)]
        v6 = [network for network in networks if isinstance(network, ipaddress.IPv6Network)]
        covers_everything = any(
            merged.prefixlen == 0 for merged in ipaddress.collapse_addresses(v4)
        ) or any(merged.prefixlen == 0 for merged in ipaddress.collapse_addresses(v6))
        if covers_everything:
            msg = "RATE_LIMIT_TRUSTED_PROXY_CIDRS must not cover every address."
            raise ValueError(msg)
        return parsed

    @model_validator(mode="after")
    def _resolve_secret_key(self) -> Self:
        """Make sure tokens are only ever signed with a private key.

        ``APP_SECRET_KEY`` signs every access token and MFA ticket; whoever
        knows it can mint a valid token for any staff account, with no
        password and no MFA code. So a key that is missing, too short, or
        published in this repository is never used:

        * **Staging and production** refuse to start. There is no fallback.
        * **Development** replaces a missing or published key with a random
          one generated for this process. Nothing known to anyone else ever
          signs a token — including when a real deployment is started in
          development mode by mistake. The cost is that sessions end when the
          process restarts; set a private key in ``.env`` to keep them.

        The messages name the setting and never the value.

        :raises ValueError: Outside development, if the key is unset, is a
            published value, or is too short; in development, if a key is set
            but too short.
        """
        key = self.APP_SECRET_KEY.get_secret_value()
        # Compared without surrounding quotes as well: the published value was
        # shipped quoted, and not every way of loading an env file strips them.
        candidates = {key, key.strip("\"'")}
        published = any(
            hmac.compare_digest(candidate.encode(), known.encode())
            for candidate in candidates
            for known in PUBLISHED_SECRET_KEYS
        )

        if self.APP_ENV is not AppEnv.DEVELOPMENT:
            if not key:
                msg = f"APP_SECRET_KEY is required when APP_ENV is {self.APP_ENV.value}."
                raise ValueError(msg)
            if published:
                msg = (
                    "APP_SECRET_KEY is set to a value published in the repository; "
                    f"a private key is required when APP_ENV is {self.APP_ENV.value}."
                )
                raise ValueError(msg)

        if not key or published:
            self.APP_SECRET_KEY = SecretStr(secrets.token_urlsafe(48))
            self._secret_key_is_ephemeral = True
        elif len(key) < MIN_SECRET_KEY_LENGTH:
            msg = f"APP_SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters."
            raise ValueError(msg)
        return self

    @property
    def secret_key_is_ephemeral(self) -> bool:
        """True if this process generated its own signing key (development only)."""
        return self._secret_key_is_ephemeral

    def mfa_encryption_keys(self, name: str = "MFA_ENCRYPTION_KEY") -> list[bytes]:
        """Return the keys held in one MFA key setting, in order.

        :param name: ``MFA_ENCRYPTION_KEY`` (at most one key) or
            ``MFA_ENCRYPTION_PREVIOUS_KEYS`` (comma-separated).
        :returns: The keys as bytes; empty when the setting is unset.
        """
        value: SecretStr | None = getattr(self, name)
        if value is None:
            return []
        return [
            part.strip().encode() for part in value.get_secret_value().split(",") if part.strip()
        ]

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
