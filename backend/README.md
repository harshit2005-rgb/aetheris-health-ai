# Aetheris Health AI — Backend

FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL 16. Layout follows
[`docs/09-PROJECT_STRUCTURE.md`](../docs/09-PROJECT_STRUCTURE.md); conventions
follow [`backend/CLAUDE.md`](./CLAUDE.md).

## The layer rule

```
Route (app/api/v1/) ──▶ Service (app/services/) ──▶ Repository (app/repositories/) ──▶ DB
```

Never skip a layer. Repositories never call other repositories — services
compose across them.

## Layout

| Path | Holds |
|---|---|
| `app/api/v1/` | FastAPI routers. No business logic — parse, delegate, respond. |
| `app/api/dependencies/` | DI composition root: `db`, `repositories`, `services`, `auth`, `ai`. |
| `app/core/` | Config, constants, error codes, response envelope, exceptions, logging, lifecycle. |
| `app/database/` | Declarative base, async engine, session factory. Plumbing only. |
| `app/models/` | SQLAlchemy models, one module per aggregate. |
| `app/repositories/` | Data access, one `<domain>_repository.py` per aggregate root. |
| `app/services/` | Business logic, one `<domain>_service.py` per aggregate. |
| `app/schemas/` | Pydantic DTOs at the API boundary. |
| `app/ai/` | AI platform layer — providers, prompts, tools, memory, context, evaluation. |
| `app/middleware/` | Request ID, logging, rate limiting, CORS, exception handling. |
| `app/utils/` | Pure helpers — no framework, no DB. |
| `app/background/` | Worker, scheduler, jobs. |
| `app/seeds/` | Idempotent seed data (permissions, system roles). |
| `app/mcp/` | MCP tool wrappers (v2.1+). |
| `app/tests/` | `unit/`, `repository/`, `api/`, `integration/`, `ai_eval/`. |
| `migrations/` | Alembic environment and versions. Append-only once merged. |

## Adding a module

Follow the 12-step procedure in
[`docs/10-DEVELOPMENT_GUIDE.md`](../docs/10-DEVELOPMENT_GUIDE.md). Placement:

1. Migration → `migrations/versions/`
2. Model → `app/models/<domain>.py`, re-exported from `app/models/__init__.py`
3. Repository → `app/repositories/<domain>_repository.py`, provider in `app/api/dependencies/repositories.py`
4. Service → `app/services/<domain>_service.py`, provider in `app/api/dependencies/services.py`
5. Schemas → `app/schemas/<domain>.py`
6. Router → `app/api/v1/<domain>.py`, registered in `app/main.py`
7. Tests → `app/tests/unit/services/`, `app/tests/repository/`, `app/tests/api/`

## Commands

Run from `backend/`. Requires [`uv`](https://docs.astral.sh/uv/).

```
make install     # sync dependencies (including dev extras)
make dev         # uvicorn with hot reload on :8000
make lint        # ruff check + mypy --strict
make format      # ruff format
make test        # pytest with coverage
make migrate     # alembic upgrade head
make migration   # alembic revision --autogenerate
```

Tool config lives in `ruff.toml` and `mypy.ini`; packaging, pytest, and
coverage config live in `pyproject.toml`.
