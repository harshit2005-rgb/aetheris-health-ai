"""Request ID middleware.

Adds a unique ``X-Request-ID`` header to every response and stores it in
``request.state`` for logging and audit correlation. If the client sends an
``X-Request-ID`` header, that value is used (enabling end-to-end tracing);
otherwise a new UUID v4 is generated.

Registered in :func:`app.main._register_middleware`.
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.constants import REQUEST_ID_HEADER


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that ensures every request has a unique ID.

    The ID is stored in ``request.state.request_id`` and
    echoed back in the ``X-Request-ID`` response header.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Extract or generate a request ID, then pass control to the next handler.

        :param request: The incoming HTTP request.
        :param call_next: The next middleware or route handler.
        :returns: The HTTP response with the ``X-Request-ID`` header set.
        """
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
        request.state.request_id = request_id

        response: Response = await call_next(request)

        response.headers[REQUEST_ID_HEADER] = request_id
        return response


__all__ = ["RequestIDMiddleware"]
