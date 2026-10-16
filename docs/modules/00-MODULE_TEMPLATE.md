# Module Template

Copy this file to create a new module spec. Fill every section. Do not skip sections; if genuinely N/A, write "N/A — because…". Empty sections rot into hidden assumptions.

---

# XX — <Module Name>

**Owner:** <Name>
**Phase:** MVP / v2.1 / v2.2 / v2.3 / Future
**Status:** Draft / In Review / Approved / In Development / Shipped
**Last updated:** YYYY-MM-DD

---

## 1. Purpose

One paragraph. What business problem does this module solve? Who benefits? Why is it in scope now?

## 2. Scope

### In Scope

- Bullet list of what this module owns
- Be precise

### Out of Scope

- Bullet list of what this module explicitly does NOT own
- Reference sibling modules that own the excluded area

## 3. Personas & Permissions

| Role | Can do | Cannot do |
|---|---|---|
| Role A | ... | ... |

## 4. Business Rules

Numbered list. Each rule is testable.

1. Business rule 1
2. Business rule 2

## 5. Workflow

Step by step. Include the happy path and at least the most important variations.

### 5.1 Happy path

1. Actor does X
2. System does Y
3. …

### 5.2 Alternative flows

- 5.2.1 Condition A → …
- 5.2.2 Condition B → …

## 6. Functional Requirements

Numbered, testable. Trace each to features from `02-FEATURES.md` where possible.

- FR-1: The system shall ...
- FR-2: The system shall ...

## 7. Non-Functional Requirements

- Performance: (latency budget)
- Reliability: (availability expectation)
- Security: (specific requirements)
- Observability: (what must be logged / measured)

## 8. Database Design

### 8.1 New tables

Follow conventions from `05-DATABASE_DESIGN.md`. UUID PKs, audit columns, soft delete, `hospital_id`.

### 8.2 Modified tables

### 8.3 Indexes

### 8.4 Constraints

## 9. API Design

For each endpoint:

- Method + path
- Purpose
- Required permission
- Request schema (Pydantic)
- Response schema
- Success + error responses
- Idempotency requirements

Follow `06-API_STANDARDS.md` for the envelope, pagination, error codes.

## 10. Permissions

New permissions this module introduces:

- `<module>.<action>` — description

## 11. Validation Rules

Field-level validation and cross-field rules.

## 12. UI Requirements

- List views, detail views, forms
- Empty states, loading states, error states
- Which shadcn components used
- Accessibility notes

## 13. AI Integration Points

Which AI capabilities this module uses, and how:

- Use case, prompt id, provider hint
- Which service methods AI can call as tools
- What data AI is allowed to see (scope)
- Safety considerations specific to this module

## 14. Edge Cases

Bullet list. Every "what if …" the team can think of.

## 15. Cross-Module Dependencies

- Depends on: <Module A> for X
- Provides to: <Module B> for Y

Cross-module traffic goes through service calls only, never repositories.

## 16. Testing Requirements

- Unit tests for every service method
- Repository tests for every non-trivial query
- API tests: happy path + 401 + 403 + 404 + 422 per endpoint
- Integration tests for critical flows
- AI eval tests where AI is invoked

## 17. Acceptance Criteria

Numbered list, each independently verifiable.

- AC-1: A receptionist can register a new patient in under 60 seconds
- AC-2: Duplicate MRN attempts are rejected with a clear error
- AC-…: …

## 18. Rollout Plan

- Feature flag name (if applicable)
- Migration approach
- Communication to pilots
- Rollback plan

## 19. Future Scope

- Numbered list of extensions this module explicitly anticipates
- Trace each to `14-ROADMAP.md` where appropriate

## 20. Open Questions

- Question, owner, deadline for resolution
- Once resolved, delete from here and update the relevant section

---

*The spec is the contract. Code follows spec. If reality demands a change, spec updates first.*
