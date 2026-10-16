"""ASGI middleware.

Request ID propagation, structured request logging, rate limiting, CORS, and
the global exception handler. Registered in :func:`app.main.create_app` — order
matters, since middleware executes in reverse registration order.
"""
