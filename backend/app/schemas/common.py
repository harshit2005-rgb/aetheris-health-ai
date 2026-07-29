"""Shared request/response shapes used by every module.

Pagination lives here so that ``metadata.pagination`` is built identically for
every list endpoint (``docs/06-API_STANDARDS.md`` §9). The envelope itself is
built by :mod:`app.core.envelope`; these models describe what goes *inside* it.

Usage::

    from app.schemas.common import PaginationParams, Page

    params = PaginationParams(page=2, page_size=50)
    page = Page[PatientSummaryResponse](items=rows, page=2, page_size=50, total_records=137)
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

__all__ = ["Page", "PaginationParams"]


class PaginationParams(BaseModel):
    """Page/page-size pagination inputs (``docs/06-API_STANDARDS.md`` §9)."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(
        default=1,
        ge=1,
        description="1-based page number.",
    )
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


class Page[ItemT](BaseModel):
    """One page of results plus the counts needed to render pagination.

    Services return this; the router unpacks it into
    :func:`app.core.envelope.paginated_envelope`.
    """

    items: list[ItemT] = Field(description="The records on this page.")
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
