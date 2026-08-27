# End-to-End Workflows

**Owner: QA Lead. Read by: everyone.**

Modules that pass their own tests can still fail when composed. Aetheris runs on multi-module workflows — a patient visit touches Patient, Doctor, Appointment, Billing, and Notifications. This document defines the workflows that must pass **end-to-end** before each release milestone.

Modules ship when their unit tests pass. **The product ships when these workflows pass.**

---

## Why Workflows Over Modules

- Real users don't use modules — they complete tasks.
- Integration bugs live between modules, not inside them.
- A workflow test catches issues that only appear in specific sequences (permission changes mid-flow, notifications not firing, audit gaps).
- Workflows are the demo material. If they work, you can sell the product.

---

## Workflow 1 — Patient Journey (Full Visit)

**Blocks release at:** Release Candidate
**Sprints:** partial in 3, extended in 6, completed in 7
**Actors:** Reception, Patient, Doctor, Billing Staff

### Steps

1. **Registration** — Reception registers a new patient. MRN is auto-generated per hospital pattern.
2. **Appointment booking** — Reception books an appointment with Dr. X for tomorrow at 10:00 AM.
3. **Notification** — Patient receives appointment confirmation (in-app for staff, email for patient).
4. **Arrival** — Next day, patient arrives. Reception marks status = "checked in."
5. **Consultation** — Doctor opens the appointment, sees patient history summary (AI-generated), records clinical notes, adds prescription.
6. **Closeout** — Doctor marks appointment "completed." Consultation fee automatically queued to billing.
7. **Invoice generation** — Billing staff opens the patient's queued items, generates invoice (consultation fee + any add-on services), reviews.
8. **Payment** — Patient pays via cash or card. Payment recorded, invoice marked "paid."
9. **Receipt** — Receipt PDF generated, emailed to patient, filed in patient record.
10. **Audit** — Every step above appears in the audit log with actor + timestamp + IP.

### Success Criteria

- No manual data re-entry between steps (data flows through modules)
- Total workflow completable in **< 5 minutes** with practiced staff
- Zero cross-tenant data leaks (verified by parallel test with second hospital)
- All notifications delivered at the 3 defined points (confirmation, check-in reminder, receipt)
- Full audit trail reconstructible
- Invoice number is sequential and gap-free with concurrent bookings
- Payment recording is idempotent (double-click on "Confirm Payment" doesn't create two payments)

### Failure Modes to Test

- Doctor is on leave when appointment date arrives (should not have been bookable)
- Patient doesn't show up (system marks no-show, notifies reception)
- Payment fails mid-flow (invoice stays open, no partial charge recorded)
- Reception closes browser after step 2 — reopens; appointment still visible
- Two receptionists try to book same slot — one succeeds, one gets clear error

---

## Workflow 2 — Doctor Journey

**Blocks release at:** Beta
**Sprints:** partial in 4, completed in 5
**Actors:** Doctor

### Steps

1. **Login** — Doctor logs in with MFA.
2. **Schedule view** — Sees today's appointments in a calendar view, sorted by time.
3. **Patient prep** — Clicks on the 10:00 AM slot, opens patient record.
4. **History review** — Reads AI-generated patient history summary; expands sections for details.
5. **Consultation start** — Marks appointment "in progress."
6. **Notes** — Types clinical notes; system auto-saves every 30 seconds.
7. **Prescription** — Adds prescription with medicine, dosage, duration.
8. **Test orders** (v2.1 dependency; skip for v2.0) — Would order lab tests here.
9. **Closeout** — Marks appointment "completed." Session ends.
10. **Next patient** — Returns to schedule view; next patient highlighted.

### Success Criteria

- Doctor never has to re-authenticate mid-day
- Schedule view refreshes automatically as new bookings come in
- Auto-save survives browser crash (recovered on relogin)
- Prescription writes to structured field (not free-text)
- Notes are visible immediately in the audit log
- Doctor cannot view a patient outside their hospital

### Failure Modes to Test

- Doctor's session token expires mid-consultation → silent refresh, no data loss
- Patient record already open on another tab → conflict warning, not overwrite
- Doctor tries to close an appointment without notes → soft warning ("no notes recorded, confirm?")

---

## Workflow 3 — Admin Journey (Hospital Setup)

**Blocks release at:** Alpha
**Sprints:** completed in 2
**Actors:** Superadmin, Hospital Admin

### Steps

1. **Provision hospital** — Superadmin provisions a new hospital (name, slug, timezone, currency, admin email).
2. **Invite admin** — System sends invitation email; Hospital Admin sets password.
3. **First login** — Hospital Admin logs in, lands on Admin Dashboard.
4. **Settings** — Configures address, contact, working hours, tax config, MRN pattern, invoice number pattern.
5. **Branding** — Uploads logo, sets primary color, drafts letterhead.
6. **User creation** — Invites doctors, receptionists, billing staff with appropriate roles.
7. **Verification** — Each invitee logs in; sees role-appropriate dashboard.
8. **Reports check** — Admin opens the Reports section, sees empty state gracefully (no data yet).

### Success Criteria

- New hospital provisioning is a single transaction (rollback on any failure)
- Invited users receive email within 60 seconds
- Password reset link works and expires per policy
- Every role sees only its own dashboard (no leakage across roles)
- Empty states are informative, not broken-looking
- All configuration changes appear in `hospital_settings_history`

### Failure Modes to Test

- Superadmin cancels provisioning mid-flow → no orphan records
- Two admins try to change the same setting simultaneously → last-write-wins with etag warning
- Deactivated hospital's users are logged out on next request

---

## Workflow 4 — Reception Journey (Walk-in)

**Blocks release at:** Release Candidate
**Sprints:** completed in 5 (booking) + 6 (payment)
**Actors:** Reception, Patient

### Steps

1. **Walk-in arrives** — Reception clicks "Walk-in Registration."
2. **Quick registration** — Enters minimum viable fields (name, phone, DOB, gender). MRN generated.
3. **Available doctor lookup** — System shows which doctors are available right now with wait times.
4. **Immediate slot** — Reception picks a doctor; system creates an "immediate" appointment (status = in-progress).
5. **Payment collection** — For hospitals that charge upfront: Reception generates invoice for consultation fee, collects payment, marks paid.
6. **Handoff** — Patient sent to doctor's room; doctor sees new appointment in queue.

### Success Criteria

- Full walk-in flow completable in **< 90 seconds**
- Optional fields don't block registration
- Doctor availability is real-time (accounts for current in-progress appointment)
- Upfront payment is optional per hospital configuration (feature flag)
- Doctor receives a notification of the new walk-in in queue

### Failure Modes to Test

- Two receptions try to hand off to the same doctor at the same second → both succeed (queue handles ordering)
- Patient with existing MRN mistakenly registered as new → system suggests matching patient before creating duplicate
- Reception cancels flow after registration but before appointment → patient record exists, no appointment orphan

---

## Testing Cadence

| Release | Required workflows |
|---------|-------------------|
| Alpha (Sep 6) | Workflow 3 (Admin) |
| Beta (Oct 18) | Workflows 2 (Doctor) + 3 (Admin); Workflow 1 partial (Registration + Appointment only) |
| Release Candidate (Nov 30) | **All 4 workflows** end-to-end + AI-augmented paths |
| Every sprint | Manual walkthrough of at-least-once-implemented workflows |

---

## Test Automation

- **Playwright** for browser-driven E2E tests (frontend + backend integration)
- **pytest** for API-only E2E flows (skips UI, tests service composition)
- **Load-test harness** (k6 or Locust) that runs the workflows at concurrency

### CI/CD Wiring

- Every PR to `main` runs the E2E test set for **currently-implemented workflow stages**
- Nightly build runs the full workflow suite against staging
- Every sprint review includes a **live manual walkthrough** of the workflow(s) that sprint delivered
- Failed workflow test blocks merge (no override)

### Test Data

- Each E2E test provisions its own hospital (isolation)
- Test data is idempotent (can re-run without cleanup)
- Golden datasets kept for regression testing
- AI eval scenarios versioned in `tests/ai_eval/`

---

## AI-Augmented Workflow Paths

For the Release Candidate, workflows must also pass when the user leans on AI:

- **Patient Journey with AI:** Doctor asks the AI to summarize this patient's last 3 visits — AI returns correct summary sourced from actual records.
- **Reception walk-in with AI:** Reception asks "which doctor is free right now?" — AI queries doctor availability via function calling, returns list.
- **Billing with AI:** Billing staff asks "why is this invoice ₹500 higher than the estimate?" — AI compares line items and estimate, explains the difference.
- **Reports with AI:** Admin asks "how was this week compared to last week?" — AI queries the analytics endpoints, produces narrative summary with correct numbers (no fabrication).

Each AI-augmented path has an accompanying eval test in `tests/ai_eval/`.

---

## Escalation

If an E2E workflow test fails and blocks a release, the priority is:

1. Fix the workflow (if the bug is in code)
2. If the workflow itself is wrong (spec changed), update this doc first, then the test, then the code
3. If neither can be resolved by the release date, the release doesn't ship

**Workflows are non-negotiable.** They exist because a broken workflow = a broken product regardless of how many unit tests pass.

---

## Change Log

| Date | Change | Approved by |
|------|--------|-------------|
| 2026-07-26 | Initial workflow definitions for v2.0 | Sanjeev, co-founders |
