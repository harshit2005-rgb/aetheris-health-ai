"""AI platform constants.

Model hint mappings, cost estimates, and default budget configurations.
Model choice guidance is documented in ``docs/08-AI_ARCHITECTURE.md`` §16.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Final


class ModelHint(StrEnum):
    """Capability hints that prompts declare instead of concrete model names.

    The provider registry resolves hints to actual models per environment.
    """

    FAST = "fast"  # Low latency, good for routine tasks
    DEEP = "deep"  # High quality, good for clinical drafting
    CHEAP = "cheap"  # Cost-optimized, high-volume
    LOCAL = "local"  # Self-hosted, data residency


#: Default mapping from model hints to (provider, model) tuples.
#: Override per environment via configuration.
DEFAULT_HINT_MAPPING: Final[dict[ModelHint, tuple[str, str]]] = {
    ModelHint.FAST: ("groq", "llama-3.1-70b-versatile"),
    ModelHint.DEEP: ("anthropic", "claude-sonnet-4-20250514"),
    ModelHint.CHEAP: ("openai", "gpt-4o-mini"),
    ModelHint.LOCAL: ("ollama", "qwen2.5:14b"),
}

#: Cost per 1K input tokens (USD), sourced from provider pricing pages.
#: Used for cost estimation in ai_interactions. Rough estimates — update
#: regularly as pricing changes.
COST_PER_1K_INPUT: Final[dict[str, dict[str, Decimal]]] = {
    "anthropic": {
        "claude-sonnet-4-20250514": Decimal("0.003"),
        "claude-haiku-3-5-20241022": Decimal("0.0008"),
    },
    "openai": {
        "gpt-4o-mini": Decimal("0.00015"),
        "gpt-4o": Decimal("0.0025"),
    },
    "groq": {
        "llama-3.1-70b-versatile": Decimal("0.00059"),
        "mixtral-8x7b-32768": Decimal("0.00027"),
    },
    "ollama": {
        "qwen2.5:14b": Decimal("0"),  # Self-hosted = estimated electricity cost
    },
}

#: Cost per 1K output tokens (USD).
COST_PER_1K_OUTPUT: Final[dict[str, dict[str, Decimal]]] = {
    "anthropic": {
        "claude-sonnet-4-20250514": Decimal("0.015"),
        "claude-haiku-3-5-20241022": Decimal("0.004"),
    },
    "openai": {
        "gpt-4o-mini": Decimal("0.0006"),
        "gpt-4o": Decimal("0.01"),
    },
    "groq": {
        "llama-3.1-70b-versatile": Decimal("0.00079"),
        "mixtral-8x7b-32768": Decimal("0.00027"),
    },
    "ollama": {
        "qwen2.5:14b": Decimal("0"),
    },
}

#: Default per-hospital monthly AI budget in USD.
DEFAULT_MONTHLY_AI_BUDGET_USD: Final[Decimal] = Decimal("100.00")

#: Default daily AI budget per user in USD.
DEFAULT_DAILY_USER_AI_BUDGET_USD: Final[Decimal] = Decimal("1.00")

#: Max tokens for AI completions by hint.
MAX_TOKENS: Final[dict[ModelHint, int]] = {
    ModelHint.FAST: 4096,
    ModelHint.DEEP: 8192,
    ModelHint.CHEAP: 2048,
    ModelHint.LOCAL: 4096,
}

#: Default temperature for AI completions by hint.
TEMPERATURE: Final[dict[ModelHint, float]] = {
    ModelHint.FAST: 0.3,
    ModelHint.DEEP: 0.1,
    ModelHint.CHEAP: 0.5,
    ModelHint.LOCAL: 0.3,
}

#: AI interaction status values.
AI_STATUS_SUCCESS = "success"
AI_STATUS_ERROR = "error"
AI_STATUS_RATE_LIMITED = "rate_limited"
