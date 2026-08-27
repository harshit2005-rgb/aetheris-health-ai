# 11 — Testing Strategy

Aetheris ships critical healthcare workflows. Tests are not optional. This document defines what we test, how, and how much.

---

## 1. Test Pyramid

```
              /\
             /  \    E2E (few, expensive, high signal)
            /____\
           /      \
          /  API   \       API tests (moderate, per endpoint)
         /__________\
        /            \
       /  Integration \   Integration (moderate, real DB + Redis)
      /________________\
     /                  \
    /   Repository       \   Repository tests (real DB)
   /______________________\
  /                        \
 /    Unit / Services       \ Unit (many, fast, mocked)
/____________________________\
```

Also on the side, feeding into everything: **AI evaluation tests**.

## 2. Test Types

### 2.1 Unit Tests

- Target: services, utilities, AI service orchestration
- Dependencies mocked
- Fast (< 100ms each)
- Location: `app/tests/unit/`
- Rule: every service method has at least one unit test per business rule

Example:

```python
async def test_patient_service_rejects_duplicate_mrn():
    repo = AsyncMock()
    repo.find_by_mrn.return_value = FakePatient()
    service = PatientService(repo, AsyncMock())

    with pytest.raises(DuplicatePatientError):
        await service.create(PatientCreateFactory(), actor=FakeUser())
```

### 2.2 Repository Tests

- Target: repository classes
- Against a real PostgreSQL (Docker Compose service)
- Location: `app/tests/repository/`
- Rule: every non-trivial query has a test; simple `get_by_id` covered by API tests

### 2.3 API Tests

- Target: HTTP layer — routes, validation, permissions, response envelope
- FastAPI test client, real service and repository wired through DI
- Test DB seeded per test module
- Location: `app/tests/api/`
- Rule: every endpoint has at least these tests:
  - Happy path
  - Missing auth → 401
  - Wrong permission → 403
  - Not found → 404 (if applicable)
  - Validation error → 422

### 2.4 Integration Tests

- Target: cross-module flows
- Real DB, real Redis, mocked AI providers
- Location: `app/tests/integration/`
- Rule: every critical workflow has at least one integration test:
  - Login → book appointment → generate invoice → record payment
  - Register patient → book appointment → complete consultation → dispense prescription → deduct stock
  - Failed payment → invoice status unchanged
  - Appointment overlap → 409
  - AI summary streaming end to end

### 2.5 E2E Tests (Frontend + Backend)

- Playwright (v2.1)
- Small set of critical journeys, run nightly and pre-release
- Location: `frontend/tests/e2e/`
- Not on every PR (too slow)

### 2.6 AI Evaluation Tests

- Target: prompts, tool calls, output structure
- Golden sets per `(prompt_id, version)`
- Evaluators:
  - Structural (JSON schema conformance)
  - Content (key facts present, LLM-as-judge scoring)
  - Behavioral (tool calls made in the right order for a given scenario)
- Runs on prompt changes; blocks on regression
- Location: `app/tests/ai_eval/`

Example:

```python
@pytest.mark.parametrize("case", load_golden("patient.summarize", "1.2.0"))
async def test_patient_summarize_case(case):
    result = await ai_service.summarize_patient(case.patient, case.actor)
    assert has_bullet_points(result.text, min_count=4, max_count=6)
    assert mentions_all(result.text, case.expected_conditions)
    assert judge_faithfulness(result.text, case.patient) > 0.85
```

---

## 3. Coverage Targets

| Layer | Minimum | Target |
|---|---|---|
| Services | 80% | 90% |
| Repositories | 70% | 85% |
| API routes | 70% | 85% |
| Utilities | 90% | 95% |
| AI service orchestration | 70% | 85% |
| Overall | 70% | 80% |

Coverage is a floor, not a ceiling. Coverage does not equal correctness.

---

## 4. Test Data

### 4.1 Factories

Use `polyfactory` or hand-written factories in `app/tests/factories/`.

```python
class PatientFactory(ModelFactory[Patient]):
    __model__ = Patient
```

Never hand-roll patient JSON in tests. Never.

### 4.2 Fixtures

- `test_db` — ephemeral PostgreSQL, migrations applied
- `test_redis` — ephemeral Redis
- `authenticated_client(role)` — API client with a JWT for a user with the given role
- `hospital` — a base hospital fixture
- `patient`, `doctor`, `appointment` — chained fixtures for common shapes

Fixtures are in `app/tests/conftest.py`.

### 4.3 Isolation

Each test gets a transaction that rolls back on completion. Tests never depend on ordering. Parallelization is safe.

---

## 5. Mocking Rules

- **Mock external services** (AI providers, email, SMS)
- **Do not mock our own repositories in API tests** — that hides regressions
- **Do mock AI providers in integration tests** — deterministic, fast, cheap
- **Never mock in a way that hides real errors** (e.g. mocking an entire service to always succeed)

For AI providers, provide a `FakeAIProvider` that returns fixture responses keyed by prompt id.

---

## 6. Running Tests

```
make backend-test                    # all backend tests
make backend-test-unit               # unit only, fastest
make backend-test-cov                # with coverage report
make backend-test-integration        # integration only
make ai-eval PROMPT=patient.summarize
```

In CI: all tests except E2E on every PR; E2E and AI eval on the merge queue.

---

## 7. Continuous Integration

GitHub Actions pipeline per PR:

1. Lint (ruff, mypy, eslint, prettier)
2. Unit + repository + API tests (parallel matrix)
3. Integration tests (single job, real services in Docker)
4. Coverage check against thresholds
5. Docker image build (verify the image builds)
6. AI eval only if prompts changed
7. E2E only on merge to `main`

Fail-fast: no green build without every one of these passing.

---

## 8. Performance / Load Testing

- k6 or Locust scenarios for critical endpoints (v2.1)
- Baseline p50/p95/p99 tracked over releases
- Every release must not regress p95 by > 10% without justification

---

## 9. Security Testing

- Static analysis in CI (`bandit`, `semgrep` — v2.1)
- Dependency scanning on every PR (`pip-audit`, `pnpm audit`)
- Penetration testing before enterprise release (v2.3)
- Fuzz testing for API validation edge cases (v2.2)

---

## 10. Test Naming

- `test_<subject>_<condition>_<expected_result>`
- Good: `test_patient_service_rejects_duplicate_mrn`
- Bad: `test1`, `test_patient`, `test_it_works`

## 11. What Not to Test

- Framework code (FastAPI, SQLAlchemy)
- Third-party libraries
- Trivial getters/setters
- Configuration constants

## 12. Flaky Test Policy

- Flaky tests get quarantined immediately (`@pytest.mark.flaky`) and a ticket opened
- Quarantined tests must be fixed within 2 weeks or deleted
- No test tolerates `time.sleep()` — use event-based waits

## 13. Test Documentation

Every non-obvious test setup block gets a comment. Every parametrized case gets a readable id:

```python
@pytest.mark.parametrize(
    "role,expected_status",
    [
        ("doctor", 200),
        ("receptionist", 403),
        ("patient", 403),
    ],
    ids=["doctor_ok", "receptionist_forbidden", "patient_forbidden"],
)
```

## 14. Reviewing Tests

Test code gets reviewed with the same rigor as production code. A PR with poor tests fails review even if the feature is correct. Tests are how we prove correctness holds tomorrow.
