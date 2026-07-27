"""Application-wide exception hierarchy.

Every custom exception inherits from :class:`AetherisError`.
The global exception handler in the middleware layer maps these
to the standard HTTP response envelope.
"""

from __future__ import annotations

from typing import Any

from app.core.error_codes import ErrorCode


class AetherisError(Exception):
    """Base exception for all application-level errors.

    Every custom exception in the codebase inherits from this.
    The global exception handler catches these and maps them to
    structured HTTP responses.

    :param message: Human-readable error description.
    :param detail: Machine-readable details (field errors, context).
    :param status_code: HTTP status code for the error response.
    :param error_code: Application error code for the response envelope.
    """

    def __init__(
        self,
        message: str = "An unexpected error occurred.",
        detail: dict[str, Any] | None = None,
        status_code: int = 500,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
    ) -> None:
        self.message = message
        self.detail = detail or {}
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(self.message)


class ConfigurationError(AetherisError):
    """Raised when the application is misconfigured.

    This is a startup-time error. It should never surface in production
    because configuration validation happens before the server accepts
    traffic.
    """

    def __init__(self, message: str = "Application configuration error.", detail: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, detail=detail, status_code=500, error_code=ErrorCode.CONFIGURATION_ERROR)


class NotFoundError(AetherisError):
    """Raised when a requested resource does not exist.

    Maps to HTTP 404.
    """

    def __init__(self, message: str = "Resource not found.", detail: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, detail=detail, status_code=404, error_code=ErrorCode.RESOURCE_NOT_FOUND)


class ValidationError(AetherisError):
    """Raised when input validation fails at the business-rule level.

    Maps to HTTP 422. (Pydantic validation errors are handled separately
    by FastAPI's built-in exception handler.)
    """

    def __init__(self, message: str = "Validation failed.", detail: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, detail=detail, status_code=422, error_code=ErrorCode.VALIDATION_ERROR)


class BusinessRuleError(AetherisError):
    """Raised when a business rule is violated.

    Maps to HTTP 400. Examples:
    - Attempting to book an appointment in the past.
    - Dispensing more medication than prescribed.
    - Applying a discount above the allowed threshold.
    """

    def __init__(self, message: str = "Business rule violation.", detail: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, detail=detail, status_code=400, error_code=ErrorCode.BUSINESS_RULE_VIOLATION)


class PermissionDeniedError(AetherisError):
    """Raised when the authenticated user lacks the required permission.

    Maps to HTTP 403.
    """

    def __init__(self, message: str = "Permission denied.", detail: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, detail=detail, status_code=403, error_code=ErrorCode.PERMISSION_DENIED)


class AuthenticationError(AetherisError):
    """Raised when authentication fails.

    Maps to HTTP 401. Used by the auth module (Sprint 2+).
    """

    def __init__(self, message: str = "Authentication required.", detail: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, detail=detail, status_code=401, error_code=ErrorCode.AUTHENTICATION_REQUIRED)


class ConflictError(AetherisError):
    """Raised when the request conflicts with the current state.

    Maps to HTTP 409. Examples:
    - Duplicate MRN.
    - Appointment time slot already booked.
    - Duplicate invoice number.
    """

    def __init__(self, message: str = "Resource conflict.", detail: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, detail=detail, status_code=409, error_code=ErrorCode.RESOURCE_CONFLICT)


class RateLimitError(AetherisError):
    """Raised when the rate limit is exceeded.

    Maps to HTTP 429.
    """

    def __init__(self, message: str = "Rate limit exceeded. Try again later.", detail: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, detail=detail, status_code=429, error_code=ErrorCode.RATE_LIMITED)


class ServiceUnavailableError(AetherisError):
    """Raised when a downstream dependency is unavailable.

    Maps to HTTP 503.
    """

    def __init__(self, message: str = "Service temporarily unavailable.", detail: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, detail=detail, status_code=503, error_code=ErrorCode.SERVICE_UNAVAILABLE)
