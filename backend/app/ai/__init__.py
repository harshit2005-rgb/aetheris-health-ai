"""AI platform layer.

Every AI call in the application goes through :mod:`app.ai.services` — never a
raw provider SDK. The layer owns provider routing and failover, the versioned
prompt registry, tool definitions, memory, retrieval context, and evaluation.

See ``docs/08-AI_ARCHITECTURE.md``.
"""
