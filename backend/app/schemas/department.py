"""Pydantic DTOs for the Department module.

Request models validate everything listed in
``docs/modules/14-hospital-settings.md`` §11 before a service ever sees it
(``docs/07-SECURITY.md``, rule 5). Response models are the only department
shapes that cross the API boundary — SQLAlchemy models never do
(``docs/03-ARCHITECTURE.md`` §15, rule 7).

Usage::

    from app.schemas.department import CreateDepartmentRequest, DepartmentResponse

    payload = CreateDepartmentRequest.model_validate(body)
    response = DepartmentResponse.from_model(department)
"""

from __future__ import annotations

import re

# NOTE: ``datetime`` and ``UUID`` must be imported at runtime, not under
# TYPE_CHECKING. Pydantic resolves field annotations against the module's real
# globals when it builds each model, so a TYPE_CHECKING-only import raises
# NameError at import time (see backend/CLAUDE.md, "Common Pitfalls").
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Annotated, Any, Self
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.department import CODE_PATTERN, DepartmentStatus
from app.schemas.common import Page

if TYPE_CHECKING:
    from app.models.department import Department

__all__ = [
    "CreateDepartmentRequest",
    "DepartmentListResponse",
    "DepartmentResponse",
    "DepartmentStatus",
    "DepartmentSummaryResponse",
    "SearchDepartmentRequest",
    "UpdateDepartmentRequest",
]

#: Compiled form of the code rule shared with the model and the database check
#: constraint. Imported from :mod:`app.models.department` rather than restated
#: so all three can never drift apart.
_CODE_RE = re.compile(CODE_PATTERN)

#: Internal phone extensions are digits and dashes only. Not E.164 — an
#: extension is not a dialable number, so ``app.utils.phone`` does not apply.
_EXTENSION_RE = re.compile(r"^[0-9-]{1,10}$")

#: Pragmatic RFC 5322 subset, identical to the one in
#: :mod:`app.schemas.patient`. ``pydantic.EmailStr`` would be the obvious
#: choice but needs the ``email-validator`` package, and new dependencies are a
#: review decision (CLAUDE.md, "What NOT to Do").
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")

#: Reusable constrained string for a department name (module spec §11).
DepartmentName = Annotated[str, Field(min_length=2, max_length=150)]

#: Update fields whose columns are ``NOT NULL``. They are declared optional on
#: :class:`UpdateDepartmentRequest` so a PATCH can omit them, but sending an
#: explicit ``null`` is rejected — see
#: :meth:`UpdateDepartmentRequest._reject_null_for_non_nullable_columns`.
_NON_NULLABLE_UPDATE_FIELDS = frozenset({"code", "name"})


def _validate_code(value: str) -> str:
    """Normalise and validate a department code.

    Uppercased before matching (module spec §4, rule 11), so ``card`` and
    ``CARD`` are the same code rather than two that collide only at the
    database.

    :param value: The raw code.
    :returns: The uppercased, trimmed code.
    :raises ValueError: If the code does not match :data:`CODE_PATTERN`.
    """
    normalized = value.strip().upper()
    if not _CODE_RE.match(normalized):
        msg = (
            "Code must be 2–20 characters, start with a letter or digit, and "
            "contain only letters, digits, hyphens, and underscores."
        )
        raise ValueError(msg)
    return normalized


def _validate_name(value: str) -> str:
    """Trim a department name and reject one that is only whitespace.

    :param value: The raw name.
    :returns: The trimmed name.
    :raises ValueError: If the name is blank after trimming.
    """
    stripped = value.strip()
    if len(stripped) < 2:
        msg = "Name must be at least 2 non-whitespace characters."
        raise ValueError(msg)
    return stripped


def _validate_optional_email(value: str | None) -> str | None:
    """Normalize and validate an optional department email address.

    Blank strings become ``None`` so that "cleared" and "never set" are the
    same state in the database rather than two states that sort differently.

    :param value: The raw email value.
    :returns: The lowercased, trimmed address, or ``None``.
    :raises ValueError: If the value is non-blank and not a valid address.
    """
    if value is None:
        return None
    stripped = value.strip().lower()
    if not stripped:
        return None
    if len(stripped) > 200:
        msg = "Email must be at most 200 characters."
        raise ValueError(msg)
    if not _EMAIL_PATTERN.match(stripped):
        msg = "Must be a valid email address."
        raise ValueError(msg)
    return stripped


def _validate_optional_extension(value: str | None) -> str | None:
    """Validate an optional internal phone extension.

    :param value: The raw extension.
    :returns: The trimmed extension, or ``None`` when blank.
    :raises ValueError: If the value contains anything but digits and hyphens.
    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if not _EXTENSION_RE.match(stripped):
        msg = "Extension must be 1–10 characters of digits and hyphens only."
        raise ValueError(msg)
    return stripped


def _blank_to_none(value: str | None) -> str | None:
    """Collapse a blank optional string to ``None``.

    :param value: The raw value.
    :returns: The trimmed value, or ``None`` when blank.
    """
    if value is None:
        return None
    return value.strip() or None


# ── Requests ────────────────────────────────────────────────────────────────


class CreateDepartmentRequest(BaseModel):
    """Payload for ``POST /api/v1/departments``.

    ``hospital_id`` is deliberately absent: it comes from the authenticated
    user, never from the request body, so a caller cannot create a department
    inside another tenant.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "code": "CARD",
                "name": "Cardiology",
                "description": "Diagnosis and treatment of heart conditions.",
                "phone_extension": "204",
                "email": "cardiology@demohospital.test",
                "location": "Block B, 3rd Floor",
            },
        },
    )

    code: str = Field(
        max_length=20,
        description="Short department code, e.g. 'CARD'. Uppercased automatically.",
    )
    name: DepartmentName = Field(description="Department name, e.g. 'Cardiology'.")
    description: str | None = Field(
        default=None, max_length=2000, description="What the department does."
    )
    phone_extension: str | None = Field(
        default=None, max_length=10, description="Internal phone extension."
    )
    email: str | None = Field(default=None, description="Department inbox address.")
    location: str | None = Field(default=None, max_length=150, description="Floor, wing, or block.")

    @field_validator("code")
    @classmethod
    def _check_code(cls, value: str) -> str:
        """Uppercase and validate the department code (module spec §11)."""
        return _validate_code(value)

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        """Trim the name and reject a blank one."""
        return _validate_name(value)

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str | None) -> str | None:
        """Normalize to lowercase and reject malformed addresses."""
        return _validate_optional_email(value)

    @field_validator("phone_extension")
    @classmethod
    def _check_extension(cls, value: str | None) -> str | None:
        """Reject an extension containing anything but digits and hyphens."""
        return _validate_optional_extension(value)

    @field_validator("description", "location")
    @classmethod
    def _trim_optional(cls, value: str | None) -> str | None:
        """Trim optional free text, collapsing blank to ``None``."""
        return _blank_to_none(value)


class UpdateDepartmentRequest(BaseModel):
    """Payload for ``PATCH /api/v1/departments/{id}``.

    Every field is optional; only fields actually present in the request body
    are applied. ``hospital_id`` is immutable and is not accepted —
    ``extra="forbid"`` turns an attempt to set it into a 422 rather than a
    silent no-op.
    """

    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(
        default=None, max_length=20, description="Short department code. Uppercased automatically."
    )
    name: DepartmentName | None = Field(default=None, description="Department name.")
    description: str | None = Field(
        default=None, max_length=2000, description="What the department does."
    )
    phone_extension: str | None = Field(
        default=None, max_length=10, description="Internal phone extension."
    )
    email: str | None = Field(default=None, description="Department inbox address.")
    location: str | None = Field(default=None, max_length=150, description="Floor, wing, or block.")

    @field_validator("code")
    @classmethod
    def _check_code(cls, value: str | None) -> str | None:
        """Uppercase and validate the department code (module spec §11)."""
        return _validate_code(value) if value is not None else None

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str | None) -> str | None:
        """Trim the name and reject a blank one."""
        return _validate_name(value) if value is not None else None

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str | None) -> str | None:
        """Normalize to lowercase and reject malformed addresses."""
        return _validate_optional_email(value)

    @field_validator("phone_extension")
    @classmethod
    def _check_extension(cls, value: str | None) -> str | None:
        """Reject an extension containing anything but digits and hyphens."""
        return _validate_optional_extension(value)

    @field_validator("description", "location")
    @classmethod
    def _trim_optional(cls, value: str | None) -> str | None:
        """Trim optional free text, collapsing blank to ``None``."""
        return _blank_to_none(value)

    @model_validator(mode="after")
    def _reject_empty_patch(self) -> Self:
        """Reject a PATCH body with no fields — it is always a client bug."""
        if not self.model_fields_set:
            msg = "Update request must contain at least one field."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _reject_null_for_non_nullable_columns(self) -> Self:
        """Reject an explicit ``null`` on a column the database requires.

        ``code`` and ``name`` are ``| None`` so they can be *omitted*, but the
        columns are ``NOT NULL``. Without this check,
        ``PATCH {"name": null}`` would reach the database and come back as a
        500 IntegrityError instead of a 422 naming the field.
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

    def changed_fields(self) -> dict[str, Any]:
        """Return only the fields the client actually sent.

        :returns: Mapping of column name to new value, for set fields only.
        """
        return self.model_dump(exclude_unset=True, mode="json")


class SearchDepartmentRequest(BaseModel):
    """Query parameters for ``GET /api/v1/departments``.

    ``q`` is the single free-text term: it prefix-matches name
    case-insensitively and exact-matches code.
    """

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(
        default=None,
        max_length=150,
        description="Free-text term: name prefix or exact code.",
    )
    include_inactive: bool = Field(
        default=False,
        description="Include deactivated (soft-deleted) departments.",
    )

    @field_validator("q")
    @classmethod
    def _strip_q(cls, value: str | None) -> str | None:
        """Trim the search term and treat a blank term as absent."""
        if value is None:
            return None
        return value.strip() or None


# ── Responses ───────────────────────────────────────────────────────────────


class DepartmentSummaryResponse(BaseModel):
    """Compact department shape for list views and cross-module references."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Department UUID.")
    code: str = Field(description="Short department code, unique per hospital.")
    name: str = Field(description="Department name.")
    location: str | None = Field(description="Floor, wing, or block.")
    status: DepartmentStatus = Field(description="active or inactive (derived from soft delete).")

    @classmethod
    def from_model(cls, department: Department) -> Self:
        """Build a summary DTO from an ORM instance.

        :param department: The ORM instance to convert.
        :returns: The populated DTO.
        """
        return cls(
            id=department.id,
            code=department.code,
            name=department.name,
            location=department.location,
            status=department.status,
        )


class DepartmentResponse(BaseModel):
    """Full department record returned by create, get, and update."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Department UUID.")
    hospital_id: UUID = Field(description="Owning hospital (tenant) UUID.")
    code: str = Field(description="Short department code, unique per hospital.")
    name: str = Field(description="Department name.")
    description: str | None = Field(description="What the department does.")
    phone_extension: str | None = Field(description="Internal phone extension.")
    email: str | None = Field(description="Department inbox address.")
    location: str | None = Field(description="Floor, wing, or block.")
    status: DepartmentStatus = Field(description="active or inactive (derived from soft delete).")
    created_at: datetime = Field(description="Creation timestamp (UTC).")
    updated_at: datetime = Field(description="Last update timestamp (UTC).")

    @classmethod
    def from_model(cls, department: Department) -> Self:
        """Build a full DTO from an ORM instance.

        :param department: The ORM instance to convert.
        :returns: The populated DTO.
        """
        return cls.model_validate(department)


#: One page of department summaries — the body of a list or search response.
DepartmentListResponse = Page[DepartmentSummaryResponse]
