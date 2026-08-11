"""Shared Pydantic schemas for API request/response models.

These schemas are used across every endpoint. They define the standard shapes
for pagination, envelopes, error responses, and metadata blocks.

Placement rule (``docs/09-PROJECT_STRUCTURE.md``): shared pagination, envelope,
and error shapes go in ``app/schemas/common.py``.

The envelope builders in :mod:`app.core.envelope` produce raw dicts for the
FastAPI exception handlers and middleware. The schemas here are the typed
Pydantic models that route handlers return as ``response_model``.
"""

from __future__ import annotations

import math
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

# ── Type variable for generic data payloads ──────────────────────────────────
DataT = TypeVar("DataT")

# ── Metadata ─────────────────────────────────────────────────────────────────


class Metadata(BaseModel):
    """Standard metadata block included in every API response envelope.

    .. attribute:: request_id

        Correlation UUID for the request. Present in every response.
    """

    request_id: str | None = Field(
        default=None,
        description="Correlation UUID for the request.",
    )


class MetadataWithPagination(Metadata):
    """Metadata block that includes pagination information.

    Extends :class:`Metadata` with a nested ``pagination`` attribute.
    Used in list responses (``docs/06-API_STANDARDS.md`` §5.2).
    """

    pagination: PaginationMeta | None = None


class PaginationMeta(BaseModel):
    """Pagination metadata attached to list-response envelopes.

    .. attribute:: page

        1-based page number.

    .. attribute:: page_size

        Number of items per page (clamped to ``MAX_PAGE_SIZE``).

    .. attribute:: total_records

        Total records matching the query across all pages.

    .. attribute:: total_pages

        Total number of pages computed from ``total_records / page_size``.
    """

    page: int = Field(ge=1, description="1-based page number.")
    page_size: int = Field(ge=1, le=100, description="Items per page.")
    total_records: int = Field(ge=0, description="Total records matching the query.")
    total_pages: int = Field(ge=0, description="Total number of pages.")


# ── Envelopes ────────────────────────────────────────────────────────────────


class SuccessResponse(BaseModel, Generic[DataT]):
    """Standard success response envelope.

    Matches the specification in ``docs/06-API_STANDARDS.md`` §5.1.

    .. attribute:: success

        Always ``True`` for success responses.

    .. attribute:: message

        Human-readable summary of the operation result.

    .. attribute:: data

        The response payload. Type depends on the endpoint.

    .. attribute:: metadata

        Metadata block containing ``request_id`` and optional extras.
    """

    success: bool = True
    message: str
    data: DataT | None = None
    metadata: Metadata | None = None


class PaginatedResponse(BaseModel, Generic[DataT]):
    """Paginated list response envelope.

    Matches the specification in ``docs/06-API_STANDARDS.md`` §5.2.
    Pagination metadata is nested inside the ``metadata`` block.

    .. attribute:: success

        Always ``True`` for success responses.

    .. attribute:: message

        Human-readable summary.

    .. attribute:: data

        The list of records for this page.

    .. attribute:: metadata

        Metadata block containing ``request_id`` and nested ``pagination``.
    """

    success: bool = True
    message: str
    data: list[DataT] = Field(default_factory=list)
    metadata: MetadataWithPagination | None = None


class FieldError(BaseModel):
    """A single field-level validation error.

    .. attribute:: field

        The name of the input field that failed validation.

    .. attribute:: message

        Human-readable description of the validation failure.
    """

    field: str
    message: str


class ErrorResponse(BaseModel):
    """Standard error response envelope.

    Matches the specification in ``docs/06-API_STANDARDS.md`` §5.3.

    .. attribute:: success

        Always ``False`` for error responses.

    .. attribute:: message

        Human-readable error description. Safe to show to end users —
        never contains stack traces or PII.

    .. attribute:: errors

        Optional list of per-field validation errors, or ``None``.

    .. attribute:: error_code

        Application error code from the catalog in
        :class:`app.core.error_codes.ErrorCode`.

    .. attribute:: metadata

        Metadata block containing ``request_id``.
    """

    success: bool = False
    message: str
    errors: list[FieldError] | None = None
    error_code: str
    metadata: Metadata | None = None


# ── Query inputs ─────────────────────────────────────────────────────────────
# The models above describe what the API *returns*. These describe what a list
# endpoint *accepts*, and the page a service hands back to be wrapped in
# PaginatedResponse.


class PaginationParams(BaseModel):
    """Page/page-size pagination inputs (``docs/06-API_STANDARDS.md`` §9)."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1, description="1-based page number.")
    page_size: int = Field(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Records per page (max {MAX_PAGE_SIZE}).",
    )

    @property
    def offset(self) -> int:
        """SQL ``OFFSET`` for this page."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """SQL ``LIMIT`` for this page."""
        return self.page_size


class Page(BaseModel, Generic[DataT]):
    """One page of results plus the counts needed to render pagination.

    Services return this; the router unpacks it into
    :class:`PaginatedResponse` and :class:`PaginationMeta`.
    """

    items: list[DataT] = Field(default_factory=list, description="The records on this page.")
    page: int = Field(ge=1, description="1-based page number.")
    page_size: int = Field(ge=1, description="Records requested per page.")
    total_records: int = Field(ge=0, description="Total records matching the query.")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_pages(self) -> int:
        """Total number of pages available for this query."""
        if self.page_size <= 0:
            return 0
        return math.ceil(self.total_records / self.page_size)


__all__ = [
    "ErrorResponse",
    "Page",
    "PaginationParams",
    "FieldError",
    "Metadata",
    "MetadataWithPagination",
    "PaginatedResponse",
    "PaginationMeta",
    "SuccessResponse",
]
