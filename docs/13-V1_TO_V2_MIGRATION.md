# 13 — v1 → v2 Migration

Harshit's v1 ships this Monday. It's a real, working prototype. v2 is a rebuild on the founding engineering constitution — not a refactor.

This document explains **what carries over**, **what gets rebuilt**, and **why**.

---

## 1. v1 Summary (for context)

- **Repo:** github.com/harshit2005-rgb/ai-hospital-management-platform
- **Stack:** Next.js + FastAPI + SQLite + Groq LLM
- **Architecture:** Modular runtime, skills-based AI, MCP-inspired servers
- **Modules present:** Patient Management, Appointment Scheduling, Billing, Reports, AI Assistant, Settings
- **Notable strengths:** modular runtime idea, AI-first mindset, skills abstraction, clean UI direction
- **Notable gaps (relative to enterprise target):** SQLite (single-file DB), no proper auth/RBAC, no audit logs, no multi-tenant isolation, no test infrastructure, no migrations, no observability, no provider abstraction

None of the v1 gaps are criticisms — v1's job was to prove the shape and demo the vision. v2's job is to make it enterprise-ready.

---

## 2. Migration Philosophy

**We rebuild, but we do not throw away.**

- **Ideas carry over:** the modular runtime, the AI-first module design, the skills concept, the UI direction, the demo scenarios
- **Code does not directly carry over:** v2 is a new repo, new patterns, new stack in places (Next.js → Vite + React; SQLite → PostgreSQL)
- **Data:** if any hospital uses v1 in the pilot window, we build a one-way migration script from SQLite to PostgreSQL

The reason we don't refactor in place: the architectural gap between "prototype" and "enterprise foundation" is wide enough that trying to bridge it feature-by-feature costs more than starting on the right foundation and porting the good ideas across.

---

## 3. What Carries Over

### 3.1 Concepts

| From v1 | To v2 | Notes |
|---|---|---|
| Modular Runtime | Modular Monolith with per-module folders | Same spirit, cleaner boundaries |
| Skills abstraction | AI Tools + Prompt Registry | The skills idea becomes typed tools + versioned prompts |
| MCP-inspired servers | Actual MCP integration (v2.1) | v1's inspiration becomes v2's reality |
| Medical-themed UI | Same design direction | Continue with Tailwind + Shadcn |
| Groq for fast inference | Groq as one provider in the abstraction | Not the only provider anymore |
| Domain-first module split | Domain-first modules with strict service/repository split | Adds the layering |

### 3.2 UI Direction

Harshit's landing page and dashboard style stay as the visual reference for v2. We take the aesthetic and rebuild it on Shadcn primitives so we get accessibility, dark mode, and consistency for free.

### 3.3 Demo Scripts / Flows

Any demos v1 already runs — patient registration, appointment booking, AI-assisted summary, invoice generation — become integration test scenarios in v2. They are the "must not regress" set.

---

## 4. What Gets Rebuilt

### 4.1 Backend

| Concern | v1 | v2 |
|---|---|---|
| Database | SQLite | PostgreSQL |
| ORM | Direct SQL / lightweight | SQLAlchemy 2.x async |
| Migrations | Manual / minimal | Alembic |
| Auth | Minimal / demo | JWT + refresh + RBAC + Permissions |
| Multi-tenant | Single tenant | Multi-tenant with `hospital_id` on every row |
| Audit logs | None | Immutable audit table on every significant action |
| Structured logging | Print / basic | structlog JSON |
| Configuration | Mixed | Env vars only via Pydantic Settings |
| Background jobs | None | RQ workers |
| Testing | Minimal | Full pyramid: unit / repo / API / integration / AI eval |
| Error handling | Ad hoc | Global handler + standard envelope |
| Rate limiting | None | Redis-backed per user + hospital + AI |
| DI | Ad hoc | FastAPI Depends everywhere |
| Response format | Varies | Standard envelope (see 06-API_STANDARDS.md) |

### 4.2 Frontend

| Concern | v1 | v2 |
|---|---|---|
| Framework | Next.js | Vite + React 18 |
| Language | TypeScript | TypeScript (strict) |
| Styling | Tailwind + custom | Tailwind + Shadcn UI |
| Motion | GSAP + Three.js | Kept for marketing/landing only; not in app |
| State (server) | Ad hoc fetch | React Query |
| State (client) | Ad hoc | Zustand where needed |
| Forms | Basic | React Hook Form + Zod |
| Auth | Minimal | Full JWT + refresh + protected routes + permission gates |
| Error boundaries | None | Global + per-route |
| Testing | Minimal | Vitest + React Testing Library |

**Why Vite over Next.js:** the staff-facing hospital app doesn't need SSR. Vite is faster to develop with. If we later need a marketing site or a public patient portal with SEO, we spin up a separate Next.js app that consumes the same API.

### 4.3 AI Layer

| Concern | v1 | v2 |
|---|---|---|
| Provider | Groq only | Anthropic + Groq + OpenAI + Gemini + self-hosted, via abstraction |
| Prompts | Inline in code | Versioned YAML in `app/ai/prompts/` |
| Function calling | Skills-based | Typed tools wrapping services |
| Memory | Ad hoc | Redis-backed session memory, bounded window |
| Observability | Minimal | `ai_interactions` table + dashboards |
| Cost tracking | None | Per hospital, per user, per use case |
| Evaluation | None | Golden sets + CI eval on prompt version changes |
| MCP | Inspired-by | Real MCP in v2.1 |
| RAG | None | pgvector-based RAG in v2.1 |

---

## 5. Migration Order

Recommended order for the founding sprint to go from empty repo to running MVP:

### Week 1: Foundation
1. Repo scaffold, docker-compose, env template
2. Backend: FastAPI app factory, structlog, config, health checks
3. Frontend: Vite + React + Tailwind + Shadcn scaffold with routing skeleton
4. CI: lint, type, test on every PR

### Week 2: Data & Auth
5. Database session, base model, audit mixin, soft-delete mixin
6. Alembic init, hospitals + users + roles + permissions tables
7. Seed script (permissions catalog, system roles)
8. Auth module: login, refresh, logout, password hashing
9. Middleware: request ID, exception handler, auth
10. Frontend: login page, protected routes, token store

### Week 3: Patients & Doctors
11. Patient module (model, repo, service, schemas, routes, permissions)
12. Doctor module (same)
13. Frontend: patient list, patient detail, doctor list

### Week 4: Appointments & Billing
14. Appointment module
15. Slots API, calendar view
16. Billing module: services catalog, invoices, payments (with idempotency)
17. Frontend: booking flow, invoice screens

### Week 5: AI Foundation
18. AI provider interface
19. Anthropic + Groq providers
20. Prompt registry + first prompts (patient summarize, invoice explanation)
21. AI service orchestration + `ai_interactions` logging
22. First AI use case wired into the UI (patient summary)

### Week 6: Notifications, Audit, Reports, Polish
23. Audit service (called from every mutating service)
24. Notification service (email + in-app)
25. Reports & dashboard endpoints
26. Frontend: dashboards, notifications center
27. E2E integration test for the golden flow (register patient → book → complete → invoice → pay → AI summary)

### Week 7-8: Hardening
28. Rate limiting
29. Structured logging + metrics
30. Docker images + staging deployment
31. Load test on golden flow
32. Security review
33. Documentation freeze

That's ~8 weeks for the MVP if the team stays focused. Realistic given the founding team size; scope stays tight because everything above matches the MVP feature list in `02-FEATURES.md`.

---

## 6. Data Migration (from v1 SQLite → v2 PostgreSQL)

If any hospital adopts v1 in the pilot window and later moves to v2, we ship a one-time migration:

- Extract v1 SQLite tables via SQLAlchemy
- Map to v2 schema (generate UUIDs; assign to a single hospital tenant)
- Import via a Python script `scripts/db/migrate_from_v1.py`
- Verify counts and spot-check records
- Cutover with the hospital in a maintenance window

The migration script is written **once we have a v1 dataset to migrate**, not preemptively.

---

## 7. Deprecation of v1

Once v2 is generally available:

- v1 repository archived on GitHub
- README updated pointing at v2
- Any pilot hospital on v1 gets a documented upgrade path
- v1 issues closed with a link to v2 tracking issues

---

## 8. What Harshit's v1 Proves

Do not undersell the v1 shipping this Monday:

- The AI-first module idea is real and works
- The skills / MCP direction resonates with the vision
- The medical UI aesthetic maps to what hospitals actually want
- A full-stack team of founders can ship end-to-end

v1 is the case for building v2. v2 is not v1's replacement out of criticism; it's v1's foundation for the next decade.

---

## 9. Points of Contact During Migration

- **v1 questions:** Harshit
- **v2 architecture decisions:** all founders sign off on doc PRs
- **AI layer questions:** whoever owns `app/ai/` in the founding sprint
- **Frontend questions:** whoever owns `frontend/` in the founding sprint

Ownership is documented in the CODEOWNERS file once the repo is created.
