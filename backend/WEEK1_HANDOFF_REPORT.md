# Week 1 Handoff — Identity Module Work Report

**Author:** Karthik (branch `k-karthik`) · **Repository:** aetheris-health-ai
**Scope:** `backend/` only — the project ownership rule means nothing outside `backend/` was changed by this work.
**Date:** 2026-08-11

---

## 1. Executive Summary

The identity module (authentication + user management) was implemented per the Week 1 spec
(`docs/modules/01-authentication.md`, `docs/modules/02-user-management.md`), then extended with
Section A feature work and hardened with Section B defect fixes. A code review later requested
that the login anti-enumeration change be split out of the defect-fix PR — an API-contract change
cannot ride a defect-fix PR — and that formatting, real-database test evidence, and `invite_token`
documentation be added. This report documents the full arc and that restructure.

Three PRs carry the work:

| PR | State | Content |
|----|-------|---------|
| **#13** | merged | Section A — roles/permissions read API, audit events, identity tests |
| **#14** | open | Section B — Week 1 handoff defects B1–B6 + review items (ruff format, `invite_token` docs) |
| **#16** | open | Login anti-enumeration (generic 401 for suspended/locked) + `§5.2` docs proposal |

## 2. What Was Built

### 2.1 Core identity (earlier sessions)

- **User Authentication** — Argon2id password hashing, login/logout, MFA scaffolding.
- **JWT Authentication** — short-lived access tokens (15 min) with permission claims.
- **Refresh Token Rotation** — rotating refresh tokens (7 d); reuse detection invalidates the
  whole session family.
- **User Management** — CRUD, invite, deactivate/reactivate, role assignment, admin-initiated
  password reset, forced password change.

### 2.2 Section A — feature work (PR #13)

- Roles/permissions read API (`GET /permissions`, `GET /roles`, `GET /users/{id}/roles`).
- Audit-event coverage for every mutating operation, with a `RecordingAuditSink` test double so
  tests can assert the events fired.
- Identity unit / integration / repository test suites.
- Review fixes (commit `95353b9`): the `GET /permissions` 422, refresh-token repository tests,
  and role-repository test were all reproduced against real PostgreSQL and repaired.

### 2.3 Section B — Week 1 handoff defects B1–B6 (PR #14)

| Id | Severity | Fix |
|----|----------|-----|
| B1 | CRITICAL | Cross-tenant IDOR closed: all admin user endpoints resolve the target via `get_user(user_id, actor_hospital_id)` and return 404 for foreign/missing users; `assign_role` rejects foreign roles. |
| B2 | HIGH | Permission fail-open inverted to fail-closed; `deactivate_user`/`reactivate_user` now enforce the `user.deactivate` permission they previously skipped. |
| B3 | MEDIUM | PII removed from logs: failed-login and forgot-password paths log a SHA-256 email prefix instead of the raw address. |
| B4 | MEDIUM | Search totals fixed: `count_by_hospital` accepts `search` and shares one `_search_predicate` helper with `list_by_hospital`, so totals can never disagree with filtered pages. |
| B5 | LOW | Invite role validation is all-or-nothing — unknown/foreign role ids fail the whole invite instead of being silently skipped. |
| B6 | LOW | Activation path added: `invite_user` mints a single-use invite token (via `PasswordResetTokenRepository`); `reset_password` transitions INVITED → ACTIVE; `POST /users` exposes the token for the Notifications module. |

### 2.4 Login anti-enumeration (PR #16)

- Suspended and locked accounts now return the **same generic `401 Invalid credentials.`** as an
  unknown email or wrong password — a login attempt can never confirm that an email is a valid
  account (byte-identical envelope across all four failure paths).
- The real reason is still recorded in the **audit event** and log line (CLAUDE.md rule 9).
- `AccountSuspendedError`/`AccountLockedError` remain defined but are documented as **reserved for
  non-login flows**, so the enumeration leak cannot be silently re-introduced.
- The `docs/modules/01-authentication.md` **§5.2** contract update is included in the PR as a
  **proposal for approval** — per CLAUDE.md, docs changes are proposed, not applied.

## 3. Review Response (PR #14 + PR #16 restructure)

| Review item | Resolution |
|---|---|
| 1. Split commit `8583a06` out of PR #14 | PR #14 rebased to B1-B6 only (`01da74a` + develop merge + the two review commits). The enumeration change moved to its own PR #16, rebased onto `develop` with **zero conflicts** — the diff is exactly the 5-file / +76 −56 change. |
| 2. Run `ruff format` on the four PR-touched files | Applied — `services/user_service.py`, `tests/unit/test_user_service.py`, `tests/unit/test_auth_service.py`, `tests/api/test_users_api.py` (formatting only, +17 −29). |
| 3. Re-run tests with a database; paste zero-skip output into the PR | Both PRs ran against a real PostgreSQL: **933 passed / 0 skipped** (PR #14), **906 passed / 0 skipped** (PR #16); output pasted into PR #14. |
| 4. Document `invite_token` in the POST /users response | Swagger 201 example added + docstring credential note — returned exactly once, delivered by Notifications, never logged/echoed. |

## 4. Validation Evidence

| Gate | PR #14 (`k-karthik`) | PR #16 (`fix/login-anti-enumeration`) |
|---|---|---|
| `pytest app/tests` (real PostgreSQL) | **933 passed, 0 skipped** (18.56 s) | **906 passed, 0 skipped** (18.09 s) |
| `mypy app` | clean — 175 source files | clean — 175 source files |
| `ruff check app` | all checks passed | all checks passed |
| `ruff format --check` | PR files formatted; 10 pre-existing unformatted files on develop left untouched | 5 files already formatted |
| Code review | reviewed in parallel with validation — final verdict commit-ready | reviewed in parallel with validation — final verdict commit-ready |

- The test database was a **throwaway cluster created under `/tmp`**; it was stopped and deleted
  after validation (port 5432 free, all temp artifacts removed). No local-Postgres connection was
  added to the project — `config.py`'s `DATABASE_URL` default is pre-existing project config,
  overridden by env vars in production.

## 5. Follow-ups

- **Rebase PR #16 onto `develop` once PR #14 merges** — both PRs touch `auth_service.py`,
  `test_auth_service.py`, and `test_identity_lifecycle.py`; the rebase is offered in the PR body.
- **Timing side-channel (pre-existing, not introduced here):** wrong-password is ~25 ms (Argon2id)
  vs ~3–4 ms for unknown/suspended/locked. A dummy `verify_password` on those branches would give
  full timing parity.
- **Audit-before-commit:** audit events are recorded before `uow.commit()` throughout, so a
  rolled-back transaction still emits an event — harmless with the structlog sink, a correctness
  bug once the durable sink lands. Noted as a follow-up in PR #14.
- **CI gates:** the repo has no `.github/workflows/`, so nothing enforces `ruff check`,
  `ruff format --check`, `mypy`, or pytest at merge time. Wiring `make lint` into CI is the
  highest-value next step.

## 6. Links

- PR #13 (Section A, merged): https://github.com/harshit2005-rgb/aetheris-health-ai/pull/13
- PR #14 (B1–B6 + review items): https://github.com/harshit2005-rgb/aetheris-health-ai/pull/14
- PR #16 (anti-enumeration + §5.2 docs proposal): https://github.com/harshit2005-rgb/aetheris-health-ai/pull/16
- This report (raised via): https://github.com/harshit2005-rgb/aetheris-health-ai/pull/17
