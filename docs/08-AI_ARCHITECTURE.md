# 08 — AI Architecture

AI is not a module in Aetheris. It is a **platform capability** every module can use. This document describes how the AI layer is structured, how modules invoke it, and the safety guarantees around it.

---

## 1. Design Goals

1. **Provider-agnostic** — swap Anthropic ↔ Groq ↔ OpenAI ↔ Gemini ↔ self-hosted without touching business logic
2. **Composable** — services request AI capabilities, not raw model calls
3. **Observable** — every AI call logged with tokens, cost, latency, provider
4. **Safe** — AI never touches the database directly; AI outputs feed structured tools with validation
5. **Testable** — prompts are versioned, evaluated with golden sets
6. **Cost-controlled** — budgets per hospital, per user, per use case
7. **Future-ready** — MCP-native, RAG-ready, agentic-workflow-ready

## 2. Directory Layout

```
app/ai/
├── providers/
│   ├── base.py               # Provider interface
│   ├── anthropic.py
│   ├── openai.py
│   ├── groq.py
│   ├── gemini.py
│   └── ollama.py             # self-hosted
├── prompts/
│   ├── registry.py           # loads templates from disk
│   └── templates/
│       ├── patient/
│       │   ├── summarize.yaml
│       │   └── history_extraction.yaml
│       ├── appointment/
│       │   └── slot_recommendation.yaml
│       ├── billing/
│       │   └── invoice_explanation.yaml
│       └── ...
├── services/
│   ├── ai_service.py         # main orchestrator
│   ├── summarization.py
│   ├── extraction.py
│   ├── recommendation.py
│   └── qa.py
├── agents/                   # multi-step workflows (v2.1+)
│   └── ...
├── tools/                    # function definitions callable by AI
│   ├── patient_tools.py
│   ├── appointment_tools.py
│   └── ...
├── memory/                   # conversational memory
│   ├── session_memory.py
│   └── long_term.py
├── context/                  # RAG retrievers (v2.1)
│   ├── vector_store.py
│   └── retriever.py
├── evaluation/               # eval harness
│   ├── golden_sets/
│   └── evaluators.py
└── constants.py
```

## 3. Provider Interface

Every provider implements the same async interface. This is what lets us swap freely.

```python
# app/ai/providers/base.py

class AIProvider(Protocol):
    name: str

    async def complete(
        self,
        messages: list[Message],
        model: str,
        max_tokens: int,
        temperature: float,
        tools: list[ToolDefinition] | None = None,
        stream: bool = False,
    ) -> AIResponse | AsyncIterator[AIChunk]: ...

    async def embed(self, texts: list[str], model: str) -> list[list[float]]: ...

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> Decimal: ...
```

`AIResponse`, `AIChunk`, `Message`, `ToolDefinition`, and `ToolCall` are internal types that normalize provider-specific quirks (Anthropic system prompts, OpenAI tool schemas, etc.).

## 4. Prompt Management

Prompts are **not hardcoded strings**. They live as versioned YAML files.

```yaml
# app/ai/prompts/templates/patient/summarize.yaml
id: patient.summarize
version: 1.2.0
description: Summarize a patient's medical history for a clinician
model_hint: fast   # → maps to a real model at runtime
input_schema:
  patient:
    type: object
    required: [id, age, gender, visits, conditions, medications, allergies]
system: |
  You are a clinical summarization assistant for a hospital management system.
  You produce concise, factual summaries of patient history for busy clinicians.
  You never invent medical facts. If information is missing, you say so.
  You never provide diagnostic conclusions.
user: |
  Summarize the following patient's history in 4-6 bullet points.
  Order by clinical relevance (chronic conditions first).
  End with a single-line "AI Note" flagging anything that warrants attention.

  Patient:
  {{ patient | tojson(indent=2) }}
output_format:
  type: markdown
```

The registry loads these at startup, validates the schema, and gives services a typed handle.

### 4.1 Prompt Versioning

- `id` is stable; `version` bumps on any change
- Every AI interaction records `(prompt_id, prompt_version)` in `ai_interactions`
- Evaluation golden sets are tied to `(prompt_id, prompt_version)`

### 4.2 Model Hinting

Prompts declare a **capability hint** (`fast`, `deep`, `cheap`, `local`), not a concrete model. The provider registry maps hints to actual models per environment.

```
fast  → groq/llama-3.1-70b
deep  → anthropic/claude-sonnet-4.6
cheap → openai/gpt-4o-mini
local → ollama/qwen2.5:14b
```

Swapping the mapping = single config change.

## 5. AI Service

Modules never call providers directly. They call a service in `app/ai/services/`.

```python
# app/ai/services/summarization.py

class SummarizationService:
    def __init__(self, provider_registry, prompt_registry, logger, budget):
        ...

    async def summarize_patient(
        self,
        patient_dto: PatientDTO,
        actor: User,
        hint: str = "fast",
    ) -> AISummaryResult:
        await self._budget.check(actor, use_case="patient.summarize")
        prompt = self._prompts.get("patient.summarize")
        provider, model = self._provider_registry.resolve(prompt.model_hint or hint)
        rendered = prompt.render(patient=self._sanitize(patient_dto))
        response = await provider.complete(rendered.messages, model=model, ...)
        await self._log_interaction(prompt, provider, model, response, actor)
        return AISummaryResult.from_response(response)
```

Business services call this:

```python
class PatientService:
    async def get_summary(self, patient_id, actor) -> AISummaryResult:
        patient = await self._patients.get(patient_id)
        self._authz.require_read(actor, patient)
        return await self._ai_summarization.summarize_patient(patient, actor)
```

## 6. Function Calling / Tools

When AI needs to trigger actions (book an appointment from a chat request, look up a patient by phone), it does so through **typed tools** that wrap existing services.

```python
# app/ai/tools/appointment_tools.py

APPOINTMENT_LOOKUP = ToolDefinition(
    name="lookup_appointments",
    description="Look up appointments for a patient within a date range.",
    input_schema={
        "type": "object",
        "properties": {
            "patient_id": {"type": "string", "format": "uuid"},
            "start_date": {"type": "string", "format": "date"},
            "end_date": {"type": "string", "format": "date"},
        },
        "required": ["patient_id", "start_date", "end_date"],
    },
)

async def handle_appointment_lookup(args: dict, actor: User, appt_service):
    validated = AppointmentLookupInput(**args)
    return await appt_service.list_for_patient(
        patient_id=validated.patient_id,
        start=validated.start_date,
        end=validated.end_date,
        actor=actor,  # permission checks apply
    )
```

Rules:
- Every tool wraps an existing service method
- Tool arguments are validated against a Pydantic schema before service invocation
- Tool execution runs under the calling user's identity — same permission checks apply
- No tool can escalate privileges, bypass tenancy, or write raw SQL
- Destructive tools require explicit confirmation in the calling context

## 7. Conversational Memory

For the chat AI Assistant, memory is per-session, per-user, per-hospital:

- Redis-backed session store, keyed by `(hospital_id, user_id, session_id)`
- TTL: 12 hours idle
- Bounded window: last N turns; older turns get compressed to a summary
- Memory never contains other patients' or other hospitals' data
- Long-term user memory (v2.2) is opt-in per user, retention-limited, and marked in prompts

## 8. RAG (v2.1+)

Retrieval-Augmented Generation over **approved hospital knowledge sources**:

- Hospital SOPs, drug references, policy documents
- Patient records **only for the retrieving user's authorized scope**
- Embeddings stored in `pgvector` on the same PostgreSQL
- Retrieval queries carry `hospital_id` and permission context; the vector store filters accordingly
- No cross-tenant retrieval, ever

Chunking, embedding model choice, and re-ranking approach documented in the retriever module when we ship it.

## 9. MCP Integration (v2.1+)

Model Context Protocol lets future AI agents (both ours and third-party) talk to Aetheris capabilities safely.

- Every MCP tool wraps an existing service method
- MCP tools are registered in `app/mcp/tools.py`
- MCP calls run under an OAuth-authenticated identity with scoped permissions
- Every MCP call is audited (`actor_type = "ai_agent"` in audit logs)

MCP is the eventual surface for third parties to build agents against Aetheris without us shipping SDKs for every language.

## 10. Streaming

Long AI responses stream to the client via SSE. The pattern:

- Service starts the provider call in streaming mode
- Each chunk yields to an async generator
- The API layer wraps the generator as an SSE stream
- Final chunk carries `total_tokens`, `cost_usd`, `prompt_id`, `model`

Frontend renders progressively for perceived performance.

## 11. AI Safety Guarantees

These are enforced at the code level, not by prompt engineering alone.

| Guarantee | Enforcement |
|---|---|
| AI never writes to the database directly | Providers have no DB session; tools call services |
| AI never bypasses authentication | Tool executor uses the caller's user identity |
| AI never bypasses authorization | Services perform their normal permission checks |
| AI never fabricates medical facts as recommendations | Every clinical output includes "decision support only" disclaimer; UI presents accordingly |
| AI never sees data outside the caller's scope | Prompts render only from data the caller could see; RAG filtered by scope |
| AI cannot execute arbitrary code | No code-execution tool; no SQL tool; no eval |

## 12. Observability

Every AI interaction produces an `ai_interactions` row containing:

- Provider, model, prompt id + version
- Input tokens, output tokens, latency
- Cost estimate
- Status (success / error / rate_limited)
- Correlation `request_id`

Dashboards (v2.1):
- Cost by hospital / module / use case
- Latency percentiles per model
- Error rate per provider
- Prompt version rollout tracking (v2.2)

## 13. Cost Controls

- Per-hospital monthly AI budget (soft cap → warning, hard cap → throttling)
- Per-user daily AI budget for chat use cases
- Per-endpoint per-minute rate limits
- Caching for idempotent summarization requests (input hash → response)
- Batching for embedding jobs

Budgets are Hospital Admin configurable.

## 14. Evaluation Harness

Every prompt with a `version` change goes through eval before rollout.

- Golden set: `app/ai/evaluation/golden_sets/patient_summarize/v1.2.0.jsonl`
- Evaluators: automated (structure, key facts, hallucination check via LLM-as-judge) + spot-check by clinicians
- CI runs eval on prompt-version changes and blocks on regression thresholds

## 15. Failure Modes

- Provider timeout → retry with backoff; on second failure, fall back to secondary provider
- All providers failing → return `AI_PROVIDER_UNAVAILABLE` (503) to the client
- Streaming disconnect → client can resume with a continuation endpoint (v2.1)
- Tool call failure → surfaced to model with a structured error; model can retry or apologize

## 16. Model Choice Guidance

We do not pick one model for everything. Guidance for module authors:

| Use case | Hint | Reasoning |
|---|---|---|
| Patient summary (routine) | `fast` | Latency matters; Groq/Llama is fine |
| Clinical draft note | `deep` | Quality matters; Claude Sonnet |
| Invoice explanation | `cheap` | Volume high, quality forgiving |
| Chat assistant | `fast` with fallback to `deep` for complex asks | UX responsiveness |
| Structured extraction | `deep` | Reliability of tool calls |
| RAG synthesis | `deep` | Long context, faithfulness |
| Embeddings | provider default | Consistency |

## 17. Do / Don't

**Do**
- Add prompt version bumps for any wording change
- Log every AI interaction
- Sanitize inputs (strip PII where not needed)
- Test tool calls with malformed arguments
- Use function calling for anything that touches data
- Fall back gracefully when providers fail

**Don't**
- Put prompts in Python source
- Give AI raw DB access
- Let AI outputs bypass validation
- Ship a new use case without an eval set
- Use one provider without a fallback
- Log full patient records with prompts unless opt-in retention is configured

## 18. Roadmap Alignment

- **v2.0 (MVP):** provider abstraction, prompt registry, function calling, streaming, observability, cost controls
- **v2.1:** MCP tool surface, RAG for hospital knowledge, evaluation harness in CI, agent scaffolding
- **v2.2:** multi-provider routing on real-time cost/latency, RAG over patient records with strict scope, opt-in user memory
- **v2.3:** multi-agent workflows, autonomous administrative agents (with human-in-the-loop by default)

---

*AI is the platform differentiator, but "AI" is not the answer to every product problem. Ship AI where it makes a workflow better. Everywhere else, ship good software.*
