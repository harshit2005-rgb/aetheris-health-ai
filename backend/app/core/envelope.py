"""Standard response envelope builders.

Every response the API emits is wrapped in the envelope defined in
``docs/06-API_STANDARDS.md`` §5. These builders are the only place that
envelope shape is constructed, so the contract cannot drift between routers.

Usage::

    from app.core.envelope import error_envelope, paginated_envelope, success_envelope

    success_envelope("Patient created successfully.", data=patient)
    paginated_envelope("Patients retrieved.", data=rows, page=1, page_size=25, total_records=137)
    error_envelope("Validation failed.", error_code=ErrorCode.VALIDATION_ERROR, errors=[...])
"""

from __future__ import annotations

import math
from typing import Any

from app.core.error_codes import ErrorCode


def _metadata(request_id: str | None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the ``metadata`` block shared by every envelope."""
    metadata: dict[str, Any] = {"request_id": request_id}
    if extra:
        metadata.update(extra)
    return metadata


def success_envelope(
    message: str,
    *,
    data: Any = None,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a success envelope (``docs/06-API_STANDARDS.md`` §5.1).

    :param message: Human-readable summary of what happened.
    :param data: The response payload.
    :param request_id: Correlation ID for this request.
    :param metadata: Additional metadata merged into the ``metadata`` block.
    :returns: The envelope as a JSON-serializable dict.
    """
    return {
        "success": True,
        "message": message,
        "data": data,
        "metadata": _metadata(request_id, metadata),
    }


def paginated_envelope(
    message: str,
    *,
    data: list[Any],
    page: int,
    page_size: int,
    total_records: int,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build a list-success envelope with pagination metadata (§5.2).

    :param message: Human-readable summary.
    :param data: The page of records.
    :param page: 1-based page number.
    :param page_size: Records requested per page.
    :param total_records: Total records matching the query across all pages.
    :param request_id: Correlation ID for this request.
    :returns: The envelope as a JSON-serializable dict.
    """
    total_pages = math.ceil(total_records / page_size) if page_size > 0 else 0
    return success_envelope(
        message,
        data=data,
        request_id=request_id,
        metadata={
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_records": total_records,
                "total_pages": total_pages,
            },
        },
    )


def error_envelope(
    message: str,
    *,
    error_code: ErrorCode | str = ErrorCode.INTERNAL_ERROR,
    errors: Any = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build a failure envelope (``docs/06-API_STANDARDS.md`` §5.3).

    :param message: Human-readable summary of the failure. Must be safe to show
        to an end user — never include stack traces or PII.
    :param error_code: A value from :class:`~app.core.error_codes.ErrorCode`.
    :param errors: Machine-readable detail (e.g. per-field validation errors).
        Falsy values are normalized to ``None``.
    :param request_id: Correlation ID for this request.
    :returns: The envelope as a JSON-serializable dict.
    """
    return {
        "success": False,
        "message": message,
        "errors": errors if errors else None,
        "error_code": str(error_code),
        "metadata": _metadata(request_id),
    }
