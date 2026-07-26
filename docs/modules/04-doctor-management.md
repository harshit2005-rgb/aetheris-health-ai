# 04 — Doctor Management

**Owner:** TBD
**Phase:** MVP
**Status:** Approved

---

## 1. Purpose

Manage doctor-specific data — profile, specialization, availability, leaves, and consultation fees — that the appointment and billing modules depend on.

## 2. Scope

### In Scope

- Doctor profile linked to a User account
- Specialization, qualifications, license number
- Weekly availability schedule
- Time-off / leave entries
- Consultation fee configuration
- Computed available slots (given availability + leaves + existing appointments)

### Out of Scope

- Login / credentials → Authentication
- General user profile fields → User Management
- Actual appointment booking → Appointment Management
- Performance analytics → Reports

## 3. Personas & Permissions

| Role | Can do |
|---|---|
| Hospital Admin | Full CRUD on doctors, availability, leaves, fees |
| Doctor | View + edit own availability, own leave requests (approval workflow v2.1 → auto-approved MVP) |
| Receptionist | View doctor list, view availability, view computed slots |
| Anyone with `doctor.read` | View doctor list |

## 4. Business Rules

1. A doctor row references exactly one user row (`user_id UNIQUE`).
2. Availability is a set of `(day_of_week, start_time, end_time, slot_duration_minutes)` entries.
3. Leaves are `(starts_at, ends_at, reason)` intervals; a slot falling within a leave is unavailable.
4. Slot generation: within each availability window, generate slots at `slot_duration_minutes` intervals; subtract leaves and booked appointments.
5. Slot generation is a **read model** — never stored; recomputed on demand.
6. Consultation fee is per-doctor, per-hospital, currency inherited from hospital settings.
7. A doctor cannot be deleted while active appointments exist; must first cancel or reassign appointments.

## 5. Workflow

### 5.1 Onboard doctor

1. Admin invites user with role `doctor` (User Management).
2. Admin creates doctor row via `POST /doctors` linking the user, setting specialization, license, fee.
3. Doctor logs in, completes profile, sets availability.

### 5.2 Set availability

1. Doctor / admin `PUT /doctors/{id}/availability` with array of weekly slots.
2. Service validates no overlapping intervals within the same day.
3. Persists availability, clearing old rows atomically.

### 5.3 Request leave

1. Doctor `POST /doctors/{id}/leaves` with start / end / reason.
2. MVP: auto-approved.
3. Service checks for existing appointments during the leave; if any, response includes them for reassignment.
4. Notification to admin.

### 5.4 Compute slots

1. Reception / patient calls `GET /doctors/{id}/slots?date=YYYY-MM-DD`.
2. Service returns array of slots with status `available` / `booked` / `on_leave`.

## 6. Functional Requirements

- FR-1: The system shall link a doctor row to exactly one user.
- FR-2: The system shall store weekly availability with configurable slot duration.
- FR-3: The system shall support leaves.
- FR-4: The system shall compute available slots on demand.
- FR-5: The system shall prevent deletion of doctors with active future appointments.

## 7. Non-Functional Requirements

- Slot computation p95 < 300ms for a single day.
- Availability update p95 < 500ms.

## 8. Database Design

Tables `doctors`, `doctor_availability`, `doctor_leaves` defined in `05-DATABASE_DESIGN.md`.

Indexes:
- `ix_doctor_avail_doctor_day (doctor_id, day_of_week)`
- `ix_doctor_leaves_doctor_range (doctor_id, starts_at, ends_at)`

## 9. API Design

```
GET    /api/v1/doctors                    # filters: specialization, department, q
POST   /api/v1/doctors
GET    /api/v1/doctors/{id}
PATCH  /api/v1/doctors/{id}
DELETE /api/v1/doctors/{id}
GET    /api/v1/doctors/{id}/availability
PUT    /api/v1/doctors/{id}/availability
GET    /api/v1/doctors/{id}/leaves
POST   /api/v1/doctors/{id}/leaves
DELETE /api/v1/doctors/{id}/leaves/{leave_id}
GET    /api/v1/doctors/{id}/slots?date=YYYY-MM-DD
```

**Slot response example:**

```json
{
  "success": true,
  "data": {
    "date": "2026-08-15",
    "doctor_id": "...",
    "slots": [
      {"start": "2026-08-15T09:00:00+05:30", "end": "2026-08-15T09:15:00+05:30", "status": "available"},
      {"start": "2026-08-15T09:15:00+05:30", "end": "2026-08-15T09:30:00+05:30", "status": "booked", "appointment_id": "..."},
      {"start": "2026-08-15T09:30:00+05:30", "end": "2026-08-15T09:45:00+05:30", "status": "on_leave"}
    ]
  }
}
```

## 10. Permissions

- `doctor.read`
- `doctor.create`
- `doctor.update`
- `doctor.delete`
- `doctor.availability.read`
- `doctor.availability.update`
- `doctor.leave.create`
- `doctor.leave.delete`

## 11. Validation Rules

- `day_of_week` ∈ [0, 6].
- `start_time < end_time`.
- No overlapping availability entries per day.
- Slot duration ∈ {10, 15, 20, 30, 45, 60} minutes.
- License number: 1–50 chars, non-empty.
- Consultation fee: ≥ 0, ≤ 999,999.99.
- Leave `ends_at > starts_at`.

## 12. UI Requirements

- Doctor list: cards or table with specialization, availability preview.
- Doctor detail: profile tab, availability tab (weekly grid editor), leaves tab.
- Weekly availability editor: drag-to-select on a grid, shadcn `Calendar` + custom overlay.
- Slot viewer for reception: date picker + horizontal slot strip.

## 13. AI Integration Points

- v2.1: `doctor.availability.suggest` — given historical booking density, suggest availability changes.
- v2.2: `doctor.match` — recommend the best doctor for a new patient based on symptoms + doctor specialization (with human confirmation).

## 14. Edge Cases

- DST transitions (rare in India but universal): availability defined in wall-clock; slot generation resolves in hospital timezone; test with a hospital in Europe/London.
- Overlapping availability entries → validation error.
- Deleting a doctor with future appointments → 409 with list of affected appointments and required action.
- Leave overlaps existing leave → merged into a single leave (v2.1) or rejected (MVP).

## 15. Cross-Module Dependencies

- Depends on: User Management.
- Provides to: Appointment (availability + slot computation), Billing (consultation fee), Consultation (owner of visit).

## 16. Testing Requirements

- Unit: slot generation algorithm — availability + leaves + bookings.
- Repository: overlap detection query.
- API: full CRUD; slot endpoint with a variety of scenarios.
- Integration: doctor onboard → set availability → receive appointment → slot marked booked.

## 17. Acceptance Criteria

- AC-1: A doctor can set availability across all seven days.
- AC-2: Booked slots and leave windows show correctly in the slot endpoint.
- AC-3: A doctor cannot be deleted if future appointments exist.
- AC-4: Slot computation for a single day returns within 300ms for 1000 doctors in the hospital.

## 18. Rollout Plan

- Ships with MVP.

## 19. Future Scope

- Multi-hospital doctor affiliation (v3)
- Doctor performance metrics (v2.1)
- AI-suggested availability optimization (v2.1)
- Shift-based (non-weekly) schedules for hospitalists (v2.2)

## 20. Open Questions

- None.
