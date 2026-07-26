# Aetheris Health AI — Project Context

You are working on **Aetheris Health AI**, an enterprise AI-first Hospital Management Platform. This file is loaded automatically at the start of every session. Read the sections below before doing anything else.

---

## Where the Truth Lives

Every decision on this project has a corresponding document. **Always read the relevant doc before writing code.**

- **Architecture**: `docs/03-ARCHITECTURE.md` — read before creating/refactoring any module
- **Tech stack**: `docs/04-TECH_STACK.md` — what to use, what NOT to use
- **Database**: `docs/05-DATABASE_DESIGN.md` — conventions, naming, migrations
- **API standards**: `docs/06-API_STANDARDS.md` — every endpoint follows this
- **Security**: `docs/07-SECURITY.md` — non-negotiable
- **AI**: `docs/08-AI_ARCHITECTURE.md` — how AI is layered in
- **Project structure**: `docs/09-PROJECT_STRUCTURE.md` — where files go
- **Development workflow**: `docs/10-DEVELOPMENT_GUIDE.md` — how to add a module
- **Testing**: `docs/11-TESTING_STRATEGY.md` — required coverage
- **Modules**: `docs/modules/` — one spec per module. Read the spec before implementing.
- **Sprint plan**: `docs/15-SPRINT_PLAN.md` — what we're building this sprint
- **Workflows**: `docs/16-END_TO_END_WORKFLOWS.md` — release gates

**Rule:** if you're touching module X, read `docs/modules/XX-<name>.md` first.

---

## Non-Negotiable Architectural Rules

Break these and the PR is rejected. No exceptions.

1. **Clean architecture layering:** API → Service → Repository → Database. Never skip a layer.
2. **Repositories never call other repositories.** Only Services orchestrate across repositories.
3. **API routes contain zero business logic.** Just parse, delegate, respond.
4. **Every table with tenant data has a `hospital_id` column.** No exceptions.
5. **Every query filters by `hospital_id` at the repository layer.** Enforced via base repository — don't bypass.
6. **Money is `NUMERIC(15,2)`. Never float. Never JSON number without care.**
7. **All datetimes are stored `TIMESTAMPTZ` in UTC.** Convert at the edge.
8. **All primary keys are `UUID`.** No auto-increment ints.
9. **All mutating operations produce an audit log entry.** Use the middleware — do not skip.
10. **No secrets in code, commits, or logs.** Use env vars / secrets manager.

---

## Non-Negotiable Security Rules

1. **Passwords hashed with Argon2id.** Never MD5, SHA-1, SHA-256, or bcrypt.
2. **JWTs are short-lived (15 min) + refresh (7d) with rotation and reuse detection.**
3. **Every endpoint requires authentication** unless explicitly public (`/healthz`, `/api/v1/auth/login`).
4. **Every endpoint checks permissions** via the permission dependency. No "just this once" bypasses.
5. **User input is validated with Pydantic** before it reaches services.
6. **SQL is parameterized via SQLAlchemy.** Never string-concatenate SQL.
7. **File uploads: verify MIME + size + extension. Store in object storage, not DB.**
8. **Rate limiting on all public endpoints.**
9. **CORS locked to configured origins only.** Never `*` in production.
10. **PII in logs is redacted or omitted.**

---

## Coding Conventions

### Backend (Python)
- Python 3.12+, all functions async unless clearly sync
- Type hints everywhere; `mypy --strict` clean
- Formatter: `ruff format`; linter: `ruff check`
- Docstrings for public functions (Google style)
- Import order: stdlib → third-party → local
- No `print()` — use structured logging
- No `except:` — catch specific exceptions
- Repository methods return domain models, not raw SQLAlchemy rows

### Frontend (TypeScript)
- React 18+, functional components with hooks
- TypeScript strict mode; no `any`
- Tailwind utility-first; no inline styles
- Shadcn UI for base components; extend, don't fork
- React Query for server state; Zustand for client state
- File naming: `PascalCase.tsx` for components, `camelCase.ts` for utilities

### Git
- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`
- Branch naming: `sprint-N/module-name` or `fix/short-description`
- PR title matches the commit subject
- Every PR has a description with: what, why, how tested

---

## How to Add a Module (Follow the 12-Step Procedure)

See `docs/10-DEVELOPMENT_GUIDE.md` Section on "Adding a Module." Summary:

1. Read the module spec in `docs/modules/XX-<name>.md` fully
2. Create the migration in `backend/alembic/versions/`
3. Create the model in `backend/app/models/`
4. Create the repository in `backend/app/repositories/`
5. Create the service in `backend/app/services/`
6. Create the schema (DTOs) in `backend/app/schemas/`
7. Create the router in `backend/app/api/v1/`
8. Wire dependencies in `backend/app/api/deps.py`
9. Write unit tests for service (mock repository)
10. Write integration tests for API (real DB, transactional rollback)
11. Add frontend types + API client wrapper
12. Build frontend components

**Never do steps out of order. Never skip 9–10.**

---

## When to Ask, When to Plan, When to Act

- **Ask first if**: the request contradicts a doc, would touch cross-module state, or the module spec is silent on the decision
- **Plan first if**: the change touches more than 3 files, involves migrations, or affects public API contracts
- **Just act if**: the change is bug-fix-scale, style, or explicitly mapped by the spec
- **Stop and flag if**: you find a security issue, a broken multi-tenant filter, or hardcoded secrets. Do not "just fix in passing." Flag it clearly.

---

## What NOT to Do

- Do not add libraries without asking. Every new dependency is a review decision.
- Do not create shell scripts (`.sh`). Use `Makefile` targets or Python scripts.
- Do not write raw SQL in services or routes. Repositories only.
- Do not add TODO comments without a linked issue/ticket.
- Do not modify migrations after they've been merged. Add a new migration instead.
- Do not commit `.env`, secrets, or generated files.
- Do not use `localStorage` for tokens in the frontend — use HTTP-only cookies for refresh, memory for access.
- Do not create a new module without a matching spec in `docs/modules/`.

---

## Commands You Can Run

Prefer `Makefile` targets over ad-hoc commands.

- `make up` — start full stack (backend, frontend, Postgres, Redis)
- `make down` — stop everything
- `make test` — run all tests (backend + frontend)
- `make test-backend` — backend tests only
- `make test-frontend` — frontend tests only
- `make lint` — ruff + eslint
- `make format` — ruff format + prettier
- `make migrate` — apply pending Alembic migrations
- `make migration name=<name>` — generate a new migration
- `make e2e` — run Playwright E2E workflow tests
- `make seed` — seed demo data (1 hospital, 1 admin, sample users)

---

## Prohibited Areas Without Explicit Approval

Do not modify without asking:

- `backend/app/core/security.py` (auth logic)
- `backend/app/core/tenancy.py` (multi-tenant filter)
- `backend/app/repositories/base.py` (base repository — enforces tenancy)
- Any file under `backend/alembic/versions/` that's already been merged
- `docker-compose.yml`, `.github/workflows/`
- `.env.example` (schema of env vars)
- Any file in `docs/` — flag suggested changes, don't apply them

---

## Session Discipline

- At the start of a session, tell me which module/task you're working on. I'll read the spec.
- After every meaningful change, run `make test-backend` (or frontend equivalent).
- Before you say "done," confirm: tests pass, lint passes, migration applies cleanly (if any), audit log entries fire (if mutating).
- If context is getting long, propose using `/clear` and I'll re-anchor from this file + the relevant module spec.

---

## Project Vocabulary

- **Hospital** = a tenant. Every user belongs to exactly one.
- **MRN** = Medical Record Number, per-patient per-hospital identifier
- **Slot** = a bookable time window on a doctor's calendar
- **Module** = one bounded context (auth, patients, billing, etc.)
- **Service** = business logic class inside a module
- **Repository** = data access class inside a module
- **DTO / Schema** = Pydantic model used at the API boundary
- **Model** = SQLAlchemy ORM class
- **Audit log** = immutable record of every mutating operation

---

_Last updated: 2026-07-26. When this file is wrong, fix it before writing the code that would depend on the fix._
