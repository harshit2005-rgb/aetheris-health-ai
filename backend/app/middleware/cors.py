"""CORS middleware configuration.

Provides a factory that builds a configured CORS middleware instance from the
application settings. The middleware is registered in :func:`app.main._register_middleware`.

Uses FastAPI's built-in ``CORSMiddleware`` which is already imported in main.py.
This module exists so CORS configuration stays in one place.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


def add_cors_middleware(app: FastAPI) -> None:
    """Register CORS middleware on the application using configured origins.

    :param app: The FastAPI application instance.
    """
    origins = settings.CORS_ORIGINS

    if not origins:
        return

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
    )


__all__ = ["add_cors_middleware"]
