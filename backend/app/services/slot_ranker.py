"""AI-backed implementation of the appointment slot ranker.

Satisfies :class:`~app.services.appointment_service.SlotRanker` by calling the
AI platform layer. Kept out of ``appointment_service.py`` on purpose: prompt
selection, provider routing and response parsing belong to the AI stack, and a
clinical service should not care which model answered
(``docs/08-AI_ARCHITECTURE.md``; ``backend/CLAUDE.md``, "AI Module Usage" —
never call a provider SDK outside ``app/ai/providers/``).

**The model ranks; it never invents.** Every returned slot is matched back
against the candidate list before it leaves this class. A hallucinated time
that reception could click "book" on is the one failure mode that would matter
here, so it is filtered structurally rather than trusted to the prompt.
"""

from __future__ import annotations

import json
import uuid  # noqa: TC003 — needed at runtime for type hints
from typing import TYPE_CHECKING, Any

from app.ai.providers.base import Message
from app.core.logging import get_logger
from app.schemas.appointment import SlotRecommendation, SlotRecommendationResponse

if TYPE_CHECKING:
    from app.ai.prompts.registry import PromptRegistry
    from app.ai.services.ai_service import AIService

logger = get_logger(__name__)

__all__ = ["AISlotRanker"]

#: Prompt template backing this ranker. Versioned on disk at
#: ``app/ai/prompts/templates/appointment/recommend_slot.yaml``.
PROMPT_ID = "appointment.recommend_slot"


class AISlotRanker:
    """Ranks candidate slots with the AI platform layer.

    :param ai: The shared AI service. All provider access goes through it.
    :param prompts: Prompt registry holding the versioned template.
    """

    def __init__(self, ai: AIService, prompts: PromptRegistry) -> None:
        self._ai = ai
        self._prompts = prompts

    async def rank_slots(
        self,
        *,
        hospital_id: uuid.UUID,
        actor_id: uuid.UUID | None,
        urgency: str,
        candidates: list[dict[str, Any]],
        limit: int,
    ) -> SlotRecommendationResponse:
        """Rank ``candidates`` best-first.

        :param hospital_id: Tenant, for budget and attribution.
        :param actor_id: Acting user, for cost attribution.
        :param urgency: routine / soon / urgent, supplied by the caller.
        :param candidates: Free slots the model may choose among.
        :param limit: Maximum suggestions to return.
        :returns: Ranked suggestions, never containing a slot outside
            ``candidates``.
        """
        rendered = self._prompts.render(
            PROMPT_ID,
            limit=limit,
            urgency=urgency,
            visit_cadence="unknown",
            preferred_window="any",
            candidate_slots=json.dumps(candidates, indent=2),
            doctor_load="not yet available",
        )

        # RenderedPrompt gives `system` plus a list of message dicts; the
        # provider layer wants typed Message objects.
        response = await self._ai.complete(
            messages=[
                Message(role="system", content=rendered.system),
                *(
                    Message(role=m.get("role", "user"), content=m.get("content", ""))
                    for m in rendered.messages
                ),
            ],
            hint="fast",
            use_case=PROMPT_ID,
            module="appointment",
            actor_id=actor_id,
            hospital_id=hospital_id,
        )

        ranked = self._parse(getattr(response, "content", ""), candidates, limit)
        return SlotRecommendationResponse(
            recommendations=ranked, model=getattr(response, "model", None) or None
        )

    @staticmethod
    def _parse(
        content: str, candidates: list[dict[str, Any]], limit: int
    ) -> list[SlotRecommendation]:
        """Turn the model's reply into validated recommendations.

        Anything that does not correspond to a supplied candidate is dropped.
        A malformed reply yields an empty list rather than an exception — the
        caller degrades to "no suggestions", and reception books by hand.

        :param content: Raw model output.
        :param candidates: The slots that were offered.
        :param limit: Maximum to return.
        :returns: Validated recommendations, best-first.
        """
        allowed = {(slot["slot_start"], slot["slot_end"]): slot for slot in candidates}

        try:
            payload = json.loads(_extract_json(content))
        except (ValueError, TypeError):
            logger.warning("appointment.slot_ranker_unparseable", content_length=len(content))
            return []

        rows = payload.get("recommendations", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []

        results: list[SlotRecommendation] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = (row.get("slot_start"), row.get("slot_end"))
            source = allowed.get(key)
            if source is None:
                # The model returned a slot nobody offered it.
                logger.warning("appointment.slot_ranker_hallucinated_slot", slot=str(key))
                continue
            try:
                results.append(
                    SlotRecommendation(
                        slot_start=source["slot_start"],
                        slot_end=source["slot_end"],
                        doctor_id=source["doctor_id"],
                        score=max(0.0, min(1.0, float(row.get("score", 0.5)))),
                        reason=str(row.get("reason", ""))[:500],
                    )
                )
            except (ValueError, TypeError, KeyError):
                continue

        return results[:limit]


def _extract_json(content: str) -> str:
    """Pull the JSON body out of a model reply.

    Models commonly wrap JSON in prose or a fenced code block even when asked
    not to, so the outermost braces or brackets are located rather than
    assuming the whole reply parses.

    :param content: Raw model output.
    :returns: The substring most likely to be JSON.
    """
    text = content.strip()
    if text.startswith("```"):
        # Strip a fenced block, with or without a language tag.
        text = text.split("```")[1] if len(text.split("```")) > 1 else text
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]

    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            return text[start : end + 1]
    return text
