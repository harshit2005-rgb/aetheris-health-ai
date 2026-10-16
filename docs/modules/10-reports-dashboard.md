# 10 — Reports & Dashboard

**Owner:** TBD
**Phase:** MVP
**Status:** Approved

---

## 1. Purpose

Turn the raw activity of the hospital into decision-ready information — for admins, doctors, receptionists, and billing staff. Provide dashboards for at-a-glance operational awareness and standard reports for period reviews.

## 2. Scope

### In Scope

- Role-specific dashboards (Admin, Doctor, Reception, Billing)
- Standard operational reports (patients registered, appointments booked/completed/cancelled, revenue, outstanding, dispensing volume, lab turnaround)
- Export to CSV and PDF
- AI-generated natural language summary of dashboards
- Ad-hoc AI-answered data questions (v2.1)
- Scheduled report email delivery (v2.1)

### Out of Scope

- Custom report builder → v3
- Cross-hospital consolidated reporting → v2.3
- BI tool integration (Metabase / Superset) → allowed for enterprise but not shipped as feature

## 3. Personas & Permissions

| Role | Sees |
|---|---|
| Hospital Admin | Everything hospital-wide |
| Doctor | Own patients, own schedule, own performance |
| Receptionist | Today's appointments, walk-in queue |
| Billing Staff | Revenue, outstanding, refunds |

## 4. Business Rules

1. Dashboards are per-role and per-hospital.
2. All aggregations respect soft delete and tenant filter.
3. Reports respect the requesting user's row-level access rules.
4. AI dashboard summary uses the same data the user is authorized to see; nothing more.
5. Exports include a header with hospital, timeframe, and generation timestamp.

## 5. Workflow

- User lands on the app → default dashboard for their primary role.
- Dashboard tiles fetch KPIs from Report service (Redis-cached where hot).
- User clicks a tile → drill down into filtered detail view.
- User asks "Explain this dashboard" → AI summary streams into a panel.

## 6. Functional Requirements

- FR-1: Admin dashboard: today's appointments, week revenue, month patient registrations, low-stock (v2.1), critical alerts.
- FR-2: Doctor dashboard: today's schedule, my patients count, pending consult notes, ai-summarized my week.
- FR-3: Reception dashboard: today's schedule, walk-in queue, no-show alerts.
- FR-4: Billing dashboard: unpaid invoices, revenue by day/week/month, discounts pending approval.
- FR-5: Export as CSV and PDF.
- FR-6: AI narrative summary of any dashboard.

## 7. Non-Functional Requirements

- Dashboard load p95 < 800ms (from Redis cache); cold p95 < 2s.
- Reports up to 10,000 rows generate under 5 seconds.
- Exports for larger sets stream via download endpoint with async generation (v2.1).

## 8. Database Design

No new business tables. Introduces a lightweight cache:

- Redis keys `report:{hospital_id}:{report_id}:{params_hash}` with TTL (default 60s for dashboards)
- Nightly precomputation for expensive aggregates (v2.1) stored in a `report_snapshots` table

## 9. API Design

```
GET  /api/v1/dashboards/admin
GET  /api/v1/dashboards/doctor
GET  /api/v1/dashboards/reception
GET  /api/v1/dashboards/billing
GET  /api/v1/reports/patients            # params: from, to, granularity
GET  /api/v1/reports/appointments
GET  /api/v1/reports/revenue
GET  /api/v1/reports/outstanding
GET  /api/v1/reports/{report_id}/export?format=csv|pdf
POST /api/v1/ai/dashboard-summary        # ai narrative
```

## 10. Permissions

- `report.admin.read`
- `report.doctor.read`
- `report.reception.read`
- `report.billing.read`
- `report.export`
- `report.ai_summary`

## 11. Validation Rules

- Date ranges: from ≤ to; max 12 months per query.
- Granularity ∈ {day, week, month}.

## 12. UI Requirements

- Dashboard grid with cards (Shadcn `Card`) and charts (Recharts).
- Filters bar (date range, department where relevant).
- AI Summary panel with streaming.
- Export button in each report view.
- Empty and loading states per tile.

## 13. AI Integration Points

- **Prompt:** `dashboard.summarize` — 3-4 sentences summarizing today's KPIs with tone appropriate for role.
- **Provider hint:** `fast`.
- **v2.1:** `report.qa` — natural language questions over hospital data; uses function calling into report service.
- **Safety:** AI never fabricates numbers; every number in a summary must appear in the source data.

## 14. Edge Cases

- Very new hospital with no data → dashboards show meaningful empty state with onboarding tips.
- Timezone: all aggregates in hospital timezone.
- Deleted patients/appointments filtered out of counts.

## 15. Cross-Module Dependencies

- Reads from: Patient, Appointment, Billing, Consultation, Pharmacy (v2.1), Lab (v2.1), Inventory (v2.2)
- Depends on: AI service.

## 16. Testing Requirements

- Unit: aggregation logic.
- Repository: complex queries with tenant filters.
- API: role-based visibility.
- AI eval: fabrication detection (no numbers in output that aren't in input).

## 17. Acceptance Criteria

- AC-1: Every role sees exactly the tiles their spec lists.
- AC-2: Dashboard renders in under 800ms on cache hit.
- AC-3: AI narrative summary never invents a KPI value.
- AC-4: Exports open cleanly in Excel and Adobe Reader.

## 18. Rollout Plan

- Ships with MVP.
- AI summary behind `feature.ai.dashboard_summary`.

## 19. Future Scope

- Custom report builder (v3)
- Cross-hospital consolidated view for Super Admin (v2.3)
- Scheduled email delivery (v2.1)

## 20. Open Questions

- None.
