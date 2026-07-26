# 13 — AI Assistant (Platform Layer)

**Owner:** TBD
**Phase:** MVP
**Status:** Approved

---

## 1. Purpose

Provide the **conversational and programmatic AI surface** for the platform: a chat interface for staff, and a shared AI service that every other module invokes for capabilities like summarization, extraction, recommendation, and Q&A. This is the module that operationalizes the AI-first philosophy.

## 2. Scope

### In Scope

- Chat interface for authenticated users
- AI provider abstraction (Anthropic, Groq, OpenAI, Gemini, self-hosted)
- Prompt template registry
- Function calling (tools that wrap existing services)
- Conversational memory (per session)
- Streaming responses (SSE)
- Token usage + cost tracking
- Model fallback (v2.1)
- MCP tool surface (v2.1)
- RAG over hospital knowledge (v2.1)
- Prompt evaluation harness

### Out of Scope

- Voice input → future
- Autonomous multi-agent workflows → v3
- Model training / fine-tuning → not on roadmap

## 3. Personas & Permissions

| Role | Can |
|---|---|
| Any authenticated user | Chat, ask questions within their permission scope |
| Hospital Admin | Manage AI cost budgets, view usage dashboards |
| Doctor | All + clinical prompts (summaries, note drafting v2.1) |
| Billing Staff | Invoice explanation, revenue Q&A (v2.1) |

The AI Assistant never lets a user do anything they couldn't already do through normal APIs. It's a UX shortcut, not a permission bypass.

## 4. Business Rules

1. Every AI interaction runs under the calling user's identity — same permissions apply.
2. AI outputs used to take actions go through **typed tools**, not free text.
3. Every AI call is logged in `ai_interactions`.
4. Hospital-configured monthly budget; exceeding triggers throttle.
5. User-configured daily chat budget; exceeding triggers throttle with clear message.
6. Prompts are versioned; changes require an eval pass.
7. AI never modifies the database directly.
8. AI never sees data outside the user's authorized scope.
9. Clinical outputs carry a "decision support only" label in the UI.

## 5. Workflow

### 5.1 Chat message (happy path)

1. User types message → `POST /ai/chat` with `{session_id, message}`.
2. AI service loads session memory (bounded window), resolves user identity + hospital.
3. Renders system prompt + memory + user message.
4. Provider (per model routing) invoked with tools available.
5. Response streamed via SSE.
6. If tool call requested → executor validates args → invokes underlying service under user identity → returns result to model → continue streaming.
7. Final chunk carries `total_tokens`, `cost_usd`, `prompt_id`.
8. Log to `ai_interactions`.

### 5.2 Programmatic capability (called by other services)

Same as chat but no memory, no streaming needed. Typical calls: `summarize_patient`, `explain_invoice`, `recommend_slot`.

## 6. Functional Requirements

- FR-1: Chat interface with streaming.
- FR-2: Function calling into typed tools.
- FR-3: Session memory.
- FR-4: Provider abstraction.
- FR-5: Versioned prompt registry.
- FR-6: Token / cost tracking.
- FR-7: Per-hospital and per-user budgets.
- FR-8: Fallback across providers on failure.
- FR-9: Structured logging of every call.
- FR-10: Evaluation harness (offline, CI).

## 7. Non-Functional Requirements

- Time to first token (streaming): p95 < 1s.
- Full response for a 3-turn chat with a tool call: p95 < 5s.
- No cross-session, cross-user, or cross-hospital data leaks in memory.
- Cost overage guardrails absolute (hard cap on hospital budget).

## 8. Database Design

Tables in `05-DATABASE_DESIGN.md`: `ai_interactions`.

Additional:

```
ai_chat_sessions
  id UUID PK
  user_id UUID FK users(id) NOT NULL
  hospital_id UUID FK hospitals(id) NOT NULL
  title VARCHAR(200)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
  archived_at TIMESTAMPTZ NULL

ai_chat_messages
  id UUID PK
  session_id UUID FK ai_chat_sessions(id) NOT NULL
  role ENUM(user/assistant/system/tool)
  content TEXT NOT NULL
  tool_calls JSONB NULL           -- structured tool call records
  tokens_input INT
  tokens_output INT
  provider VARCHAR(50)
  model VARCHAR(100)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()

ai_budgets
  hospital_id UUID PK FK hospitals(id)
  monthly_cost_cap NUMERIC(15,2) NOT NULL DEFAULT 500
  soft_alert_at NUMERIC(3,2) NOT NULL DEFAULT 0.80  -- 80%
  current_month_spend NUMERIC(15,2) NOT NULL DEFAULT 0
  reset_at TIMESTAMPTZ
```

Session memory lives in Redis for the hot window; DB is the durable log.

## 9. API Design

```
POST /api/v1/ai/chat                  # SSE stream
POST /api/v1/ai/chat/sessions
GET  /api/v1/ai/chat/sessions
GET  /api/v1/ai/chat/sessions/{id}/messages
DELETE /api/v1/ai/chat/sessions/{id}
POST /api/v1/ai/summarize             # utility endpoint used programmatically
POST /api/v1/ai/extract               # structured data extraction
POST /api/v1/ai/qa                    # question over hospital data (v2.1)
GET  /api/v1/ai/usage                 # my usage summary
GET  /api/v1/ai/hospital-usage        # admin only
GET  /api/v1/ai/budgets               # admin only
PUT  /api/v1/ai/budgets               # admin only
```

**Chat request:**

```json
{
  "session_id": "...",
  "message": "Summarize the last three visits for MRN-2026-00042",
  "stream": true
}
```

## 10. Permissions

- `ai.chat`
- `ai.chat.session.manage.own`
- `ai.summarize` (internal service scope)
- `ai.extract` (internal service scope)
- `ai.qa` (v2.1)
- `ai.usage.read.own`
- `ai.usage.read.hospital`
- `ai.budget.manage`

## 11. Validation Rules

- Message ≤ 10,000 chars.
- Session ownership enforced.
- Tool arguments validated against the tool's Pydantic schema.

## 12. UI Requirements

- Chat panel accessible from a fixed side/bottom position.
- Streaming Markdown rendering.
- Tool call display: "Looking up patient…" progress indicators.
- Session list drawer.
- Cost / usage indicator (admins).
- Feedback thumbs-up/down per assistant reply (feeds eval set candidates).

## 13. AI Integration Points

This module IS the AI integration. See `08-AI_ARCHITECTURE.md` for the layer detail.

## 14. Edge Cases

- Provider timeout mid-stream → catch, emit an error event, offer retry.
- Tool call fails → surface structured error to model; model can retry or apologize.
- Session over token limit → older turns compressed into a summary; not silently dropped.
- User attempts to use AI to see another patient not in their scope → tool call returns permission denied; model relays.
- Budget exceeded mid-response → allow current turn to finish; block next turn with clear message.

## 15. Cross-Module Dependencies

- Consumed by: every module for internal AI capabilities.
- Provides to: chat UI + programmatic AI endpoints.
- Depends on: User Management (identity), Audit (log AI actions), external providers.

## 16. Testing Requirements

- Unit: prompt rendering, tool argument validation, budget check.
- Repository: session + message CRUD.
- API: streaming, permission gates, budget throttling.
- Integration: chat turn with a real tool call against a fixture DB.
- AI eval: golden set for each named prompt.
- Adversarial: prompt-injection attempts on user input; verify tool call permission checks hold under prompt-injected tool arguments.

## 17. Acceptance Criteria

- AC-1: A user can chat with the assistant and receive streaming responses starting within 1s.
- AC-2: Every AI response is logged with tokens and cost.
- AC-3: A tool call cannot access data outside the user's permission scope.
- AC-4: Budget hard cap prevents further AI calls until reset or raised.
- AC-5: Prompt version updates are blocked from merging on eval regression.

## 18. Rollout Plan

- Ships with MVP with two providers (Anthropic + Groq).
- Behind `feature.ai.chat` for first two weeks post-launch.

## 19. Future Scope

- Voice input / output (v3)
- Multi-agent workflows (v3)
- Cross-hospital knowledge base (v3, with strict consent)
- Long-term opt-in user memory (v2.2)

## 20. Open Questions

- Default monthly budget per hospital pilot? Proposed: $200 USD equivalent per hospital, tunable per pilot.
