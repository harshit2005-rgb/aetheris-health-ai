# 05 — Appointment Management

**Owner:** TBD
**Phase:** MVP
**Status:** Approved

---

## 1. Purpose

Coordinate the meeting between patient and doctor. Own the appointment lifecycle from booking through completion, including walk-ins, cancellations, and no-shows. Provide the schedule the entire clinic runs on for the day.

## 2. Scope

### In Scope

- Book / reschedule / cancel appointments
- Walk-in queue
- Appointment status lifecycle: booked → checked-in → in-progress → completed → no-show / cancelled
- Doctor calendar view
- Reception dashboard for the day
- AI slot recommendation
- AI-generated reminder text
- Immutable status history

### Out of Scope

- Clinical notes → Consultation
- Fees / invoicing → Billing (created at completion)
- Notifications delivery → Notification service
- Slot computation → Doctor Management

## 3. Personas & Permissions

| Role | Can do |
|---|---|
| Receptionist | Book, reschedule, cancel, check in, no-show, view schedule |
| Doctor | View own schedule, start / complete own appointments |
| Nurse | View schedule, check in patients |
| Hospital Admin | All operations |
| Patient (portal, future) | View own appointments, request reschedule |

## 4. Business Rules

1. An appointment must reference a valid patient and doctor in the same hospital.
2. `scheduled_start < scheduled_end`; duration must match a doctor's slot duration.
3. Two appointments cannot overlap for the same doctor (unless both are walk-in and admin overrides).
4. Booking outside doctor availability requires `appointment.book_override` permission.
5. A cancelled appointment cannot be reactivated; book a new one instead.
6. Status transitions follow the state machine (Section 5.1); invalid transitions return 400.
7. Every status change writes to `appointment_status_history`.
8. Idempotency key required on `POST /appointments` to prevent double-book on client retry.
9. A completed appointment cannot be edited except to append clinical notes (owned by Consultation).

## 5. Workflow

### 5.1 State Machine

```
             ┌─────────┐
   book    → │ booked  │ ─ cancel → cancelled
             └────┬────┘
                  │ check-in
                  ▼
             ┌──────────┐
             │checked_in│ ─ cancel → cancelled
             └────┬─────┘
                  │ start
                  ▼
             ┌──────────┐
             │in_progress│
             └────┬─────┘
                  │ complete
                  ▼
             ┌──────────┐
             │ completed│
             └──────────┘

Any state other than completed / cancelled can transition to no_show if scheduled_end passes without check-in.
```

### 5.2 Book (happy path)

1. Reception picks patient + doctor + date.
2. Client calls `GET /doctors/{id}/slots?date=...` to get available slots.
3. Reception picks a slot (or requests AI recommendation).
4. `POST /appointments` with `Idempotency-Key`.
5. Service checks: patient exists, doctor available, no overlap, slot inside availability (unless override).
6. Transaction: insert appointment + insert status history row.
7. Notification: appointment confirmation.
8. Audit: `appointment.booked`.

### 5.3 Reschedule

1. `PATCH /appointments/{id}` with new `scheduled_start` / `scheduled_end`.
2. Only allowed while status = `booked`.
3. Same validation as booking.
4. Notification of the change.
5. Audit + status history entry (`booked → booked` with `reason = 'reschedule'`).

### 5.4 Cancel

1. `POST /appointments/{id}/cancel` with `reason`.
2. Allowed from `booked` or `checked_in`.
3. Sets `cancelled_reason`, updates status.
4. Notification.
5. Audit.

### 5.5 Check-in

1. `POST /appointments/{id}/check-in`.
2. Requires status = `booked`.
3. Sets `checked_in_at`.

### 5.6 Start & complete

1. Doctor `POST /appointments/{id}/start` when ready.
2. Status → `in_progress`, `started_at` set.
3. Doctor completes consultation (Consultation module).
4. Doctor `POST /appointments/{id}/complete`.
5. Status → `completed`, `completed_at` set.
6. Trigger: Billing invoice draft creation via BillingService.
7. Audit.

### 5.7 No-show sweeper

- Background job runs every 5 minutes.
- For appointments with status ∈ {booked, checked_in} and `scheduled_end < now() - grace_period`, mark `no_show`.
- Grace period per hospital setting (default 30 minutes).

### 5.8 Walk-in

1. Reception `POST /appointments` with `type = 'walk_in'`.
2. Service assigns next available slot for the requested doctor.
3. If no slot in next X minutes, response asks for override / queue.
4. Queue view shows walk-ins ordered by arrival time.

### 5.9 AI slot recommendation

1. Reception clicks "AI Suggest" during booking.
2. Client calls `POST /appointments/recommend-slot` with `{ patient_id, urgency, preferred_window, doctor_id? }`.
3. AI service considers doctor load, urgency, patient history; returns ranked slots with rationale.
4. Reception picks one and books normally.

## 6. Functional Requirements

- FR-1: The system shall book appointments with a state-machine-controlled lifecycle.
- FR-2: The system shall prevent double-booking for the same doctor.
- FR-3: The system shall support walk-in appointments.
- FR-4: The system shall support cancellation, reschedule, check-in, start, complete transitions.
- FR-5: The system shall generate an immutable status history.
- FR-6: The system shall provide AI-assisted slot recommendation.
- FR-7: The system shall auto-mark no-shows via a background job.
- FR-8: The system shall enforce idempotency on booking.

## 7. Non-Functional Requirements

- Booking p95 < 500ms.
- Slot recommendation p95 < 2s (AI).
- No-show sweeper cannot lag more than 10 minutes behind real time.

## 8. Database Design

Tables `appointments`, `appointment_status_history` in `05-DATABASE_DESIGN.md`.

Constraint (deferred to Postgres `EXCLUDE` in migration):

```sql
ALTER TABLE appointments
ADD CONSTRAINT no_overlap_per_doctor
EXCLUDE USING gist (
  doctor_id WITH =,
  tstzrange(scheduled_start, scheduled_end, '[)') WITH &&
) WHERE (deleted_at IS NULL AND status NOT IN ('cancelled', 'no_show'));
```

Indexes:
- `ix_appointments_hospital_scheduled_start (hospital_id, scheduled_start)`
- `ix_appointments_doctor_scheduled_start (doctor_id, scheduled_start)`
- `ix_appointments_patient_scheduled_start (patient_id, scheduled_start DESC)`
- `ix_appointments_status (hospital_id, status)`

## 9. API Design

```
GET    /api/v1/appointments                # filters: patient_id, doctor_id, date, status, type
POST   /api/v1/appointments                # Idempotency-Key required
GET    /api/v1/appointments/{id}
PATCH  /api/v1/appointments/{id}           # reschedule only
POST   /api/v1/appointments/{id}/check-in
POST   /api/v1/appointments/{id}/start
POST   /api/v1/appointments/{id}/complete
POST   /api/v1/appointments/{id}/cancel
POST   /api/v1/appointments/{id}/no-show
GET    /api/v1/appointments/{id}/status-history
POST   /api/v1/appointments/recommend-slot   # AI
GET    /api/v1/appointments/queue?doctor_id  # walk-in queue view
```

**Request example — POST /appointments:**

```json
{
  "patient_id": "...",
  "doctor_id": "...",
  "scheduled_start": "2026-08-15T09:15:00+05:30",
  "scheduled_end": "2026-08-15T09:30:00+05:30",
  "type": "new",
  "reason": "Persistent cough for 5 days",
  "notes": "Prefers morning slots"
}
```

## 10. Permissions

- `appointment.read`
- `appointment.read.own` (doctor's own schedule)
- `appointment.book`
- `appointment.reschedule`
- `appointment.cancel`
- `appointment.check_in`
- `appointment.start`
- `appointment.complete`
- `appointment.book_override` (bypass availability constraint)
- `appointment.recommend_slot`

## 11. Validation Rules

- `scheduled_start` in the future (or within a 15-minute grace for walk-in).
- Duration in {10, 15, 20, 30, 45, 60} minutes.
- Type ∈ {new, follow_up, walk_in, emergency}.
- Reason ≤ 500 chars.
- Cancellation reason required.

## 12. UI Requirements

- Reception dashboard: today's schedule as a timeline; walk-in queue side panel; drag to reschedule (v2.1).
- Booking modal: patient search → doctor pick → date/slot → confirm.
- Doctor calendar: day / week views with color-coded status.
- Slot suggestion drawer with AI-ranked options.
- Status pill with clear color coding across the app.

## 13. AI Integration Points

- **Prompt:** `appointment.recommend_slot`
- **Provider hint:** `fast`
- **Data scope:** doctor availability, doctor load next 7 days, patient's past appointment cadence, urgency
- **Tools available:** `list_doctor_slots(date_range)`, `list_appointments_by_doctor(date_range)`
- **Output shape:** function call returning `[{slot_start, slot_end, score, reason}]`
- **Safety:** the model can only recommend; the reception clicks book

Future (v2.1):
- `appointment.reminder_text` — draft the reminder message to the patient in their preferred language.

## 14. Edge Cases

- Simultaneous booking of the same slot from two receptionists → one wins on DB constraint; the loser gets 409 with a fresh slot fetch suggestion.
- Doctor deletes availability with existing bookings → doctors module blocks that; users must reassign appointments first.
- Booking at 23:59 with a duration crossing midnight → allowed; timezone-aware.
- Reschedule to a slot that's now unavailable → 409.
- Complete without check-in? Allowed for doctor discretion, but audit records skipped states.
- Cancellation window (e.g. no cancel within 1 hour) is v2.1; MVP allows any time before start.

## 15. Cross-Module Dependencies

- Depends on: Patient (patient reference), Doctor (availability, slot generation), Notification (confirmations, reminders), Audit, AI service.
- Provides to: Consultation (an appointment is the container for a visit), Billing (invoice drafted on complete).

## 16. Testing Requirements

- Unit: state machine transitions, idempotency, no-overlap logic.
- Repository: overlap constraint, state history queries.
- API: all endpoints × status × permission combinations.
- Integration: full booking → complete → invoice draft.
- Load: 100 concurrent bookings; overlap constraint holds.

## 17. Acceptance Criteria

- AC-1: A receptionist can book an appointment in under 30 seconds.
- AC-2: Double-booking is prevented at the database level.
- AC-3: The status of an appointment can only follow the defined state machine.
- AC-4: An AI slot recommendation returns 3 ranked options in under 2 seconds.
- AC-5: A no-show sweeper marks appointments correctly within 10 minutes of the grace window.
- AC-6: Every state change writes a history row.

## 18. Rollout Plan

- Ships with MVP.
- AI slot recommendation behind `feature.ai.slot_recommendation` flag.

## 19. Future Scope

- Recurring appointments (v2.1)
- Wait-list & auto-fill on cancellations (v2.1)
- Drag-to-reschedule on the calendar UI (v2.1)
- Video consultation booking (v3)
- Multi-doctor visits (team-based) (v2.2)

## 20. Open Questions

- Grace period for no-show — is 30 minutes reasonable across all pilot hospitals? Confirm with pilot 1 during onboarding.
