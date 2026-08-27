# 03 — System Architecture

**Status:** Finalized. Do not modify without a formal change proposal.

This document describes *how* Aetheris Health AI is built. It is derived from the founding architectural constitution and is the definitive reference for every engineer, human or AI, working on the codebase.

---

## 1. Architectural Style

Aetheris is a **Modular Monolith** with **Clean Architecture** foundations, designed to be **Microservice Ready**.

We chose a modular monolith because:
- **Faster MVP delivery** — one repo, one deploy, one database
- **Lower operational complexity** — no distributed systems debugging in the founding phase
- **Cheaper infrastructure** — critical for pilot hospitals
- **Easier refactoring** — modules can evolve without breaking network contracts

We designed it as microservice-ready because:
- Any module can be lifted into its own service without rewriting business logic
- Cross-module communication already goes through services, not shared repositories or shared database access
- The AI layer already speaks provider-agnostic interfaces

## 2. Core Principles

1. **Clean Architecture** — business logic is independent of frameworks, databases, and UI
2. **SOLID** — every class earns its keep against these principles
3. **Repository Pattern** — persistence is isolated behind repositories
4. **Service Layer** — business rules live in services, nowhere else
5. **Dependency Injection** — services receive their dependencies, they don't construct them
6. **DTO Pattern** — database entities never leak into API responses
7. **Layered Boundaries** — no layer bypasses another

## 3. Layer Diagram

```
┌─────────────────────────────────────────────┐
│              Presentation Layer             │
│              (React frontend)               │
└────────────────────┬────────────────────────┘
                     │  HTTP / JSON
┌────────────────────▼────────────────────────┐
│                 API Layer                   │
│           (FastAPI routes)                  │
│  auth, validation, formatting, error map    │
└────────────────────┬────────────────────────┘
                     │  Function calls
┌────────────────────▼────────────────────────┐
│               Service Layer                 │
│           (Business logic)                  │
│  workflows, rules, orchestration, AI calls  │
└────────────────────┬────────────────────────┘
                     │  Function calls
┌────────────────────▼────────────────────────┐
│             Repository Layer                │
│         (Persistence only)                  │
│  CRUD, queries, transactions, filters       │
└────────────────────┬────────────────────────┘
                     │  SQLAlchemy
┌────────────────────▼────────────────────────┐
│                Database                     │
│              (PostgreSQL)                   │
└─────────────────────────────────────────────┘

                    ┌────────┐
                    │   AI   │  (cross-cutting)
                    │ Layer  │  called by services only
                    └────────┘
```

## 4. Layer Responsibilities

### 4.1 Presentation Layer (Frontend)

**Owns:** UI rendering, user interaction, calling APIs, client-side routing, UI-level validation.

**Never owns:** business rules, direct database access, cross-tenant logic.

### 4.2 API Layer

**Owns:** HTTP routes, request/response schemas, authentication middleware, authorization checks, input validation, exception → HTTP mapping.

**Never owns:** business rules, SQL, direct database access. Routes are thin.

**Example (correct):**
```python
@router.post("/patients", response_model=PatientResponse)
async def create_patient(
    payload: PatientCreateSchema,
    service: PatientService = Depends(get_patient_service),
    current_user: User = Depends(require_permission("patient.create")),
):
    patient = await service.create(payload, actor=current_user)
    return PatientResponse.from_dto(patient)
```

### 4.3 Service Layer

**Owns:** every business rule, workflow orchestration, cross-module coordination, permission checks beyond simple RBAC, transaction boundaries, AI orchestration.

**Never owns:** SQL, HTTP concerns, view formatting. Never returns SQLAlchemy models directly.

**Example (correct):**
```python
class PatientService:
    def __init__(self, patient_repo: PatientRepository, audit: AuditService):
        self._patients = patient_repo
        self._audit = audit

    async def create(self, data: PatientCreateSchema, actor: User) -> PatientDTO:
        if await self._patients.find_by_mrn(data.mrn):
            raise DuplicatePatientError(data.mrn)
        patient = await self._patients.create(data, created_by=actor.id)
        await self._audit.log("patient.created", actor=actor, target=patient.id)
        return PatientDTO.from_orm(patient)
```

### 4.4 Repository Layer

**Owns:** CRUD, queries, filters, pagination, transactions on a single aggregate.

**Never owns:** business rules, cross-repository calls, API calls, workflow decisions.

**Example (correct):**
```python
class PatientRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def find_by_mrn(self, mrn: str) -> Patient | None:
        stmt = select(Patient).where(Patient.mrn == mrn, Patient.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()
```

### 4.5 Database Layer

PostgreSQL, SQLAlchemy 2.x async, Alembic migrations. UUID primary keys, audit columns, soft delete on every table. See `05-DATABASE_DESIGN.md`.

### 4.6 AI Layer

Lives in `app/ai/`. Called only by services. Never talks to repositories or the database directly. See `08-AI_ARCHITECTURE.md`.

## 5. Directory Layout (High Level)

See `09-PROJECT_STRUCTURE.md` for the complete tree.

```
backend/
├── app/
│   ├── api/            # FastAPI routes, dependencies
│   ├── core/           # config, security, logging, constants
│   ├── models/         # SQLAlchemy models
│   ├── schemas/        # Pydantic schemas (request/response/DTO)
│   ├── repositories/   # persistence layer
│   ├── services/       # business logic
│   ├── ai/             # AI providers, prompts, agents, tools
│   ├── mcp/            # MCP tool wrappers (future)
│   ├── middleware/     # auth, logging, exception middleware
│   ├── utils/          # shared utilities
│   ├── database/       # session, connection, base
│   ├── migrations/     # alembic migrations
│   └── tests/          # unit, integration, ai eval
└── main.py
```

## 6. Dependency Injection

Every layer receives its dependencies through FastAPI's `Depends()` system. We do not construct services inside routes.

```python
# app/api/dependencies.py

def get_db() -> AsyncSession: ...
def get_patient_repository(db: AsyncSession = Depends(get_db)) -> PatientRepository:
    return PatientRepository(db)
def get_patient_service(
    repo: PatientRepository = Depends(get_patient_repository),
    audit: AuditService = Depends(get_audit_service),
) -> PatientService:
    return PatientService(repo, audit)
```

Benefits:
- Trivial to swap implementations for tests
- Route handlers stay clean
- Onboarding engineers can follow the wire graph

## 7. Module Structure

Every business module follows the exact same internal structure:

```
patients/
├── routes.py         # FastAPI router
├── service.py        # PatientService
├── repository.py     # PatientRepository
├── schemas.py        # Pydantic request/response/DTO
├── models.py         # SQLAlchemy models
├── permissions.py    # permission constants for this module
├── validators.py     # module-specific validation helpers
├── exceptions.py     # module-specific exceptions
└── constants.py      # enums, status codes, magic strings
```

This structure is **not optional**. Every new module adopts it. This is what makes the modular monolith → microservice migration mechanical.

## 8. Module Communication Rules

**Allowed:**
- `PatientService` calls `AppointmentService`
- `AppointmentService` calls `BillingService`
- Any service calls the AI Layer through `AIService`

**Forbidden:**
- `PatientRepository` calls `AppointmentRepository`
- `AppointmentRoute` calls `PatientRepository` directly
- Any repository imports another module's models
- Any service reaches into another module's database tables

If module A needs data owned by module B, it goes through B's service. Full stop.

## 9. Transactions

Transactions are owned by the **service layer**, not the repository. A service that orchestrates writes across multiple repositories opens a transaction and commits or rolls back atomically.

```python
async def book_appointment(...):
    async with self._uow.transaction():
        appointment = await self._appt_repo.create(...)
        await self._slot_repo.reserve(...)
        await self._audit.log("appointment.booked", ...)
        return appointment
```

Critical workflows that **must be transactional**:
- Appointment booking (appointment + slot reservation)
- Billing (invoice + payment + audit)
- Pharmacy dispensing (prescription + stock deduction)
- Inventory receiving (PO + stock update)
- Any medical record creation (record + audit)

## 10. Error Handling

- Business exceptions live in each module's `exceptions.py`
- A global exception handler in `app/middleware/exceptions.py` maps exceptions to HTTP responses
- Every response follows the standard envelope (see `06-API_STANDARDS.md`)
- No `except Exception: pass`. Ever.

## 11. Logging

Structured JSON logs. Every significant action gets a log entry with:

```json
{
  "timestamp": "...",
  "level": "INFO",
  "event": "patient.created",
  "actor_id": "...",
  "hospital_id": "...",
  "target_type": "patient",
  "target_id": "...",
  "request_id": "...",
  "duration_ms": 42
}
```

Logs and audit entries are related but different: logs are for observability, audit is for compliance. Some events go to both.

## 12. Configuration

Only environment variables. Loaded via `app/core/config.py` using Pydantic Settings. No hardcoded values. No committed secrets. Ever.

## 13. Scalability Strategy

**Phase 1 (MVP):** Single-instance modular monolith, single PostgreSQL, single Redis.
**Phase 2 (v2.x):** Horizontal scaling of the monolith behind a load balancer; Redis for shared session and cache; PostgreSQL with read replicas.
**Phase 3 (Enterprise):** Extract hottest modules (AI, Notifications, Reporting) into standalone services. Introduce message queue for async work. Introduce object storage for large files.
**Phase 4 (Global):** Regional deployments; multi-region PostgreSQL; regional AI providers for data residency.

Nothing about the code needs to change dramatically for any of these transitions because the module boundaries are already the right seams.

## 14. Testing Boundaries

- **Unit tests** — services and utilities (mocked repositories)
- **Repository tests** — against a real ephemeral PostgreSQL (Docker)
- **API tests** — HTTP layer, dependency-injected in-memory service stubs
- **Integration tests** — full stack, real DB, real Redis, mocked AI providers
- **AI evaluation tests** — golden-set regression tests on prompt changes (see `08-AI_ARCHITECTURE.md`)

## 15. Non-Negotiables

The following rules never bend. If a proposed implementation violates any of them, the implementation is wrong.

1. Business logic never lives in routes
2. Routes never touch the database
3. Services never write SQL
4. Repositories never call other repositories
5. Repositories never call APIs (internal or external)
6. AI never touches the database
7. Database models never appear in API responses
8. No hardcoded configuration
9. Every action mutating data goes through a service
10. Every significant action generates an audit log entry

## 16. Reference Documents

- `04-TECH_STACK.md` — every technology and why
- `05-DATABASE_DESIGN.md` — schema conventions
- `06-API_STANDARDS.md` — REST conventions and response envelope
- `07-SECURITY.md` — AuthN, AuthZ, encryption
- `08-AI_ARCHITECTURE.md` — AI layer detail
- `09-PROJECT_STRUCTURE.md` — full folder tree
- `modules/00-MODULE_TEMPLATE.md` — the spec every module must follow
