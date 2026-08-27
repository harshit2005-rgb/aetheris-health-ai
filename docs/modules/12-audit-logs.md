# 12 — Audit Logs

**Owner:** TBD
**Phase:** MVP
**Status:** Approved

---

## 1. Purpose

Provide an immutable, searchable record of every significant action in the system. Foundation for compliance, investigation, and internal accountability. Not optional — this is the module that lets us look a regulator, a hospital admin, or a subpoena in the eye.

## 2. Scope

### In Scope

- Immutable audit entries for every mutating action across the platform
- Structured before/after state where relevant
- Actor identity (user / system / AI)
- Correlation with `request_id`
- Search and filter interface
- Export for compliance review

### Out of Scope

- Application logs (observability, not compliance)
- Anomaly detection → v3

## 3. Personas & Permissions

| Role | Can |
|---|---|
| Hospital Admin | Read all audit entries for their hospital |
| Super Admin | Read across hospitals |
| Compliance Officer (v2.3 role) | Read + export |
| Any user | No direct access |

## 4. Business Rules

1. Audit entries are **append-only**. `UPDATE` and `DELETE` are prohibited at the database level (revoked privileges on the audit user).
2. Entries include: actor, action, target, timestamp, IP, user-agent, request id.
3. Sensitive fields (password hashes, MFA secrets) are never included, even in "before" state.
4. Audit failure must not block business action, but is itself logged and paged.
5. Retention: 7 years default; configurable per hospital compliance policy.

## 5. Workflow

- Every service method that mutates data calls `AuditService.log(...)`.
- The audit call is inside the same transaction where possible (so a failed action rolls back its audit too).
- For cross-transaction concerns (long jobs), audit is written after commit with a saga-style compensation.

## 6. Functional Requirements

- FR-1: Immutable persistence.
- FR-2: Structured before/after (JSONB).
- FR-3: Full-text search across actions.
- FR-4: Filter by actor, target, action, date range.
- FR-5: Export as CSV / JSON.
- FR-6: Correlate with request id.

## 7. Non-Functional Requirements

- Audit write p95 < 20ms in the same transaction.
- Search p95 < 500ms with 10M entries per hospital.
- Zero data loss.

## 8. Database Design

Table `audit_logs` in `05-DATABASE_DESIGN.md`.

Additional DB privileges:

```sql
-- On the migration user, after audit_logs is created:
REVOKE UPDATE, DELETE ON audit_logs FROM aetheris_app;
GRANT INSERT, SELECT ON audit_logs TO aetheris_app;
```

Time-series partitioning by month (v2.2) for scale.

## 9. API Design

```
GET  /api/v1/audit-logs                # filters: actor_id, action, target_type, target_id, from, to, q
GET  /api/v1/audit-logs/{id}
GET  /api/v1/audit-logs/export?format=csv|json
```

## 10. Permissions

- `audit.read`
- `audit.export`

## 11. Validation Rules

- Query date range ≤ 1 year per call.
- Search text ≥ 3 chars.

## 12. UI Requirements

- Audit search page with structured filters.
- Detail view with before/after diff.
- Export button (async job for large exports; email link when ready).

## 13. AI Integration Points

- **v3:** anomaly detection over audit stream (flag unusual access patterns).
- For MVP, no AI in the audit read path.

## 14. Edge Cases

- Audit write fails but action succeeds → engineer paged; entry replayed from application log if possible.
- Backfilling historic audit (e.g. after a bug) → separate script with explicit `actor_type = 'system_backfill'`.

## 15. Cross-Module Dependencies

- Consumed by: every module (all call `AuditService.log(...)`).
- Depends on: request middleware (for request id, IP, user agent).

## 16. Testing Requirements

- Unit: log serialization.
- Repository: cannot UPDATE / DELETE (integration test proving privilege revocation).
- API: filters, permissions, export.

## 17. Acceptance Criteria

- AC-1: Every state-changing service method produces at least one audit entry.
- AC-2: No mechanism exists (short of DB superuser) to alter or delete an audit entry.
- AC-3: Admin can find "who edited patient X's phone number last month" in under 30 seconds.

## 18. Rollout Plan

- Ships with MVP.

## 19. Future Scope

- Immutable off-DB archival (write to WORM object storage)
- Merkle-tree tamper evidence (v2.2)
- Anomaly detection (v3)

## 20. Open Questions

- None.
