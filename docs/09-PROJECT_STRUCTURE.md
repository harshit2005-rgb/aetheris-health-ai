# 09 — Project Structure

The canonical layout of the Aetheris Health AI repository. Every new file belongs somewhere on this map. If it doesn't, the map extends before the file lands.

---

## Repository Root

```
aetheris/
├── backend/
├── frontend/
├── infra/
├── docs/
├── scripts/
├── .github/
│   └── workflows/
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
├── .gitignore
├── README.md
├── LICENSE
└── CHANGELOG.md
```

---

## Backend Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── patients.py
│   │   │   ├── doctors.py
│   │   │   ├── appointments.py
│   │   │   ├── billing.py
│   │   │   ├── laboratory.py
│   │   │   ├── pharmacy.py
│   │   │   ├── inventory.py
│   │   │   ├── notifications.py
│   │   │   ├── audit.py
│   │   │   ├── reports.py
│   │   │   ├── ai.py
│   │   │   └── hospital_settings.py
│   │   └── dependencies/
│   │       ├── __init__.py
│   │       ├── auth.py               # get_current_user, require_permission
│   │       ├── db.py                 # get_db session
│   │       ├── services.py           # DI for every service
│   │       ├── repositories.py       # DI for every repository
│   │       └── ai.py                 # DI for AI service
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                 # Pydantic Settings
│   │   ├── security.py               # hashing, JWT, MFA
│   │   ├── logging.py                # structlog setup
│   │   ├── constants.py              # global constants
│   │   ├── error_codes.py            # error code catalog
│   │   ├── envelope.py               # standard response envelope
│   │   └── exceptions.py             # base exception classes
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                   # Base, audit mixin, soft-delete mixin
│   │   ├── hospital.py
│   │   ├── user.py
│   │   ├── role.py
│   │   ├── permission.py
│   │   ├── patient.py
│   │   ├── doctor.py
│   │   ├── appointment.py
│   │   ├── consultation.py
│   │   ├── prescription.py
│   │   ├── service.py                # billable service catalog
│   │   ├── invoice.py
│   │   ├── payment.py
│   │   ├── notification.py
│   │   ├── audit_log.py
│   │   └── ai_interaction.py
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── common.py                 # pagination, envelope, errors
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── patient.py
│   │   ├── doctor.py
│   │   ├── appointment.py
│   │   ├── billing.py
│   │   ├── notification.py
│   │   ├── ai.py
│   │   └── ...
│   │
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base.py                   # BaseRepository with soft-delete-aware queries
│   │   ├── user_repository.py
│   │   ├── patient_repository.py
│   │   ├── doctor_repository.py
│   │   ├── appointment_repository.py
│   │   ├── consultation_repository.py
│   │   ├── invoice_repository.py
│   │   ├── payment_repository.py
│   │   ├── notification_repository.py
│   │   ├── audit_repository.py
│   │   └── ai_interaction_repository.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── role_service.py
│   │   ├── permission_service.py
│   │   ├── patient_service.py
│   │   ├── doctor_service.py
│   │   ├── appointment_service.py
│   │   ├── consultation_service.py
│   │   ├── billing_service.py
│   │   ├── payment_service.py
│   │   ├── notification_service.py
│   │   ├── audit_service.py
│   │   ├── report_service.py
│   │   └── hospital_service.py
│   │
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── providers/
│   │   │   ├── base.py
│   │   │   ├── anthropic.py
│   │   │   ├── openai.py
│   │   │   ├── groq.py
│   │   │   └── ollama.py
│   │   ├── prompts/
│   │   │   ├── registry.py
│   │   │   └── templates/
│   │   │       ├── patient/
│   │   │       ├── appointment/
│   │   │       ├── billing/
│   │   │       └── reports/
│   │   ├── services/
│   │   │   ├── ai_service.py
│   │   │   ├── summarization.py
│   │   │   ├── extraction.py
│   │   │   ├── recommendation.py
│   │   │   └── qa.py
│   │   ├── tools/
│   │   │   ├── patient_tools.py
│   │   │   ├── appointment_tools.py
│   │   │   └── billing_tools.py
│   │   ├── memory/
│   │   │   ├── session_memory.py
│   │   │   └── long_term.py
│   │   ├── context/
│   │   │   ├── vector_store.py
│   │   │   └── retriever.py
│   │   ├── evaluation/
│   │   │   ├── golden_sets/
│   │   │   └── evaluators.py
│   │   └── constants.py
│   │
│   ├── mcp/                           # MCP tool wrappers (v2.1+)
│   │   ├── __init__.py
│   │   ├── server.py
│   │   └── tools.py
│   │
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── logging.py
│   │   ├── request_id.py
│   │   ├── exception_handler.py
│   │   ├── rate_limit.py
│   │   └── cors.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── datetime.py
│   │   ├── money.py
│   │   ├── phone.py                   # E.164 helpers
│   │   ├── mrn.py                     # MRN generator
│   │   ├── slug.py
│   │   └── pagination.py
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── session.py                 # async engine, session factory
│   │   ├── base_class.py              # declarative base
│   │   └── unit_of_work.py            # transaction context manager
│   │
│   ├── background/                    # background jobs
│   │   ├── __init__.py
│   │   ├── worker.py
│   │   ├── jobs/
│   │   │   ├── send_notifications.py
│   │   │   ├── nightly_reports.py
│   │   │   └── ai_batch_summaries.py
│   │   └── scheduler.py
│   │
│   ├── seeds/
│   │   ├── __init__.py
│   │   ├── permissions.py
│   │   ├── roles.py
│   │   └── services_starter.py
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── unit/
│   │   │   ├── services/
│   │   │   ├── utils/
│   │   │   └── ai/
│   │   ├── repository/
│   │   ├── api/
│   │   ├── integration/
│   │   └── ai_eval/
│   │
│   ├── __init__.py
│   └── main.py                        # FastAPI app entry
│
├── migrations/                        # Alembic
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── pyproject.toml
├── ruff.toml
├── mypy.ini
├── alembic.ini
├── Dockerfile
├── .dockerignore
└── README.md
```

---

## Frontend Structure

```
frontend/
├── src/
│   ├── app/                           # top-level app shell
│   │   ├── App.tsx
│   │   ├── AppRoutes.tsx
│   │   └── providers.tsx              # React Query, Theme, Toast
│   │
│   ├── layouts/
│   │   ├── AuthLayout.tsx
│   │   ├── DashboardLayout.tsx
│   │   └── PublicLayout.tsx
│   │
│   ├── pages/
│   │   ├── auth/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── ForgotPasswordPage.tsx
│   │   │   └── ResetPasswordPage.tsx
│   │   ├── dashboard/
│   │   │   ├── AdminDashboard.tsx
│   │   │   ├── DoctorDashboard.tsx
│   │   │   └── ReceptionDashboard.tsx
│   │   ├── patients/
│   │   ├── doctors/
│   │   ├── appointments/
│   │   ├── billing/
│   │   ├── laboratory/
│   │   ├── pharmacy/
│   │   ├── inventory/
│   │   ├── reports/
│   │   ├── settings/
│   │   └── ai/
│   │
│   ├── components/
│   │   ├── ui/                        # shadcn primitives
│   │   ├── forms/
│   │   ├── tables/
│   │   ├── charts/
│   │   ├── layout/
│   │   ├── patient/
│   │   ├── appointment/
│   │   ├── billing/
│   │   └── ai/                        # AI Assistant panel, streaming display
│   │
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── usePermissions.ts
│   │   ├── usePagination.ts
│   │   ├── useDebounce.ts
│   │   └── useAiStream.ts
│   │
│   ├── api/                           # generated / hand-written API client
│   │   ├── client.ts                  # axios instance with interceptors
│   │   ├── auth.ts
│   │   ├── patients.ts
│   │   ├── doctors.ts
│   │   ├── appointments.ts
│   │   ├── billing.ts
│   │   ├── reports.ts
│   │   ├── notifications.ts
│   │   └── ai.ts
│   │
│   ├── services/                      # frontend service classes (auth token store, etc.)
│   │   ├── tokenStore.ts
│   │   ├── notificationService.ts
│   │   └── errorReporter.ts
│   │
│   ├── store/                         # Zustand stores
│   │   ├── authStore.ts
│   │   ├── uiStore.ts
│   │   └── notificationStore.ts
│   │
│   ├── contexts/
│   │   └── ThemeContext.tsx
│   │
│   ├── routes/
│   │   ├── ProtectedRoute.tsx
│   │   └── PermissionGate.tsx
│   │
│   ├── utils/
│   │   ├── datetime.ts
│   │   ├── currency.ts
│   │   ├── phone.ts
│   │   └── validators.ts
│   │
│   ├── types/                         # generated from OpenAPI
│   │   └── api.ts
│   │
│   ├── assets/
│   │   ├── logo.svg
│   │   └── ...
│   │
│   ├── styles/
│   │   ├── globals.css
│   │   └── tailwind.css
│   │
│   ├── main.tsx
│   └── vite-env.d.ts
│
├── public/
│   └── favicon.svg
│
├── index.html
├── package.json
├── pnpm-lock.yaml
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.js
├── .eslintrc.cjs
├── .prettierrc
├── Dockerfile
└── README.md
```

---

## Infrastructure

```
infra/
├── docker/
│   ├── nginx.conf
│   ├── postgres/
│   │   └── init.sql
│   └── redis/
├── k8s/                               # v2.2+
│   └── ...
├── terraform/                         # v2.2+
│   └── ...
└── monitoring/
    ├── prometheus.yml
    └── grafana/
        └── dashboards/
```

---

## Docs

```
docs/
├── 01-PRD.md
├── 02-FEATURES.md
├── 03-ARCHITECTURE.md
├── 04-TECH_STACK.md
├── 05-DATABASE_DESIGN.md
├── 06-API_STANDARDS.md
├── 07-SECURITY.md
├── 08-AI_ARCHITECTURE.md
├── 09-PROJECT_STRUCTURE.md
├── 10-DEVELOPMENT_GUIDE.md
├── 11-TESTING_STRATEGY.md
├── 12-DEPLOYMENT.md
├── 13-V1_TO_V2_MIGRATION.md
├── 14-ROADMAP.md
├── modules/
│   ├── 00-MODULE_TEMPLATE.md
│   ├── 01-authentication.md
│   ├── 02-user-management.md
│   ├── 03-patient-management.md
│   ├── 04-doctor-management.md
│   ├── 05-appointment-management.md
│   ├── 06-billing.md
│   ├── 07-laboratory.md
│   ├── 08-pharmacy.md
│   ├── 09-inventory.md
│   ├── 10-reports-dashboard.md
│   ├── 11-notifications.md
│   ├── 12-audit-logs.md
│   ├── 13-ai-assistant.md
│   └── 14-hospital-settings.md
├── adr/                               # architectural decision records
│   └── 0001-modular-monolith.md
└── incidents/                         # postmortems (v2.1+)
```

---

## Scripts

```
scripts/
├── dev/
│   ├── start.sh                       # (use Make target instead — no shell scripts by team convention)
│   └── ...
├── db/
│   ├── seed.py
│   └── reset.py
└── ai/
    ├── run_eval.py
    └── promote_prompt.py
```

> Team convention: prefer Python scripts and Makefile targets over shell scripts.

---

## Placement Rules

1. **New model** → `app/models/<domain>.py` + migration in `migrations/versions/`
2. **New service** → `app/services/<domain>_service.py` + DI wiring in `app/api/dependencies/services.py`
3. **New repository** → `app/repositories/<domain>_repository.py` + DI wiring in `app/api/dependencies/repositories.py`
4. **New route file** → `app/api/v1/<domain>.py` + registered in `app/main.py`
5. **New prompt** → `app/ai/prompts/templates/<module>/<name>.yaml`
6. **New tool** → `app/ai/tools/<module>_tools.py`
7. **New frontend page** → `frontend/src/pages/<module>/<Name>Page.tsx` + route in `AppRoutes.tsx`
8. **New API client** → `frontend/src/api/<module>.ts` (paired with a page)

If placement is unclear, propose it in a docs PR before writing the code.
