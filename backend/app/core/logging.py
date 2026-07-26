"""Structured logging setup using structlog.

Configures structlog to produce JSON-formatted log entries with
consistent fields (timestamp, level, event, request_id, etc.).

Usage::

    from structlog import get_logger

    logger = get_logger(__name__)
    logger.info("patient.created", patient_id=uuid, actor_id=uuid)

Do **not** use ``print()`` in application code. Always use the logger.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

import structlog

from app.core.config import settings

if TYPE_CHECKING:
    from collections.abc import MutableMapping


def _add_app_version(
    logger: structlog.typing.WrappedLogger,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Inject the application name into every log entry."""
    event_dict.setdefault("app", settings.APP_NAME)
    return event_dict


def configure_logging() -> None:
    """Configure structlog and standard logging for the entire application.

    Call this once during application startup, **before** any log messages
    are emitted. Idempotent.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # ── Shared processors for all output modes ──────────────────────────
    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        _add_app_version,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # ── Add request_id if present in context vars ───────────────────────
    # (set by middleware in a later sprint)

    if settings.LOG_FORMAT == "json":
        # JSON output — for staging / production
        processors = shared_processors + [
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Console output — for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(
                colors=sys.stdout.isatty(),
                sort_keys=False,
            ),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # ── Route standard library logs through structlog ───────────────────
    # This captures logs from third-party libraries (SQLAlchemy, etc.)
    # and formats them using our structlog configuration.
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        stream=sys.stdout,
        force=True,
    )

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Set the root logger level
    logging.getLogger().setLevel(log_level)

    # Log confirmation
    logger = structlog.get_logger("aetheris.logging")
    logger.info(
        "logging_configured",
        log_level=settings.LOG_LEVEL,
        log_format=settings.LOG_FORMAT,
        environment=settings.APP_ENV,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Convenience function to get a structlog logger for the calling module.

    Usage::

        from app.core.logging import get_logger

        logger = get_logger(__name__)
        logger.info("hello_world")
    """
    return structlog.get_logger(name or __name__)  # type: ignore[no-any-return]
