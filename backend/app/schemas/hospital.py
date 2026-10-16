"""Pydantic DTOs for the Hospital Settings module.

Request models validate everything listed in
``docs/modules/14-hospital-settings.md`` §11 before a service sees it
(``docs/07-SECURITY.md`` rule 5). The update model forbids unknown fields, so
the restricted columns the spec reserves for Superadmin approval — ``slug``,
``timezone``, ``currency``, ``tax_id`` (§9) — are rejected with a 422 rather
than silently ignored: the caller learns the write did not happen.
"""

from __future__ import annotations

# NOTE: ``datetime``/``UUID`` must be imported at runtime, not under
# TYPE_CHECKING — Pydantic resolves annotations against the module globals.
from datetime import datetime, time  # noqa: TC003
from typing import Any, Self  # noqa: TC003
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "FeatureFlagState",
    "FeatureFlagsResponse",
    "HospitalPublicResponse",
    "HospitalSettingsResponse",
    "SetWorkingHoursRequest",
    "UpdateHospitalSettingsRequest",
    "WorkingHoursDay",
    "WorkingHoursDayResponse",
]

#: Update fields whose columns are ``NOT NULL``. Declared optional so a PATCH
#: can omit them, but an explicit ``null`` is rejected — see
#: :meth:`UpdateHospitalSettingsRequest._reject_null_for_non_nullable_columns`.
#: ``phone``, ``email`` and ``logo_url`` are intentionally absent: their columns
#: are nullable, so ``null`` is the supported way to clear them.
_NON_NULLABLE_UPDATE_FIELDS = frozenset({"name", "address", "locale", "settings"})

#: Keys in ``hospitals.settings`` that are feature flags, e.g.
#: ``feature.ai.slot_recommendation``. Read-only to a hospital admin.
_FEATURE_FLAG_PREFIX = "feature."

#: Pragmatic RFC 5322 subset, identical to the one in
#: :mod:`app.schemas.department` (no new dependencies — CLAUDE.md).
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$"

#: Permissive phone shape: digits with optional spaces, dashes and a leading +.
_PHONE_PATTERN = r"^\+?[0-9][0-9 -]{4,19}$"


class HospitalPublicResponse(BaseModel):
    """Branding/public fields any authenticated user may read (§9)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Hospital UUID.")
    name: str = Field(description="Full hospital name.")
    slug: str = Field(description="URL-friendly identifier.")
    address: dict[str, Any] = Field(description="Structured address.")
    phone: str | None = Field(default=None, description="Primary contact phone.")
    email: str | None = Field(default=None, description="Primary contact email.")
    logo_url: str | None = Field(default=None, description="Logo URL.")
    timezone: str = Field(description="IANA timezone.")
    currency: str = Field(description="ISO 4217 currency code.")
    locale: str = Field(description="Locale for formatting.")
    is_active: bool = Field(description="Whether the hospital is active.")


class HospitalSettingsResponse(HospitalPublicResponse):
    """Everything ``GET /hospitals/current/full`` returns (settings.read)."""

    tax_id: str | None = Field(default=None, description="Tax / registration ID.")
    settings: dict[str, Any] = Field(
        default_factory=dict, description="Working hours, policies, feature flags."
    )
    created_at: datetime = Field(description="Creation timestamp.")
    updated_at: datetime = Field(description="Last update timestamp.")


class UpdateHospitalSettingsRequest(BaseModel):
    """Editable hospital fields for ``PATCH /hospitals/current`` (§9).

    ``extra="forbid"`` is load-bearing: restricted fields (``slug``,
    ``timezone``, ``currency``, ``tax_id``) and typos produce a 422 instead of
    being dropped, so an admin never believes a save landed when it did not.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=200)
    address: dict[str, Any] | None = Field(
        default=None, description="Structured address (street, city, state, zip, country)."
    )
    phone: str | None = Field(default=None, max_length=20, pattern=_PHONE_PATTERN)
    email: str | None = Field(default=None, max_length=200, pattern=_EMAIL_PATTERN)
    locale: str | None = Field(
        default=None, max_length=10, pattern=r"^[a-z]{2}(-[A-Za-z0-9]{2,8})*$"
    )
    logo_url: str | None = Field(default=None, max_length=500)
    settings: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Working hours / policies. **Merged** into the stored object key by "
            "key: keys not sent are kept, and a key sent as null is removed. "
            "Feature flags (`feature.*`) cannot be set here."
        ),
    )

    @field_validator("address")
    @classmethod
    def _address_values_are_scalars(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        """The address is a flat string map — no nested objects (§2.3)."""
        if value is None:
            return None
        if len(value) > 20:
            msg = "Address has too many fields."
            raise ValueError(msg)
        for key, item in value.items():
            if not isinstance(item, str):
                msg = f"Address field '{key}' must be a string."
                raise ValueError(msg)
            if len(item) > 300:
                msg = f"Address field '{key}' is too long."
                raise ValueError(msg)
        return value

    @field_validator("settings")
    @classmethod
    def _no_feature_flags(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        """Refuse feature flags in a hospital admin's settings update.

        Module spec §4 rule 8 and §10: flags are toggled only by the platform
        Superadmin (``platform.feature_flags.toggle``), and the Settings page
        shows them read-only to a hospital admin. They live in the same JSONB
        object as the editable policies, so without this check an admin could
        switch on a gated feature for their own hospital with one PATCH.
        """
        if value is None:
            return None
        flags = sorted(key for key in value if key.startswith(_FEATURE_FLAG_PREFIX))
        if flags:
            msg = (
                f"Feature flags can only be changed by a platform administrator: "
                f"{', '.join(flags)}."
            )
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _reject_null_for_non_nullable_columns(self) -> Self:
        """Reject an explicit ``null`` on a column the database requires.

        Every field here is ``| None`` so that it can be *omitted*, but ``name``,
        ``address``, ``locale`` and ``settings`` back ``NOT NULL`` columns.
        Because the service uses ``model_dump(exclude_unset=True)`` — which keeps
        explicit nulls — ``PATCH {"name": null}`` used to reach the database and
        return a 500 IntegrityError instead of a 422 naming the field (PR #29
        review finding 4; same pattern as ``app.schemas.patient``).
        """
        offenders = sorted(
            name
            for name in _NON_NULLABLE_UPDATE_FIELDS & self.model_fields_set
            if getattr(self, name) is None
        )
        if offenders:
            msg = f"These fields cannot be set to null: {', '.join(offenders)}."
            raise ValueError(msg)
        return self


class FeatureFlagState(BaseModel):
    """Whether one gated feature can be used right now.

    One boolean, on purpose. Any signed-in user of the hospital can read it,
    including roles that cannot use the feature, so it does not say *why* a
    feature is unavailable: a separate "flag is on" value would let them infer
    from "on but unavailable" that the server has no AI key.
    """

    available: bool = Field(
        description=(
            "The hospital's flag is on AND the server is configured to serve the "
            "feature. Configured is not the same as reachable."
        )
    )


class FeatureFlagsResponse(BaseModel):
    """The gated features of the caller's hospital (module spec §9)."""

    flags: dict[str, FeatureFlagState] = Field(
        description="Only the well-known flag keys; never other hospital settings."
    )


# ── Working hours (§8 ``hospital_working_hours``, §9, §11) ───────────────────


class WorkingHoursDay(BaseModel):
    """One day of the hospital's week: open between two times, open all day, or closed.

    ``is_24h`` with no times is open all day; no times and not ``is_24h`` is
    closed; otherwise both times are given and ``close_time`` is after
    ``open_time`` (§11). Times are the hospital's wall clock.
    """

    model_config = ConfigDict(extra="forbid")

    day_of_week: int = Field(ge=0, le=6, description="0=Monday .. 6=Sunday.")
    is_24h: bool = Field(default=False, description="Open all day.")
    open_time: time | None = Field(
        default=None, description="Opening time. Null when closed or all day."
    )
    close_time: time | None = Field(
        default=None, description="Closing time. Null when closed or all day."
    )

    @model_validator(mode="after")
    def _check_shape(self) -> Self:
        """Enforce the three shapes the table allows (§11)."""
        times = (self.open_time, self.close_time)
        if self.is_24h:
            if times != (None, None):
                msg = "A day open all day has no opening or closing time."
                raise ValueError(msg)
        elif (self.open_time is None) != (self.close_time is None):
            msg = "Give both an opening and a closing time, or neither for a closed day."
            raise ValueError(msg)
        elif (
            self.open_time is not None
            and self.close_time is not None
            and self.close_time <= self.open_time
        ):
            msg = "close_time must be after open_time."
            raise ValueError(msg)
        return self


class SetWorkingHoursRequest(BaseModel):
    """Body of ``PUT /hospitals/current/working-hours``: the whole week, replacing what is stored.

    A day left out has no entry, which the app shows as "not set"; send it
    with no times to mark it closed.
    """

    model_config = ConfigDict(extra="forbid")

    days: list[WorkingHoursDay] = Field(
        default_factory=list, max_length=7, description="Up to one entry per day."
    )

    @model_validator(mode="after")
    def _one_entry_per_day(self) -> Self:
        """Refuse a day given twice: the table holds one row per day."""
        seen = [day.day_of_week for day in self.days]
        if len(seen) != len(set(seen)):
            msg = "Each day of the week may appear only once."
            raise ValueError(msg)
        return self


class WorkingHoursDayResponse(BaseModel):
    """One stored day of the hospital's week."""

    model_config = ConfigDict(from_attributes=True)

    day_of_week: int = Field(description="0=Monday .. 6=Sunday.")
    is_24h: bool = Field(description="Open all day.")
    open_time: time | None = Field(description="Opening time, or null.")
    close_time: time | None = Field(description="Closing time, or null.")
