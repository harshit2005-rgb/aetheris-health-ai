"""AI service — the single entry point every business module calls.

Modules never call providers directly. They call one of the use-case services
in this module (summarization, extraction, recommendation, QA) or the generic
:class:`AIService` for ad-hoc completions.

Every AI interaction is logged to ``ai_interactions`` for observability,
cost tracking, and evaluation.
"""

from __future__ import annotations

import time as _time
import uuid  # noqa: TC003 — needed at runtime for type hints
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import structlog

from app.ai.prompts import PromptRegistry
from app.ai.providers import AIProviderRegistry
from app.ai.providers.base import AIChunk, AIProvider, AIResponse, Message, ToolDefinition
from app.core.exceptions import ServiceUnavailableError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

#: Fallbacks when a model hint has no entry in the lookup tables.
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.3

logger = structlog.get_logger(__name__)


class BudgetExceededError(ServiceUnavailableError):
    """Raised when the AI budget for a hospital or user is exceeded."""

    def __init__(
        self,
        message: str = "AI budget exceeded.",
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, detail=detail)


class AIInteractionLog:
    """Record of a single AI interaction, to be persisted to ``ai_interactions``.

    This is a domain DTO — the actual persistence is handled by the
    ``AIInteractionRepository`` when it exists.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        hospital_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
        module: str,
        use_case: str,
        prompt_id: str,
        prompt_version: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        status: str,
        error_message: str | None = None,
        cost_estimate_usd: Decimal = Decimal("0"),
        request_id: str | None = None,
    ) -> None:
        self.hospital_id = hospital_id
        self.user_id = user_id
        self.module = module
        self.use_case = use_case
        self.prompt_id = prompt_id
        self.prompt_version = prompt_version
        self.provider = provider
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.latency_ms = latency_ms
        self.status = status
        self.error_message = error_message
        self.cost_estimate_usd = cost_estimate_usd
        self.request_id = request_id
        self.created_at = datetime.now(UTC)


class AIService:
    """Central AI orchestration service.

    Every business module that needs AI capabilities goes through this service
    (or one of the specialised services in this package).

    :param provider_registry: The provider registry for model resolution.
    :param prompt_registry: The prompt template registry.
    """

    def __init__(
        self,
        provider_registry: AIProviderRegistry,
        prompt_registry: PromptRegistry,
    ) -> None:
        self._provider_registry = provider_registry
        self._prompt_registry = prompt_registry

    async def complete(
        self,
        *,
        messages: list[Message],
        hint: str = "fast",
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[ToolDefinition] | None = None,
        stream: bool = False,
        use_case: str = "generic.complete",
        module: str = "ai",
        actor_id: uuid.UUID | None = None,
        hospital_id: uuid.UUID | None = None,
        request_id: str | None = None,
    ) -> AIResponse | AsyncIterator[AIChunk]:
        """Send a completion request through the AI provider layer.

        This is the lowest-level method in the AI service. Prefer using
        the specialised services (summarization, extraction, etc.) over
        calling this directly.

        :param messages: The conversation messages.
        :param hint: Model capability hint (``fast``, ``deep``, ``cheap``, ``local``).
        :param model: Concrete model override (bypasses hint resolution).
        :param max_tokens: Override default max tokens.
        :param temperature: Override default temperature.
        :param tools: Tool definitions the model may call.
        :param stream: Enable streaming response.
        :param use_case: Identifier for cost tracking and observability.
        :param module: Module name for observability.
        :param actor_id: User ID for audit logging.
        :param hospital_id: Hospital ID for tenant isolation.
        :param request_id: Correlation ID for observability.
        :returns: A complete response or an async iterator of chunks.
        :raises BudgetExceededError: If the AI budget is exceeded.
        :raises AllProvidersFailedError: If all providers fail.
        """
        from app.ai.constants import MAX_TOKENS, TEMPERATURE

        # Resolve provider and model.
        if model is not None:
            # Use a specific model — find which provider owns it.
            provider, resolved_model = self._resolve_provider_for_model(model)
        else:
            provider, resolved_model = await self._provider_registry.resolve_with_fallback(hint)

        # Apply defaults from hint if not overridden.
        hint_enum = None
        try:
            from app.ai.constants import ModelHint

            hint_enum = ModelHint(hint)
        except ValueError:
            pass

        # The defaults are supplied to .get() rather than only to the else
        # branch: a valid ModelHint that is absent from the lookup table would
        # otherwise resolve to None and be passed straight to the provider.
        actual_max_tokens: int = (
            max_tokens
            if max_tokens is not None
            else (
                MAX_TOKENS.get(hint_enum, DEFAULT_MAX_TOKENS) if hint_enum else DEFAULT_MAX_TOKENS
            )
        )
        actual_temperature: float = (
            temperature
            if temperature is not None
            else (
                TEMPERATURE.get(hint_enum, DEFAULT_TEMPERATURE)
                if hint_enum
                else DEFAULT_TEMPERATURE
            )
        )

        start_ns = _time.perf_counter_ns()

        try:
            result = await provider.complete(
                messages=messages,
                model=resolved_model,
                max_tokens=int(actual_max_tokens),
                temperature=float(actual_temperature),
                tools=tools,
                stream=stream,
            )

            latency_ms = (_time.perf_counter_ns() - start_ns) / 1_000_000

            if stream:
                # Streaming is handled by the caller via SSE.
                return result

            response: AIResponse = result  # type: ignore[assignment]
            assert isinstance(response, AIResponse)
            cost = provider.estimate_cost(
                response.input_tokens, response.output_tokens, resolved_model
            )

            self._log_interaction(
                module=module,
                use_case=use_case,
                prompt_id="direct",
                prompt_version="",
                provider=provider.name,
                model=resolved_model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                latency_ms=int(latency_ms),
                status="success",
                cost_estimate_usd=cost,
                actor_id=actor_id,
                hospital_id=hospital_id,
                request_id=request_id,
            )

            return response

        except Exception as exc:  # noqa: BLE001
            latency_ms = (_time.perf_counter_ns() - start_ns) / 1_000_000
            logger.error(
                "ai_completion_failed",
                provider=provider.name,
                model=resolved_model,
                error=str(exc),
                latency_ms=round(latency_ms, 2),
            )

            self._log_interaction(
                module=module,
                use_case=use_case,
                prompt_id="direct",
                prompt_version="",
                provider=provider.name,
                model=resolved_model,
                input_tokens=0,
                output_tokens=0,
                latency_ms=int(latency_ms),
                status="error",
                error_message=str(exc),
                cost_estimate_usd=Decimal("0"),
                actor_id=actor_id,
                hospital_id=hospital_id,
                request_id=request_id,
            )
            raise

    def _resolve_provider_for_model(self, model: str) -> tuple[AIProvider, str]:
        """Find a registered provider that can serve the given model.

        :param model: The model identifier.
        :returns: A (provider, model) tuple.
        :raises ServiceUnavailableError: If no provider can serve the model.
        """
        from app.ai.constants import COST_PER_1K_INPUT

        for provider_name in self._provider_registry.available_providers:
            if provider_name in COST_PER_1K_INPUT and model in COST_PER_1K_INPUT[provider_name]:
                provider_instance = self._provider_registry.get_provider(provider_name)
                if provider_instance is not None:
                    return provider_instance, model

        msg = f"No registered provider can serve model '{model}'."
        raise ServiceUnavailableError(message=msg)

    def _log_interaction(
        self,
        **kwargs: Any,
    ) -> None:
        """Log an AI interaction to the observability system.

        In the current sprint, this logs via structlog. When the
        ``AIInteractionRepository`` exists, this will also persist
        to the database.
        """
        logger.info(
            "ai_interaction",
            **kwargs,
        )


__all__ = [
    "AIInteractionLog",
    "AIService",
    "BudgetExceededError",
]
