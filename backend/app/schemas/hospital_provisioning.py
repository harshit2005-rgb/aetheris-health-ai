"""DTOs for provisioning a new hospital (``docs/modules/14-hospital-settings.md`` §5, §9, §11).

Platform-level: only a holder of ``platform.hospital.provision`` (Super Admin)
reaches these, through ``POST /admin/hospitals`` or ``make provision-hospital``.
"""

from __future__ import annotations

import re
from typing import Any, Final, Literal
from uuid import UUID  # noqa: TC003
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "InitialAdmin",
    "ProvisionHospitalRequest",
    "ProvisionedHospitalResponse",
    "RESERVED_SLUGS",
]

#: §11: lowercase letters, digits and inner hyphens, 4 to 50 characters.
_SLUG: Final = re.compile(r"^[a-z0-9][a-z0-9-]{2,48}[a-z0-9]$")

#: Slugs that would collide with platform paths and names (§11).
RESERVED_SLUGS: Final = frozenset(
    {
        "admin",
        "api",
        "app",
        "www",
        "static",
        "assets",
        "platform",
        "login",
        "auth",
        "patient",
        "atheris",
    }
)

_EMAIL = r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$"
_PHONE = r"^\+?[0-9][0-9 -]{4,19}$"


class InitialAdmin(BaseModel):
    """The hospital's first administrator. Invited by email; no password is set here."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=255, pattern=_EMAIL)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20, pattern=_PHONE)


class ProvisionHospitalRequest(BaseModel):
    """Body of ``POST /admin/hospitals``.

    The address uses the platform's canonical keys (``line1``, ``city``,
    ``state``, ``postal_code``, ``country``), the same as patients.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(description="URL-safe identifier; unique and permanent (§4 rule 3).")
    timezone: str = Field(default="Asia/Kolkata", description="IANA timezone.")
    currency: str = Field(default="INR", description="ISO 4217 code.")
    email: str | None = Field(default=None, max_length=200, pattern=_EMAIL)
    phone: str | None = Field(default=None, max_length=20, pattern=_PHONE)
    address: dict[str, Any] = Field(
        default_factory=dict, description="line1, city, state, postal_code, country."
    )
    admin: InitialAdmin

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, value: str) -> str:
        """§11: the pattern, and not a reserved word."""
        if not _SLUG.fullmatch(value):
            msg = "Use 4-50 lowercase letters, digits and inner hyphens, e.g. 'city-care'."
            raise ValueError(msg)
        if value in RESERVED_SLUGS:
            msg = f"'{value}' is reserved."
            raise ValueError(msg)
        return value

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        """§4 rule 4: a real IANA zone."""
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            msg = "Not a known IANA timezone, e.g. 'Asia/Kolkata'."
            raise ValueError(msg) from None
        return value

    @field_validator("currency")
    @classmethod
    def _check_currency(cls, value: str) -> str:
        """§4 rule 5: an ISO 4217 code."""
        if not re.fullmatch(r"[A-Z]{3}", value):
            msg = "Use a three-letter ISO 4217 code, e.g. 'INR'."
            raise ValueError(msg)
        return value

    @field_validator("address")
    @classmethod
    def _check_address(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Only the canonical keys, each a short string."""
        allowed = {"line1", "line2", "city", "state", "postal_code", "country"}
        unknown = set(value) - allowed
        if unknown:
            msg = f"Unknown address keys: {', '.join(sorted(unknown))}."
            raise ValueError(msg)
        if any(not isinstance(v, str) or len(v) > 200 for v in value.values()):
            msg = "Address values must be text of at most 200 characters."
            raise ValueError(msg)
        return value


class ProvisionedHospitalResponse(BaseModel):
    """What provisioning created. Never an activation link: that goes only by email."""

    hospital_id: UUID
    name: str
    slug: str
    admin_user_id: UUID
    admin_email: str
    invitation: Literal["queued", "unavailable"] = Field(
        description=(
            "'queued': the admin's activation email was queued. 'unavailable': this "
            "server has no mail transport, so no link exists yet; re-send the invitation "
            "once email is configured."
        )
    )
