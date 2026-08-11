"""AI use-case services — summarization, extraction, recommendation, Q&A.

``AIService`` is the single entry point other modules call. It enforces the
per-hospital budget, records every interaction to ``ai_interactions``, and
resolves prompts through the registry.
"""

from __future__ import annotations

from app.ai.services.ai_service import AIService, BudgetExceededError

__all__ = [
    "AIService",
    "BudgetExceededError",
]
