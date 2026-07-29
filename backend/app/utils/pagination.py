"""Pagination utilities.

Provides shared logic for both offset-based and cursor-based pagination.
The actual pagination of queries happens inside repositories — this module
owns the **math** and **schema** for pagination metadata.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PageParams:
    """Normalised pagination parameters from the request.

    :param page: 1-based page number.
    :param page_size: Number of items per page.
    :param sort: Optional sort field.
    :param sort_desc: Whether to sort descending.
    """

    page: int = 1
    page_size: int = 25
    sort: str | None = None
    sort_desc: bool = False

    @property
    def offset(self) -> int:
        """Calculate the offset for SQL ``OFFSET``."""
        return (max(self.page, 1) - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Return the limit for SQL ``LIMIT``."""
        return min(max(self.page_size, 1), 100)


@dataclass(frozen=True)
class Page[ModelT]:
    """A generic page of results.

    :param items: The records for this page.
    :param total_records: Total records matching the query.
    :param page: 1-based page number.
    :param page_size: Items per page.
    :param next_cursor: Cursor for the next page (cursor-based pagination).
    """

    items: list[ModelT]
    total_records: int = 0
    page: int = 1
    page_size: int = 25
    next_cursor: str | None = None

    @property
    def total_pages(self) -> int:
        """Total number of pages."""
        if self.page_size <= 0 or self.total_records <= 0:
            return 0
        return math.ceil(self.total_records / self.page_size)

    @property
    def has_next(self) -> bool:
        """True if there is at least one more page."""
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        """True if this is not the first page."""
        return self.page > 1

    @property
    def metadata(self) -> dict[str, object]:
        """Return the pagination metadata block for the response envelope.

        :returns: A dict matching the ``metadata.pagination`` schema
            in ``docs/06-API_STANDARDS.md`` §5.2.
        """
        return {
            "page": self.page,
            "page_size": self.page_size,
            "total_records": self.total_records,
            "total_pages": self.total_pages,
        }


def validate_page_params(page: int = 1, page_size: int = 25) -> PageParams:
    """Validate and normalise pagination query parameters.

    :param page: The requested page (1-based).
    :param page_size: The requested page size.
    :returns: A normalised :class:`PageParams`.
    """
    from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

    validated_page = max(page, 1)
    validated_size = max(1, min(page_size, MAX_PAGE_SIZE))
    actual_size = validated_size or DEFAULT_PAGE_SIZE

    return PageParams(page=validated_page, page_size=actual_size)


def empty_page(page: int = 1, page_size: int = 25) -> Page[object]:
    """Return an empty page (useful when no results match).

    :param page: The requested page.
    :param page_size: The requested page size.
    :returns: A :class:`Page` with an empty items list.
    """
    return Page(items=[], total_records=0, page=page, page_size=page_size)


__all__ = [
    "Page",
    "PageParams",
    "empty_page",
    "validate_page_params",
]
