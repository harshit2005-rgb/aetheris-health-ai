# 18 — Frontend API Contract Reference

The exact request/response contracts for the endpoints the frontend consumes today:
**Patients, Departments, Doctors, Appointments, Billing, Notifications, Laboratory, Pharmacy, Inventory**. Written so a frontend module
can be built without reading backend code or guessing a shape.

**Source of truth.** Every contract below was read out of the implementation, not the
design docs — routers in `backend/app/api/v1/`, DTOs in `backend/app/schemas/`, and the
assertions in `backend/app/tests/`. Where a design doc and the code disagreed, the code
won and the disagreement is called out. Conventions come from
[06-API_STANDARDS.md](06-API_STANDARDS.md); this document does not restate them, it
records what is actually wired.

Anything not listed here is not available yet. Do not build against it.

---

## 1. Conventions

### 1.1 Base URL

```
/api/v1
```

The frontend Axios instance already defaults to `/api/v1` (`frontend/src/lib/api.ts`);
in dev the Vite proxy forwards `/api` to the backend.

### 1.2 Response envelope

Every response — success or failure — is wrapped. Single resource:

```json
{
  "success": true,
  "message": "Patient retrieved.",
  "data": { "...": "..." },
  "metadata": null
}
```

> **`metadata` is `null` on single-resource successes.** [06-API_STANDARDS.md](06-API_STANDARDS.md)
> §5.1 shows `metadata.request_id` on every response, but only the error handlers
> and the list routers actually build a metadata block. On a success the
> correlation id comes back in the **`X-Request-ID` response header** instead, and
> list responses carry `metadata.pagination` with `request_id` still null. Do not
> dereference `metadata.request_id` on a success path. This is a doc-vs-code
> divergence, pinned by a test (`test_metadata_is_null_on_a_single_resource_success`)
> and raised with the team — until it is settled, the behaviour above is what ships.

List:

```json
{
  "success": true,
  "message": "Patients retrieved.",
  "data": [ { "...": "..." } ],
  "metadata": {
    "request_id": null,
    "pagination": { "page": 1, "page_size": 25, "total_records": 137, "total_pages": 6 }
  }
}
```

Failure — the fields are **flat**, there is no nested `error` object:

```json
{
  "success": false,
  "message": "Validation failed.",
  "errors": [ { "field": "date_of_birth", "message": "Cannot be in the future" } ],
  "error_code": "VALIDATION_ERROR",
  "metadata": { "request_id": "b6e2..." }
}
```

`frontend/src/api/http.ts` already unwraps `data` and maps `metadata.pagination` into
camelCase. Keep using it — components should never see the envelope.

### 1.3 Error codes

From `backend/app/core/error_codes.py`:

| `error_code` | HTTP | When you will hit it |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Pydantic rejected the body or a query param |
| `AUTHENTICATION_REQUIRED` | 401 | Missing/expired access token |
| `PERMISSION_DENIED` | 403 | Authenticated, but the role lacks the permission |
| `RESOURCE_NOT_FOUND` | 404 | Wrong id, or the row belongs to another hospital |
| `RESOURCE_CONFLICT` | 409 | Duplicate MRN/code/licence, or a double-booked slot |
| `BUSINESS_RULE_VIOLATION` | 400 | Illegal state transition, already-deactivated record |
| `RATE_LIMITED` | 429 | 300 req/min per user, 1000/min per hospital |

A 404 is deliberately returned for a record in another tenant. Do not treat it as a bug.

### 1.4 Authentication

`Authorization: Bearer <access_token>` on **every** endpoint in this document. There are
no public patient/doctor/appointment endpoints.

**Both tokens travel in JSON bodies — there is no cookie.** The backend never sets one.

- `POST /api/v1/auth/login` returns `{ access_token, refresh_token, expires_in, user }`.
- `POST /api/v1/auth/refresh` takes `{ "refresh_token": "…" }` and returns
  `{ access_token, refresh_token, expires_in }` — no `user`.
- The access token lives 15 minutes (`expires_in: 900`); the refresh token 7 days.

Keep both **in memory only** (`frontend/src/services/tokenStore.ts`), never in
`localStorage` or `sessionStorage`. A page reload therefore drops the session and lands
on `/login` — that is expected, not a bug.

**Refresh tokens rotate, and reuse is treated as theft.** Every successful refresh
returns a *new* refresh token and revokes the old one. Presenting an already-used refresh
token revokes **all of that user's sessions** and returns `401` ("All sessions
invalidated"). The practical consequence: never run two refreshes at once with the same
token. `frontend/src/lib/api.ts` already guards this — concurrent `401`s share a single
in-flight refresh, the original request is retried once with the new token, and if the
refresh itself fails the session is cleared and route guards send the user to `/login`.
Keep that shape if you touch it, and give any second client the same single-flight guard.

> **Diverges from `CLAUDE.md`,** which specifies the refresh token as an HTTP-only cookie.
> That is the intended design; what ships is the body-based flow above. See §13.

### 1.5 Tenancy

`hospital_id` is taken from the authenticated user's token. It is never a query param and
never accepted in a body. A Super Admin (no hospital) gets `400 BUSINESS_RULE_VIOLATION`
on these endpoints — that is intentional, not a bug: cross-tenant reads are a separate
audited capability. Log in as a hospital-scoped user.

### 1.6 Pagination

`?page=1&page_size=25`. `page` ≥ 1, `page_size` 1–100 (default 25). Out-of-range values
are a `422`, not a clamp. Counts come back in `metadata.pagination`.

### 1.7 Time

All datetimes on the wire are ISO 8601 **with an offset**, stored UTC. A naive datetime
is rejected. `date` fields (`date_of_birth`, `?date=`) are plain `YYYY-MM-DD`.

Doctor availability is the one exception: it is *wall-clock* in the hospital's timezone
(`Asia/Kolkata` for the demo hospital), because a clinic that opens at 09:00 opens at
09:00 either side of a DST change.

### 1.8 Sorting

**No endpoint in this document accepts a `sort` parameter.** Order is fixed per resource
and documented below. `06-API_STANDARDS.md` §11 describes a `?sort=` convention — it is
not implemented for these resources. Sort client-side within a page, or ask before
building UI that needs server-side sort.

### 1.9 Roles → permissions

Which seeded role can call what. Relevant subset only:

| Permission | Hospital Admin | Doctor | Nurse | Receptionist |
|---|:--:|:--:|:--:|:--:|
| `patient.read` | ✅ | ✅ | ✅ | ✅ |
| `patient.create` | ✅ | ✅ | — | ✅ |
| `patient.update` | ✅ | ✅ | ✅ | — |
| `patient.delete` | ✅ | — | — | — |
| `department.read` | ✅ | ✅ | ✅ | ✅ |
| `department.create/update/delete` | ✅ | — | — | — |
| `doctor.read` | ✅ | ✅ | ✅ | ✅ |
| `doctor.create/update/delete` | ✅ | — | — | — |
| `doctor.availability.read` | ✅ | ✅ | ✅ | ✅ |
| `doctor.availability.update` | ✅ | ✅ | — | — |
| `doctor.leave.create/delete` | ✅ | ✅ | — | — |
| `appointment.read` | ✅ | ✅ | ✅ | ✅ |
| `appointment.book` | ✅ | — | — | ✅ |
| `appointment.reschedule` | ✅ | — | — | ✅ |
| `appointment.cancel` | ✅ | — | — | ✅ |
| `appointment.check_in` | ✅ | ✅ | ✅ | ✅ |
| `appointment.start` / `.complete` | ✅ | ✅ | — | — |
| `appointment.recommend_slot` | ✅ | — | — | ✅ |
| `appointment.book_override` | ✅ | — | — | — |

Two gotchas worth designing around: a **Receptionist cannot edit or deactivate a patient**,
and a **Doctor cannot book or cancel** — hide those controls per permission rather than
letting the call 403.

---

## 2. Patients

`backend/app/api/v1/patients.py` · `backend/app/schemas/patient.py`

### 2.1 Endpoints

| Method | Path | Permission | Success |
|---|---|---|---|
| POST | `/api/v1/patients` | `patient.create` | 201 |
| GET | `/api/v1/patients` | `patient.read` | 200 (paginated) |
| GET | `/api/v1/patients/{patient_id}` | `patient.read` | 200 |
| PATCH | `/api/v1/patients/{patient_id}` | `patient.update` | 200 |
| DELETE | `/api/v1/patients/{patient_id}` | `patient.delete` | 200 (soft delete) |

`DELETE` returns the updated record with `status: "inactive"`, not a 204 — the row is
never removed, because appointments and invoices keep referencing it.

### 2.2 Canonical field shapes

- **Name** is stored as `first_name` + `last_name`. Both responses also carry a computed
  `full_name`. There is no single `name` input field — a create must supply both parts.
- **Age** is never stored or accepted. `date_of_birth` is the input; `age` is computed at
  response time and is present on both response shapes. Do not send `age`.
- **Gender** is `"male" | "female" | "other" | "unspecified"` — lowercase, and fixed by
  the `gender_enum` Postgres type ([05-DATABASE_DESIGN.md](05-DATABASE_DESIGN.md) §2.7).
  `"M"`/`"F"` are rejected with 422. `unspecified` exists so "declined to answer" is
  recorded as itself rather than being coerced to `other`.
- **MRN** is generated server-side, unique per hospital, format `MRN-{year}-{seq:05d}`
  (e.g. `MRN-2026-00042`). It cannot be supplied on create and cannot be changed on update.
- **`status`** is `"active" | "inactive"` and is derived from the soft-delete column. It
  is **not** a clinical state — there is no Admitted/Discharged/Critical concept in this
  module, and no admissions module exists yet.
- A patient has **no assigned doctor or department**. That relationship lives on
  appointments. To show "current doctor" in a patient list you would have to join
  appointments client-side; nothing on the patient endpoint provides it.

### 2.3 `POST /api/v1/patients`

Request (`CreatePatientRequest`) — required: `first_name`, `last_name`, `date_of_birth`,
`gender`. Everything else optional.

```json
{
  "first_name": "Ananya",
  "last_name": "Rao",
  "date_of_birth": "1988-03-14",
  "gender": "female",
  "phone": "+919812345678",
  "email": "ananya@example.com",
  "blood_group": "B+",
  "address": {
    "line1": "12, MG Road",
    "city": "Hyderabad",
    "state": "TS",
    "postal_code": "500001",
    "country": "IN"
  }
}
```

Validation the form must respect:

| Field | Rule |
|---|---|
| `first_name`, `last_name` | 1–100 chars |
| `date_of_birth` | not in the future; age ≤ 130 |
| `gender` | the four enum values above |
| `phone` | normalized to E.164, max 20 chars; blank is allowed, malformed is 422 |
| `email` | lowercased and trimmed; must have one `@` and a dotted domain |
| `address.country` | uppercased ISO country code |
| `emergency_contact` | `{ name, phone, relation }` — phone must be E.164 |
| `allergies[]` | `{ name, severity: "mild"\|"moderate"\|"severe", reaction?, noted_on? }` |
| `chronic_conditions[]` | `{ name, since_year?, notes? }` |
| `current_medications[]` | `{ name, dosage?, frequency?, started_on? }` |

Response `201` → `PatientResponse` (§2.6). `409 RESOURCE_CONFLICT` if no MRN could be
allocated.

### 2.4 `GET /api/v1/patients`

| Query param | Type | Notes |
|---|---|---|
| `q` | string ≤100 | **Prefix** match on first *or* last name (case-insensitive), **exact** match on MRN or phone. Not a substring search — `"ao"` will not find `"Rao"`. |
| `gender` | enum | Exact |
| `date_of_birth` | `YYYY-MM-DD` | Exact |
| `age_gte` / `age_lte` | int 0–130 | Inverted range is 422 |
| `include_inactive` | bool | Default `false` |
| `page` | int ≥1 | Default 1 |
| `page_size` | int 1–100 | Default 25 |

Unknown query params are ignored by FastAPI, but sending `search=` or `pageSize=` simply
does nothing — the names are `q` and `page_size`.

Order is fixed: `last_name`, then `first_name`, then `id`. The `id` tiebreak makes paging
stable.

Response `data[]` is `PatientSummaryResponse` — deliberately lighter than the detail
shape, with no medical history:

```json
{
  "id": "3f6c1b2e-...",
  "mrn": "MRN-2026-00042",
  "first_name": "Ananya",
  "last_name": "Rao",
  "full_name": "Ananya Rao",
  "date_of_birth": "1988-03-14",
  "age": 38,
  "gender": "female",
  "phone": "+919812345678",
  "status": "active"
}
```

### 2.5 `PATCH /api/v1/patients/{id}`

Partial update. Omitted fields are untouched; sending explicit `null` for a `NOT NULL`
column (`first_name`, `last_name`, `date_of_birth`, `gender`) is rejected. `mrn` and
`hospital_id` are rejected outright.

### 2.6 `PatientResponse` (create / get / update)

`PatientSummaryResponse` plus: `hospital_id`, `blood_group`, `email`, `address`,
`emergency_contact`, `marital_status`, `occupation`, `allergies[]`,
`chronic_conditions[]`, `current_medications[]`, `notes`, `created_at`, `updated_at`.
`full_name` and `age` are computed here too.

---

## 3. Departments

`backend/app/api/v1/departments.py` · `backend/app/schemas/department.py`

| Method | Path | Permission | Success |
|---|---|---|---|
| POST | `/api/v1/departments` | `department.create` | 201 |
| GET | `/api/v1/departments` | `department.read` | 200 (paginated) |
| GET | `/api/v1/departments/{id}` | `department.read` | 200 |
| PATCH | `/api/v1/departments/{id}` | `department.update` | 200 |
| DELETE | `/api/v1/departments/{id}` | `department.delete` | 200 (soft delete) |
| POST | `/api/v1/departments/{id}/activate` | `department.update` | 200 |

Query params on the list: `q`, `include_inactive`, `page`, `page_size`. `q` is a
case-insensitive **prefix** match on name and an **exact** match on code.

`DepartmentSummaryResponse` (list rows):

```json
{ "id": "…", "code": "CARD", "name": "Cardiology", "location": "Block A, 2nd floor", "status": "active" }
```

`DepartmentResponse` (detail) adds `hospital_id`, `description`, `phone_extension`,
`email`, `created_at`, `updated_at`.

`code` is unique per hospital and is what a duplicate 409 refers to.

---

## 4. Doctors

`backend/app/api/v1/doctors.py` · `backend/app/schemas/doctor.py`

### 4.1 Endpoints

| Method | Path | Permission |
|---|---|---|
| POST | `/api/v1/doctors` | `doctor.create` |
| GET | `/api/v1/doctors` | `doctor.read` |
| GET | `/api/v1/doctors/{id}` | `doctor.read` |
| PATCH | `/api/v1/doctors/{id}` | `doctor.update` |
| DELETE | `/api/v1/doctors/{id}` | `doctor.delete` |
| POST | `/api/v1/doctors/{id}/activate` | `doctor.update` |
| GET | `/api/v1/doctors/{id}/availability` | `doctor.availability.read` |
| PUT | `/api/v1/doctors/{id}/availability` | `doctor.availability.update` |
| GET | `/api/v1/doctors/{id}/leaves` | `doctor.read` |
| POST | `/api/v1/doctors/{id}/leaves` | `doctor.leave.create` |
| DELETE | `/api/v1/doctors/{id}/leaves/{leave_id}` | `doctor.leave.delete` |
| GET | `/api/v1/doctors/{id}/slots?date=YYYY-MM-DD` | `doctor.availability.read` |

### 4.2 Doctor ↔ user ↔ department

A doctor is a **profile attached to an existing user**, not a standalone person. `POST
/doctors` takes a `user_id` — the user must already exist. There is no "create doctor and
user in one call" endpoint. Name and email come from that user record, which is why
`full_name` is read-only on the doctor and there are no name fields on create/update.

`department_id` is **nullable** — a doctor may be unassigned. `department_name` is
denormalized into both response shapes so a list view needs no second call.

### 4.3 `GET /api/v1/doctors`

| Query param | Notes |
|---|---|
| `q` | Prefix match on the user's first/last name, exact match on `license_number` |
| `specialization` | **Exact** string match, not a prefix — send the value verbatim |
| `department` | Department **UUID** (note: the param is `department`, not `department_id`) |
| `include_inactive` | Default `false` |
| `page`, `page_size` | As §1.6 |

`DoctorSummaryResponse`:

```json
{
  "id": "…",
  "user_id": "…",
  "full_name": "Priya Sharma",
  "specialization": "Cardiology",
  "department_id": "…",
  "department_name": "Cardiology",
  "consultation_fee": "800.00",
  "status": "active"
}
```

`consultation_fee` is a **string-serialized decimal**, not a JSON number — money is
`NUMERIC(15,2)`. Parse it as a decimal string; do not run it through `parseFloat` for
anything but display.

`DoctorResponse` (detail) adds `hospital_id`, `email`, `license_number`,
`qualifications[]` (`{ degree, institution?, year? }`), `languages[]`, `bio`,
`created_at`, `updated_at`.

### 4.4 Availability

`GET` returns every window ordered by day then start time:

```json
{ "id": "…", "day_of_week": 0, "start_time": "09:00:00", "end_time": "13:00:00", "slot_duration_minutes": 30 }
```

`day_of_week` is **0 = Monday … 6 = Sunday**. Not the JS `Date.getDay()` convention —
convert.

`PUT` is a **full replace**, not a merge: `{ "entries": [...] }` becomes the entire weekly
schedule and omitted days are cleared. An empty `entries` list wipes availability.
Same-day windows must not overlap; windows that touch exactly (one ends when the next
starts) are legal and are how a mid-day slot-length change is expressed.

### 4.5 Leaves

`POST /doctors/{id}/leaves` takes `{ starts_at, ends_at, reason? }` — timezone-aware ISO
8601, `ends_at` exclusive. `LeaveResponse` echoes those plus `id` and `doctor_id`, in UTC.

### 4.6 Slots

`GET /doctors/{id}/slots?date=YYYY-MM-DD` — the parameter is `date`.

Slots are a **read model**: computed on demand from availability, leaves and existing
appointments. They are never stored, so there is no "slot id" to book against; you book by
sending `scheduled_start`/`scheduled_end` to `POST /appointments`.

```json
{
  "date": "2026-08-24",
  "doctor_id": "…",
  "timezone": "Asia/Kolkata",
  "slots": [
    { "start": "2026-08-24T09:00:00+05:30", "end": "2026-08-24T09:30:00+05:30", "status": "available", "appointment_id": null },
    { "start": "2026-08-24T09:30:00+05:30", "end": "2026-08-24T10:00:00+05:30", "status": "booked", "appointment_id": "…" }
  ]
}
```

`status` is `available | booked | on_leave`. Times are in the hospital's timezone, echoed
in `timezone`.

---

## 5. Appointments

`backend/app/api/v1/appointments.py` · `backend/app/schemas/appointment.py`

### 5.1 Endpoints

| Method | Path | Permission | Notes |
|---|---|---|---|
| POST | `/api/v1/appointments` | `appointment.book` | **Requires `Idempotency-Key` header** |
| GET | `/api/v1/appointments` | `appointment.read` | Paginated |
| GET | `/api/v1/appointments/queue` | `appointment.read` | Walk-in queue, unpaginated list |
| GET | `/api/v1/appointments/{id}` | `appointment.read` | |
| PATCH | `/api/v1/appointments/{id}` | `appointment.reschedule` | Reschedule only |
| POST | `/api/v1/appointments/{id}/check-in` | `appointment.check_in` | |
| POST | `/api/v1/appointments/{id}/start` | `appointment.start` | |
| POST | `/api/v1/appointments/{id}/complete` | `appointment.complete` | |
| POST | `/api/v1/appointments/{id}/cancel` | `appointment.cancel` | Body: `{ "reason": "…" }` |
| POST | `/api/v1/appointments/{id}/no-show` | `appointment.cancel` | |
| GET | `/api/v1/appointments/{id}/status-history` | `appointment.read` | |
| POST | `/api/v1/appointments/recommend-slot` | `appointment.recommend_slot` | AI ranking |

### 5.2 Booking

```
POST /api/v1/appointments
Idempotency-Key: 9f1c4b2a-...
```

```json
{
  "patient_id": "…",
  "doctor_id": "…",
  "scheduled_start": "2026-08-24T09:30:00+05:30",
  "scheduled_end": "2026-08-24T10:00:00+05:30",
  "type": "new",
  "reason": "Chest pain follow-up",
  "notes": "Patient prefers morning"
}
```

Four things the client must get right:

1. **`Idempotency-Key` is required**, 8–200 chars. Generate a UUID per booking attempt and
   reuse it across retries of that same attempt. A replay returns **200** with the original
   appointment and the message "Appointment already booked with this key." — not 201, and
   not a second booking. Treat 200 and 201 as the same success path in the UI.
2. There is **no `department_id`** on an appointment. Department is reached through the
   doctor. A department filter in the UI means: resolve doctors in that department first,
   then filter/query by `doctor_id`.
3. **Double-booking is caught by a database exclusion constraint**, so two receptionists
   racing the same slot means one gets `409 RESOURCE_CONFLICT` with the conflicting
   appointment attached. Handle 409 as "slot just went", refresh slots, do not retry blind.
4. Booking **outside published availability** needs `appointment.book_override`, which only
   Hospital Admin holds. Without it, an out-of-hours slot is a 400.

### 5.3 `GET /api/v1/appointments`

| Query param | Notes |
|---|---|
| `patient_id`, `doctor_id` | UUID |
| `date` | Single calendar day, `YYYY-MM-DD`, **in the hospital's own timezone** |
| `status` | `booked \| checked_in \| in_progress \| completed \| cancelled \| no_show` |
| `type` | `new \| follow_up \| walk_in \| emergency` |
| `page`, `page_size` | As §1.6 |

`date` means the clinic's calendar day: local midnight to the next local midnight in the
hospital's configured timezone (`Asia/Kolkata` for the demo hospital). Send the local date
and nothing else. There is **no `tz_offset_hours` parameter any more** — it could only
express whole hours, which is wrong for India (UTC+5:30), so the server now resolves the
day itself. A client that still sends it is not refused; the value is ignored.

The names are `date`, `status` and `type` — not `appointment_date`, `appointment_status`
or `appointment_type`. Unknown query parameters are ignored, so a wrong name does not fail:
it returns every appointment, unfiltered.

Order is earliest-first by `scheduled_start`.

`AppointmentSummaryResponse`:

```json
{
  "id": "…",
  "patient_id": "…",
  "patient_name": "Ananya Rao",
  "doctor_id": "…",
  "doctor_name": "Priya Sharma",
  "scheduled_start": "2026-08-24T04:00:00Z",
  "scheduled_end": "2026-08-24T04:30:00Z",
  "status": "booked",
  "type": "new"
}
```

`patient_name` and `doctor_name` are denormalized in — a list view needs no extra lookups.

`AppointmentResponse` (detail) adds `hospital_id`, `reason`, `notes`, `cancelled_reason`,
`checked_in_at`, `started_at`, `completed_at`, `created_at`, `updated_at`.

### 5.4 Status lifecycle

```
booked ──check-in──> checked_in ──start──> in_progress ──complete──> completed
   │                      │                     │
   └──cancel/no-show──────┴─────────────────────┘
```

`completed`, `cancelled` and `no_show` are **terminal** — a cancelled appointment is never
reactivated, a new one is booked instead. An illegal transition is `400
BUSINESS_RULE_VIOLATION`, so drive the action buttons off the current `status` rather than
letting the call fail.

`GET /{id}/status-history` returns the audit trail: `{ id, from_status, to_status,
changed_by, changed_at, reason }`, append-only.

### 5.5 Walk-in queue

`GET /api/v1/appointments/queue?doctor_id=…` returns unfinished walk-ins in arrival order
(check-in time where the patient has arrived, booking time otherwise), as a plain list —
**no pagination metadata**, so use `http.get`, not `http.getPaginated`.

There is **no token/queue-number field** on an appointment. Queue position is the array
index in this response. Do not display a "token number" as if the backend issued one.

### 5.6 AI slot recommendation

`POST /api/v1/appointments/recommend-slot` with `{ patient_id, doctor_id?, urgency?,
preferred_window_start?, preferred_window_end?, limit? }` returns
`{ recommendations: [{ slot_start, slot_end, doctor_id, score, reason }], model }`.
`score` is 0–1. `limit` is 1–10, default 3.

---

## 6. Billing

`backend/app/api/v1/services.py` · `backend/app/api/v1/invoices.py` ·
`backend/app/schemas/billing.py`

The core money path of [modules/06-billing.md](modules/06-billing.md): a services
catalog, draft invoices, discounts with approval, issue, payments, refunds, void. **PDF
and AI explain are not built** — see §6.12.

### 6.1 Endpoints

| Method | Path | Permission | Success |
|---|---|---|---|
| GET | `/api/v1/services` | `service.read` | 200 (paginated) |
| POST | `/api/v1/services` | `service.create` | 201 |
| GET | `/api/v1/services/{service_id}` | `service.read` | 200 |
| PATCH | `/api/v1/services/{service_id}` | `service.update` | 200 |
| GET | `/api/v1/invoices` | `invoice.read` or `invoice.read.own` | 200 (paginated) |
| POST | `/api/v1/invoices` | `invoice.create` | 201 |
| GET | `/api/v1/invoices/{invoice_id}` | `invoice.read` or `invoice.read.own` | 200 |
| PATCH | `/api/v1/invoices/{invoice_id}` | `invoice.update` | 200 — drafts only |
| POST | `/api/v1/invoices/{invoice_id}/issue` | `invoice.issue` | 200 |
| POST | `/api/v1/invoices/{invoice_id}/approve-discount` | `invoice.approve_discount` | 200 |
| POST | `/api/v1/invoices/{invoice_id}/void` | `invoice.void` | 200 |
| POST | `/api/v1/invoices/{invoice_id}/payments` | `invoice.payment.record` or `invoice.payment.record.cash` | 201, or 200 on a replay. **Requires `Idempotency-Key`** |
| GET | `/api/v1/invoices/{invoice_id}/payments` | `invoice.read` or `invoice.read.own` | 200 (plain list) |
| POST | `/api/v1/invoices/{invoice_id}/refund` | `invoice.refund` | 201, or 200 on a replay. **Requires `Idempotency-Key`** |
| GET | `/api/v1/invoices/{invoice_id}/refunds` | `invoice.read` or `invoice.read.own` | 200 (plain list) |

Two of these codes are **narrow** versions of a wider one, and the server applies the
limit — see §6.11. A user holding both the wide and the narrow code is not limited.

### 6.2 Money

- **Every amount is a decimal string** — `"1200.00"`, never a JSON number. Send them as
  strings too. Do not run them through `parseFloat` for anything but display.
- **The server computes every total.** No request body has `total`, `subtotal`,
  `tax_amount`, `line_total` or `tax_rate`; sending one is a `422`. To preview a total
  while editing, compute it for display only and trust the response.
- Per line: `net = unit_price × quantity`, `tax = net × tax_rate ÷ 100`, each rounded
  **half-to-even** to two places; `line_total = net + tax`. The invoice `subtotal` is the
  sum of the nets, `tax_amount` the sum of the taxes, and
  `total = subtotal + tax_amount − discount_amount`.
- `tax_rate` is a percentage (`"18.00"` = 18%). It is the hospital's configured rate for
  a taxable line and `"0.00"` otherwise. The demo hospital configures none, so every
  seeded line is untaxed.
- `currency` (ISO 4217, `"INR"` for the demo hospital) is on every invoice shape. It is
  the hospital's and cannot be set per invoice.
- `discount_amount` is an **amount**, not a percentage, and applies to the whole invoice.
  Tax is charged on the undiscounted lines; the discount comes off the total (§6.7).
- `amount_refunded` sits beside `amount_paid`; neither is ever reduced. `balance_due` is
  `total − amount_paid` and does not change when a refund is given.

### 6.3 Services catalog

`ServiceResponse` (list rows and detail are the same shape):

```json
{
  "id": "…",
  "code": "ECG",
  "name": "ECG (12-lead)",
  "category": "Diagnostics",
  "price": "450.00",
  "taxable": false,
  "is_active": true,
  "created_at": "2026-10-01T14:17:10Z",
  "updated_at": "2026-10-01T14:17:10Z"
}
```

`GET /services` query params:

| Query param | Notes |
|---|---|
| `q` | **Prefix** match on name (case-insensitive), **exact** match on code |
| `category` | Exact string match |
| `is_active` | `true` / `false`. Omit for both — inactive services are **included** by default, unlike the other lists |
| `page`, `page_size` | As §1.6 |

Order is fixed: `name`, then `id`.

`POST /services` — required: `code`, `name`, `price`. Optional: `category`, `taxable`
(default `true`).

| Field | Rule |
|---|---|
| `code` | 1–50 chars, letters/digits/`-`/`_`, uppercased automatically, unique per hospital (duplicate → `409`) |
| `name` | 1–200 chars, not blank |
| `price` | ≥ 0, at most 2 decimal places |

`PATCH /services/{id}` takes any of `name`, `category`, `price`, `taxable`, `is_active`.
**`code` cannot be changed** (`422`). There is no delete: retire a service with
`"is_active": false`. Changing `price` never alters an existing invoice — lines keep the
price they were written with.

### 6.4 Invoices

```
draft ──issue──> issued ──payment──> partially_paid ──payment──> paid
                   │   └──────────────payment in full──────────────┘
                   └──void──> void
```

`status` is `draft | issued | partially_paid | paid | void | refunded`. `void` and
`refunded` are terminal. Drive the action buttons off `status`:

| Status | Edit | Issue | Record payment | Refund | Void |
|---|:--:|:--:|:--:|:--:|:--:|
| `draft` | ✅ | ✅ unless `discount_pending_approval` | — | — | — |
| `issued` | — | — | ✅ | — | ✅ |
| `partially_paid` | — | — | ✅ | ✅ | — |
| `paid` | — | — | — | ✅ | — |
| `void`, `refunded` | — | — | — | — | — |

A disallowed action is `400 BUSINESS_RULE_VIOLATION`.

**`POST /invoices`** creates a **draft**. Required: `patient_id`. Optional:
`appointment_id`, `items[]` (max 200, may be empty), `notes` (≤ 2000).

```json
{
  "patient_id": "…",
  "appointment_id": "…",
  "items": [
    { "service_id": "…", "quantity": "1" },
    { "description": "Crepe bandage", "quantity": "2", "unit_price": "75.00" }
  ],
  "notes": "Counter items"
}
```

A line is one of two shapes, and nothing in between:

| | Catalog line | Ad-hoc line |
|---|---|---|
| `service_id` | required | omit |
| `description` | optional — overrides the service name on this invoice | **required** |
| `unit_price` | **must be omitted** — comes from the catalog | **required**, ≥ 0 |
| `taxable` | **must be omitted** — comes from the catalog | optional, default `false` |
| `quantity` | optional, default `"1"`, > 0, ≤ 2 decimals | same |

An inactive service, or one from another hospital, is a `422` naming the line
(`items.1.service_id`). An `appointment_id` must belong to the same patient (`422`
otherwise), and **an appointment can have only one live invoice** — a second is
`409 RESOURCE_CONFLICT`. Void invoices do not count, so void-and-re-raise works.

**`InvoiceResponse`** (create / get / patch / issue / void):

```json
{
  "id": "…",
  "hospital_id": "…",
  "invoice_number": "INV-2026-000003",
  "patient_id": "…",
  "patient_name": "Thomas George",
  "appointment_id": "…",
  "status": "partially_paid",
  "currency": "INR",
  "items": [
    {
      "id": "…",
      "service_id": "…",
      "description": "Follow-up consultation",
      "quantity": "1.00",
      "unit_price": "300.00",
      "tax_rate": "0.00",
      "line_total": "300.00",
      "position": 0
    },
    {
      "id": "…",
      "service_id": "…",
      "description": "ECG (12-lead)",
      "quantity": "1.00",
      "unit_price": "450.00",
      "tax_rate": "0.00",
      "line_total": "450.00",
      "position": 1
    }
  ],
  "subtotal": "750.00",
  "tax_amount": "0.00",
  "discount_amount": "0.00",
  "discount_reason": null,
  "discount_pending_approval": false,
  "discount_approved_by": null,
  "total": "750.00",
  "amount_paid": "300.00",
  "amount_refunded": "0.00",
  "balance_due": "450.00",
  "notes": null,
  "issued_at": "2026-09-30T05:05:00Z",
  "voided_at": null,
  "void_reason": null,
  "created_at": "2026-10-01T14:17:11Z",
  "updated_at": "2026-10-01T14:17:11Z"
}
```

`invoice_number` and `issued_at` are `null` on a draft. `items` come back in `position`
order. `patient_name` is denormalized in.

**`PATCH /invoices/{id}`** — drafts only. Body is any of `items`, `notes`,
`discount_amount`, `discount_reason`; at least one is required. **`items` replaces the
whole line set**, it is not merged — send every line you want to keep. `patient_id` and
`appointment_id` cannot be changed. Discounts are covered in §6.7.

**`GET /invoices`**

| Query param | Notes |
|---|---|
| `patient_id` | UUID |
| `status` | One of the six status values |
| `discount_pending` | `true` returns the drafts whose discount awaits approval — the admin's approval queue |
| `issued_from`, `issued_to` | `YYYY-MM-DD`, both **inclusive**, interpreted in the **hospital's timezone** — no offset parameter needed. Drafts have no issue date and never match. `issued_from` after `issued_to` is a `422` |
| `page`, `page_size` | As §1.6 |

Order is newest first by `created_at`. `data[]` is `InvoiceSummaryResponse` — no lines:

```json
{
  "id": "…",
  "invoice_number": "INV-2026-000003",
  "patient_id": "…",
  "patient_name": "Thomas George",
  "appointment_id": "…",
  "status": "partially_paid",
  "currency": "INR",
  "total": "750.00",
  "amount_paid": "300.00",
  "amount_refunded": "0.00",
  "balance_due": "450.00",
  "discount_pending_approval": false,
  "issued_at": "2026-09-30T05:05:00Z",
  "created_at": "2026-10-01T14:17:11Z"
}
```

### 6.5 Issue

`POST /invoices/{id}/issue` — no body. Recomputes and freezes the totals, stamps
`issued_at`, and assigns the next number.

- Numbers are `INV-{year}-{seq:06d}`, **sequential and gap-free per hospital**. The
  sequence does not reset each year; `{year}` is the issue year in the hospital's
  timezone.
- A draft with no lines cannot be issued (`400`).
- A draft whose discount is awaiting approval cannot be issued (`400`) — see §6.7.
- A zero-total invoice goes straight to `paid`.
- After issue the invoice is immutable. A correction is a void plus a new invoice.

### 6.6 Payments

```
POST /api/v1/invoices/{invoice_id}/payments
Idempotency-Key: 9f1c4b2a-7d3e-4c1a-9b2f-0a1b2c3d4e5f
```

```json
{ "amount": "300.00", "method": "card", "reference": "CARD-TXN-8899", "notes": "Paid at the desk" }
```

`method` is `cash | card | upi | bank_transfer | insurance`. `amount` must be > 0 with at
most 2 decimals. `reference` (≤ 100) and `notes` (≤ 2000) are optional.

Response `data` is the payment **and** the invoice as it now stands, so the balance and
status can be updated without a second request:

```json
{
  "payment": {
    "id": "…",
    "invoice_id": "…",
    "amount": "300.00",
    "method": "card",
    "reference": "CARD-TXN-8899",
    "notes": "Paid at the desk",
    "received_by": "…",
    "received_at": "2026-09-30T05:10:00Z"
  },
  "invoice": { "…": "InvoiceSummaryResponse, as §6.4" }
}
```

Four things the client must get right:

1. **`Idempotency-Key` is required**, 16–100 chars (a UUID fits). Generate one per
   payment attempt and reuse it across retries of that attempt. A replay returns **200**
   with the original payment and the message "Payment already recorded with this key." —
   not 201, and not a second payment. Treat 200 and 201 as the same success path.
2. **Reusing a key for a different payment is `409`** — a different invoice, amount or
   method. Generate a fresh key for every new payment, including a second payment on the
   same invoice.
3. **Overpayment is `400`.** The amount cannot exceed `balance_due`. Two cashiers paying
   the same invoice at once are serialized by the server, so the second sees the reduced
   balance. On a `400`, re-fetch the invoice and show the current balance; do not retry
   blind.
4. Only `issued` and `partially_paid` invoices take payments. The invoice becomes
   `partially_paid`, or `paid` once `balance_due` reaches `"0.00"`.
5. **A cash-only user gets `403` for any other method.** A receptionist holds
   `invoice.payment.record.cash`, not `invoice.payment.record`. For them, offer only
   `cash` in the method selector rather than letting `card` or `upi` fail.

`GET /invoices/{id}/payments` returns the payments oldest-first as a plain list — **no
pagination metadata**, so use `http.get`, not `http.getPaginated`.

### 6.7 Discounts and approval

Set a discount on a draft with `PATCH /invoices/{id}`:

```json
{ "discount_amount": "200.00", "discount_reason": "Financial hardship" }
```

- `discount_amount` must be ≥ 0 and **must not exceed `subtotal`** (`422` naming
  `discount_amount`). A discount above zero **needs a `discount_reason`** (`422` naming
  `discount_reason`). Send `"0"` to remove a discount; the reason is cleared with it.
- The server compares the discount with the **hospital's approval threshold**, a
  percentage of the subtotal. At or below it, nothing more is needed. Above it, the draft
  comes back with `"discount_pending_approval": true`.
- **A pending discount blocks the issue.** `POST /invoices/{id}/issue` returns `400` until
  an admin approves. Show the draft as "awaiting approval" and disable the Issue button
  rather than letting it fail.
- **`POST /invoices/{id}/approve-discount`** (no body, `invoice.approve_discount`) clears
  the flag and sets `discount_approved_by`. If there is nothing to approve it is `409` —
  which is also what the second of two admins approving at once receives.
- **Editing withdraws an approval.** Changing `discount_amount` or sending `items` resets
  `discount_approved_by` to `null` and re-evaluates the threshold. Editing only `notes`
  does not.
- A client cannot approve its own discount: `discount_pending_approval` and
  `discount_approved_by` are not accepted in any request body (`422`).

The threshold is `settings.billing.discount_approval_threshold_percent` on the hospital,
set through `PATCH /hospitals/current`. **If a hospital has not set one it is 0, so every
discount needs approval.** The demo hospital is seeded with 10.

The approval queue for an admin is `GET /invoices?discount_pending=true`.

### 6.8 Refunds

```
POST /api/v1/invoices/{invoice_id}/refund
Idempotency-Key: 4b8e2f1c-9a3d-4e7b-8c1f-2d3e4f5a6b7c
```

```json
{ "amount": "350.00", "method": "card", "reason": "Blood sample could not be processed.", "reference": "CARD-REFUND-0006" }
```

`reason` is **required** (1–500 chars, not blank). `method` is how the money goes back,
from the same list as payments. `reference` is optional. Requires `invoice.refund`, which
only a Hospital Admin holds.

Response `data` mirrors a payment's:

```json
{
  "refund": {
    "id": "…",
    "invoice_id": "…",
    "amount": "350.00",
    "method": "card",
    "reason": "Blood sample could not be processed.",
    "reference": "CARD-REFUND-0006",
    "refunded_by": "…",
    "refunded_at": "2026-10-03T14:30:00Z"
  },
  "invoice": { "…": "InvoiceSummaryResponse, as §6.4" }
}
```

- Only a `partially_paid` or `paid` invoice can be refunded (`400` otherwise).
- The amount cannot exceed what is left to give back: `amount_paid − amount_refunded`
  (`400`).
- **Refunding everything closes the invoice as `refunded`**, which is terminal. A partial
  refund leaves the status as it was.
- `Idempotency-Key` works exactly as for payments (§6.6): required, 16–100 chars, a replay
  is `200` with the original refund, and reusing a key for a different refund is `409`.
- This is how a part-paid invoice is undone: it cannot be voided, but it can be refunded
  in full.

`GET /invoices/{id}/refunds` returns the refunds oldest-first as a plain list, with no
pagination metadata.

### 6.9 Void

`POST /invoices/{id}/void` with `{ "reason": "…" }` — required, 1–500 chars, not blank.

Allowed only while the invoice is `issued` **and has taken no payment**. An invoice with
any payment cannot be voided (`400`, "must be refunded first") — refund it instead (§6.8).
The voided invoice keeps its `invoice_number`; `voided_at` and `void_reason` are set. A
draft cannot be voided, and there is no way to delete one.

### 6.10 Invoices drafted from appointments

`POST /appointments/{id}/complete` now drafts an invoice automatically: one ad-hoc line,
`Consultation — Dr. {first} {last}`, at the doctor's `consultation_fee`, untaxed, linked
by `appointment_id`. Find it with `GET /invoices?patient_id=…&status=draft`.

- If the appointment already has a live invoice, nothing is drafted.
- The draft is created after the appointment is committed. A billing failure does not
  fail the completion — the response is still `200` and the invoice can be raised by hand.
- The complete response does **not** include the invoice id.

### 6.11 Roles → permissions

Which seeded role can call what. Hide controls per permission rather than letting the
call 403.

| Permission | Hospital Admin | Billing Staff | Receptionist | Doctor | Nurse |
|---|:--:|:--:|:--:|:--:|:--:|
| `service.read` | ✅ | ✅ | ✅ | — | — |
| `service.create` / `service.update` | ✅ | — | — | — | — |
| `invoice.read` | ✅ | ✅ | ✅ | — | — |
| `invoice.read.own` | ✅ | — | — | ✅ | — |
| `invoice.create` / `invoice.update` | ✅ | ✅ | — | — | — |
| `invoice.issue` | ✅ | ✅ | — | — | — |
| `invoice.approve_discount` | ✅ | — | — | — | — |
| `invoice.void` | ✅ | — | — | — | — |
| `invoice.refund` | ✅ | — | — | — | — |
| `invoice.payment.record` | ✅ | ✅ | — | — | — |
| `invoice.payment.record.cash` | ✅ | — | ✅ | — | — |

**Two narrow codes, both enforced by the server:**

- **`invoice.read.own` — a doctor sees the invoices for their own visits only.** That
  means invoices linked to an appointment where they are the doctor. Another doctor's
  invoice for the same patient, and any invoice with no appointment, are not theirs. The
  list and its `total_records` contain only their invoices, and asking for any other
  invoice by id is a `404` identical to a missing one — so the client needs no special
  handling: call the same endpoints and render what comes back. A user with this code
  but no doctor profile gets an empty list.
- **`invoice.payment.record.cash` — a receptionist records cash only.** Any other
  `method` is `403 PERMISSION_DENIED`.

Things worth designing around: **only an admin can void, approve a discount or refund**
— Billing Staff can *set* a discount but not approve it; a **receptionist can take a
cash payment but cannot create or issue** an invoice; and a **doctor is read-only**, with
no access to the services catalog — hide every billing action for them.

Either read code opens the Billing module. These replace the earlier `billing.read` /
`billing.write` placeholders, which the backend never issued. `invoice.pdf.download` and
`invoice.ai_explain` are in the catalog but guard nothing yet.

### 6.12 Not built yet

These paths from the module spec return `404`. Do not build against them:

- `GET /invoices/{id}/pdf`
- `POST /invoices/{id}/ai-explain`

---

## 7. Notifications

`backend/app/api/v1/notifications.py` · `backend/app/schemas/notification.py`

The MVP slice of [modules/11-notifications.md](modules/11-notifications.md): an in-app
notification centre for staff, per-user channel preferences, hospital announcements, and
email for the kinds that need it. **SMS, push, admin-editable templates and the delivery
log are not built** — see §7.7.

### 7.1 Endpoints

| Method | Path | Permission | Success |
|---|---|---|---|
| GET | `/api/v1/notifications` | `notification.read.own` | 200 (paginated) |
| GET | `/api/v1/notifications/unread-count` | `notification.read.own` | 200 |
| POST | `/api/v1/notifications/{notification_id}/read` | `notification.read.own` | 200 |
| POST | `/api/v1/notifications/read-all` | `notification.read.own` | 200 |
| GET | `/api/v1/notifications/preferences` | `notification.read.own` | 200 |
| PUT | `/api/v1/notifications/preferences` | `notification.preference.update.own` | 200 |
| POST | `/api/v1/notifications/broadcast` | `notification.broadcast` | 200 |

**Every endpoint is about the caller's own notifications.** None takes a user id. Someone
else's notification — a colleague's or another hospital's — is a `404`, never a `403`.

Every seeded role holds the two `.own` codes. Only **Hospital Admin** and **Super Admin**
hold `notification.broadcast`.

### 7.2 The notification centre

`GET /api/v1/notifications` — newest first.

| Query | Type | Default | Meaning |
|---|---|---|---|
| `unread_only` | bool | `false` | Only notifications not yet read |
| `page` | int ≥ 1 | `1` | |
| `page_size` | int 1–100 | `25` | |

```json
{
  "success": true,
  "message": "Notifications retrieved.",
  "data": [
    {
      "id": "0b9c6f0e-3f1b-4a5e-9c55-0a1f6f1d2e77",
      "kind": "billing.discount_approval_requested",
      "title": "Discount awaiting your approval",
      "body": "Priya Sharma applied a discount of INR 200.00 to an invoice for Ananya Rao. It cannot be issued until an admin approves it.",
      "link": "/billing",
      "is_read": false,
      "read_at": null,
      "created_at": "2026-10-04T09:00:00Z"
    }
  ],
  "metadata": { "pagination": { "page": 1, "page_size": 25, "total_records": 1, "total_pages": 1 } }
}
```

- `link` is an **in-app path** (or `null`) — route to it on click; it is never an external
  URL.
- `title` and `body` are already rendered text. Display them as text, not HTML.
- `kind` is a stable code; use it to pick an icon. The list of kinds is in §7.4.

`GET /api/v1/notifications/unread-count` → `"data": { "unread": 3 }`. This is the number
for the bell. There is no push channel yet — **poll it** (30–60 s is plenty).

`POST /api/v1/notifications/{notification_id}/read` → the notification, now with
`is_read: true` and `read_at` set. Marking one that is already read is a `200` and changes
nothing. No request body.

`POST /api/v1/notifications/read-all` → `"data": { "marked": 3 }`. No request body.

### 7.3 Preferences

`GET /api/v1/notifications/preferences` returns **every** kind with what is in effect for
the caller, so the page can be drawn from this response alone:

```json
{
  "kinds": [
    {
      "kind": "auth.password_reset_requested",
      "category": "Account",
      "label": "Password reset requested",
      "critical": true,
      "in_app": true,
      "email": true,
      "email_available": true,
      "locked_channels": ["in_app", "email"]
    },
    {
      "kind": "billing.discount_approval_requested",
      "category": "Billing",
      "label": "Discount awaiting approval",
      "critical": false,
      "in_app": true,
      "email": false,
      "email_available": true,
      "locked_channels": []
    }
  ]
}
```

- Group rows by `category`; show `label`.
- **Disable the toggle** for any channel named in `locked_channels` — a critical kind
  cannot be switched off. Hide the email toggle when `email_available` is `false`.

`PUT /api/v1/notifications/preferences` — send only what changes:

```json
{ "preferences": { "billing.discount_approval_requested": { "email": true },
                   "system.broadcast": { "in_app": false } } }
```

- Each kind takes `in_app` and/or `email` (booleans). A channel left out is left as it
  was; a kind left out is left as it was. `sms` is rejected with a `422`.
- The response has the same shape as the `GET`, showing what is **now in effect**.
- Switching a critical kind off is accepted and has no effect — the response still shows
  it on. An unknown kind is a `422` with `field: "preferences.<kind>"`.
- Switching `in_app` off and `email` on gives the user the email and keeps the
  notification out of the centre.

### 7.4 What raises a notification

| Kind | When | Who | Default channels | Critical |
|---|---|---|---|:--:|
| `auth.user_invited` | `POST /users` invites someone | The invited user | in-app + email | ✅ |
| `auth.password_reset_requested` | `POST /auth/password/forgot` | That user | in-app + email | ✅ |
| `billing.discount_approval_requested` | A draft's discount goes above the hospital's threshold (§6.7), or a pending discount's amount changes | Every active user holding `invoice.approve_discount`, except the person who applied it | in-app | — |
| `system.broadcast` | `POST /notifications/broadcast` | The role, or the whole hospital | in-app | — |
| `inventory.low_stock` | An item's usable stock crosses its reorder point (§10.6) | Every active user holding `inventory.po.create` | in-app | — |
| `lab.critical_result` | A result is entered in the critical range (§8.5) | The ordering doctor | in-app only | ✅ |
| `lab.results_released` | A lab order is released (§8.5) | The ordering doctor | in-app only | — |
| `lab.result_amended` | A released result is corrected (§8.6) | The ordering doctor | in-app only | ✅ |

The invitation and reset emails carry the single-use link
`{FRONTEND_BASE_URL}/reset-password?token=…`, which is the frontend's existing
`/reset-password` page: it reads `token` and posts it to `POST /api/v1/auth/password/reset`
with the new password. For an invited user that same call activates the account. The token
appears only in the email — never in the in-app notification and never in this API.

`POST /users` still returns the invite token in its response as before, so an admin can
pass the link on by hand where email is not configured.

### 7.5 Broadcast

`POST /api/v1/notifications/broadcast`

```json
{
  "title": "Scheduled maintenance tonight",
  "body": "The system will be unavailable from 23:00 to 23:30.",
  "link": "/dashboard",
  "role_id": null
}
```

| Field | Rules |
|---|---|
| `title` | Required, 1–200 characters, not blank |
| `body` | Required, 1–2000 characters, not blank |
| `link` | Optional. Must be an in-app path: starts with a single `/`. An external URL is a `422` |
| `role_id` | Optional. Omit or `null` for every active user in the hospital |

→ `"data": { "recipients": 12 }`. Each recipient gets their own notification, the sender
included. Users who are invited-but-not-activated or suspended are not counted. A `role_id`
from another hospital reaches nobody (`recipients: 0`).

### 7.6 Email

Email is **off unless the backend is configured with `SMTP_HOST`**, and the background
worker must be running — the API only queues an email; the worker sends it, polling every
ten seconds. With email off, an in-app notification is still delivered and the queued
email is recorded as failed with the reason. A send that fails is retried up to five times
with increasing delays.

None of this is visible through the API yet (the delivery log is in §7.7); what the
frontend sees is only the in-app half.

### 7.7 Not built yet

These paths from the module spec return `404`. Do not build against them:

- `GET /notifications/templates`, `POST /notifications/templates`,
  `PUT /notifications/templates/{id}` — the wording of each kind is fixed in code.
- `GET /notifications/delivery-log`

Also not built: SMS, WhatsApp and push; live delivery over a socket; hospital-wide default
preferences; and **any notification to a patient** — appointment reminders, invoice
emails. Recipients are staff users only.

---

## 8. Laboratory

`backend/app/api/v1/tests_catalog.py` · `backend/app/api/v1/lab_orders.py` ·
`backend/app/schemas/lab.py`

The core of [modules/07-laboratory.md](modules/07-laboratory.md): a test catalog with
reference ranges, and lab orders taken from order through sample collection and result
entry to release, with corrections after release. **PDF reports and AI explain are not
built** — see §8.8.

### 8.1 Endpoints

| Method | Path | Permission | Success |
|---|---|---|---|
| GET | `/api/v1/tests-catalog` | `lab.test.read` | 200 (paginated) |
| POST | `/api/v1/tests-catalog` | `lab.test.create` | 201 |
| GET | `/api/v1/tests-catalog/{test_id}` | `lab.test.read` | 200 |
| PATCH | `/api/v1/tests-catalog/{test_id}` | `lab.test.update` | 200 |
| GET | `/api/v1/lab-orders` | `lab.order.read` | 200 (paginated) |
| POST | `/api/v1/lab-orders` | `lab.order.create` | 201 |
| GET | `/api/v1/lab-orders/{order_id}` | `lab.order.read` | 200 |
| PATCH | `/api/v1/lab-orders/{order_id}` | `lab.order.create` | 200 — priority and notes only |
| POST | `/api/v1/lab-orders/{order_id}/collect` | `lab.order.collect_sample` | 200 |
| POST | `/api/v1/lab-orders/{order_id}/enter-results` | `lab.order.enter_results` | 200 |
| POST | `/api/v1/lab-orders/{order_id}/release` | `lab.order.release` | 200 |
| POST | `/api/v1/lab-orders/{order_id}/cancel` | `lab.order.cancel` | 200 |
| POST | `/api/v1/lab-orders/{order_id}/items/{item_id}/amend` | `lab.order.amend` | 200 |

A step attempted from the wrong status is a `400` with `error_code:
"BUSINESS_RULE_VIOLATION"`. An order or test in another hospital is a `404`.

### 8.2 Roles → permissions

| Permission | Hospital Admin | Doctor | Nurse | Lab Technician |
|---|:--:|:--:|:--:|:--:|
| `lab.test.read` | ✅ | ✅ | — | ✅ |
| `lab.test.create` / `.update` | ✅ | — | — | — |
| `lab.order.read` | ✅ | ✅ | ✅ | ✅ |
| `lab.order.create` / `.cancel` | ✅ | ✅ | — | — |
| `lab.order.collect_sample` | ✅ | — | — | ✅ |
| `lab.order.enter_results` | ✅ | — | — | ✅ |
| `lab.order.release` | ✅ | — | — | — |
| `lab.order.amend` | ✅ | — | — | — |

The spec gives release and amendment to a *Lab Supervisor*. There is no such seeded role,
so today **only an admin can release or amend** — a technician cannot release their own
results. Receptionist, Billing Staff, Pharmacist and Inventory Manager hold no lab code.
These replace the earlier `lab.read` / `lab.create` / `lab.update` placeholders.
`lab.report.download` and `lab.ai_explain` are in the catalog but guard nothing yet.

### 8.3 Test catalog

`POST /api/v1/tests-catalog`

```json
{
  "code": "HB",
  "name": "Haemoglobin",
  "category": "Haematology",
  "unit": "g/dL",
  "result_type": "numeric",
  "reference_ranges": [
    { "sex": "male", "age_min": 18, "low": "13.0", "high": "17.0", "critical_low": "7.0" },
    { "sex": "female", "age_min": 18, "low": "12.0", "high": "15.5", "critical_low": "7.0" },
    { "sex": "any", "age_min": 0, "age_max": 17, "low": "11.0", "high": "14.5" }
  ],
  "turnaround_hours": 4,
  "price": "250.00"
}
```

| Field | Rules |
|---|---|
| `code` | Required, ≤ 50, letters/digits/`-`/`_`. Uppercased. Unique per hospital → `409` |
| `name` | Required, ≤ 200 |
| `category`, `unit` | Optional free text (≤ 100, ≤ 20) |
| `result_type` | `numeric` (default) or `text`. **Cannot be changed later** |
| `reference_ranges` | A `numeric` test needs at least one; a `text` test cannot have any |
| `turnaround_hours` | Optional, > 0 |
| `price` | Decimal string, ≥ 0. Default `"0.00"` |

One range entry: `sex` is `male`, `female` or `any` (default); `age_min` / `age_max` are
whole years, inclusive, either may be omitted; at least one of `low` / `high`;
`critical_low` / `critical_high` are optional. Bounds are decimal strings.

`PATCH` takes `name`, `category`, `unit`, `reference_ranges` (replaces the whole list),
`turnaround_hours`, `price`, `is_active`. Sending `code` or `result_type` is a `422`.
Editing a test never changes an order already placed.

`GET /api/v1/tests-catalog` takes `q` (name prefix, or exact code), `category`,
`is_active`, `page`, `page_size`; ordered by name. For an order form, ask for
`is_active=true`.

The response adds `id`, `is_active`, `created_at`, `updated_at`.

### 8.4 Ordering

`POST /api/v1/lab-orders`

```json
{
  "appointment_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "test_ids": ["8a6e0804-2bd0-4672-b79d-d97027f9071a"],
  "priority": "routine",
  "notes": "Fasting sample."
}
```

- **`appointment_id` is required.** The patient and the ordering doctor are taken from
  that appointment — do not send them; `patient_id` or `doctor_id` in the body is a `422`.
  A `cancelled` or `no_show` appointment is refused.
- `test_ids`: 1–50, no repeats, each an active test of this hospital. A bad one is a
  `422` naming `test_ids.<index>`.
- `priority`: `routine` (default), `urgent`, `stat`.

`LabOrderResponse`:

```json
{
  "id": "…",
  "appointment_id": "…",
  "patient_id": "…", "patient_name": "Ananya Rao", "patient_mrn": "MRN-2026-00007",
  "doctor_id": "…", "doctor_name": "Dr. Priya Sharma",
  "ordered_at": "2026-10-05T09:00:00Z",
  "priority": "routine",
  "status": "ordered",
  "notes": "Fasting sample.",
  "collected_at": null, "results_entered_at": null,
  "released_at": null, "released_by": null,
  "cancelled_at": null, "cancel_reason": null,
  "invoice_id": "…",
  "turnaround_minutes": null,
  "has_abnormal": false,
  "has_critical": false,
  "items": [
    {
      "id": "…", "test_id": "…", "test_code": "HB", "test_name": "Haemoglobin",
      "result_type": "numeric", "price": "250.00",
      "sample_id": null, "sample_collected_at": null,
      "result_value": null, "result_unit": null, "result_flag": null,
      "reference_low": null, "reference_high": null,
      "result_entered_at": null, "released_at": null,
      "notes": null, "amendments": []
    }
  ]
}
```

The same shape is returned by every order endpoint, list included.

`GET /api/v1/lab-orders` — newest first. Filters: `status`, `priority`, `patient_id`,
`doctor_id`, `appointment_id`, plus `page` / `page_size`. This is the lab worklist; the
release queue is `status=results_entered`.

`PATCH /api/v1/lab-orders/{id}` changes `priority` and/or `notes` while the order is not
released or cancelled. The tests on an order cannot be changed.

### 8.5 Lifecycle

```
ordered ──collect──▶ collected ──enter-results──▶ in_progress ──▶ results_entered ──release──▶ released
   └────────────────────── cancel (any status before released) ──────────────────────▶ cancelled
```

| Step | From | Body | Result |
|---|---|---|---|
| `collect` | `ordered` | none, or `{ "items": [{ "item_id", "sample_id"? }] }` | `collected` once no sample is outstanding; stays `ordered` if some are |
| `enter-results` | `collected`, `in_progress`, `results_entered` | `{ "results": [{ "item_id", "value", "notes"? }] }` | `in_progress` while results are missing, `results_entered` when none are |
| `release` | `results_entered` | none | `released` |
| `cancel` | anything before `released` | `{ "reason": "…" }` | `cancelled` |

- **Collect.** With no body every outstanding sample is collected and given a generated
  id (`S-` + ten characters). A supplied `sample_id` is uppercased and must be unique in
  the hospital → `409` if it is not.
- **Results.** `value` is a string. A `numeric` test needs a number → `422` naming
  `results.<index>.value` otherwise. Results can be re-entered until release.
- **Flags are the server's.** Each numeric result is judged against the range for the
  patient's sex and their age on the day the sample was collected, and comes back as
  `result_flag`: `normal`, `low`, `high` or `critical`, with the `reference_low` /
  `reference_high` it was judged against. **`null` means no range applied** (a text test,
  or no range for this patient) — show it as "no reference range", not as normal. Sending
  a `result_flag` is a `422`.
- **A patient whose sex is `other` or `unspecified`** is matched only against `any`
  ranges, never a sex-specific one.
- **Critical values.** A result entered in the critical range notifies the ordering doctor
  immediately, before release.
- **Release** notifies the ordering doctor and sets `turnaround_minutes` (order to
  release). After release nothing on the order can be edited except through §8.6.

`has_abnormal` is true when any item is `low`, `high` or `critical`; `has_critical` when
any is `critical`. Use them for row colouring on the worklist.

### 8.6 Amending a released result

`POST /api/v1/lab-orders/{order_id}/items/{item_id}/amend`

```json
{ "new_value": "5.9", "reason": "Transcription error" }
```

Only on a `released` order (`400` otherwise — before release, just re-enter the result).
The item takes the new value and is flagged again; the item's `amendments` list keeps the
history, oldest first:

```json
{
  "id": "…",
  "previous_value": "4.2", "new_value": "5.9",
  "previous_flag": "normal", "new_flag": "high",
  "reason": "Transcription error",
  "amended_by": "…", "amended_at": "2026-10-05T11:30:00Z"
}
```

An unchanged value, or text for a numeric test, is a `422`. The ordering doctor is
notified. Show an amended result as amended — a non-empty `amendments` is the signal.

### 8.7 Billing

Placing an order adds one line per test (`Lab test — <name>`, at the catalog price) to a
draft invoice for the patient, in the same transaction; `invoice_id` on the order says
which.

- If the appointment has a draft invoice, the lines join it.
- If the appointment has no invoice, a draft is created and linked to it.
- If the appointment's invoice is already issued, the lines go on a new draft with no
  appointment link, because an issued invoice cannot be edited.

The lines are untaxed; billing staff adjust the draft before issuing. **Cancelling an
order does not remove its lines** — the invoice has to be corrected by hand.

### 8.8 Not built yet

These paths from the module spec return `404`. Do not build against them:

- `GET /lab-orders/{id}/report.pdf`
- `POST /lab-orders/{id}/ai-explain`

---

## 9. Pharmacy

`backend/app/api/v1/medicines.py` · `prescriptions.py` · `vendors.py` ·
`purchase_orders.py` · `backend/app/schemas/pharmacy.py`

The core of [modules/08-pharmacy.md](modules/08-pharmacy.md): a medicine catalog with
batch-level stock, prescriptions and dispensing, and vendors with purchase orders.
**Interaction warnings and AI substitution are not built** — see §9.9.

### 9.1 Endpoints

| Method | Path | Permission | Success |
|---|---|---|---|
| GET | `/api/v1/medicines` | `pharmacy.medicine.read` | 200 (paginated) |
| POST | `/api/v1/medicines` | `pharmacy.medicine.create` | 201 |
| GET | `/api/v1/medicines/{id}` | `pharmacy.medicine.read` | 200 |
| PATCH | `/api/v1/medicines/{id}` | `pharmacy.medicine.update` | 200 |
| GET | `/api/v1/medicines/{id}/stock` | `pharmacy.batch.read` | 200 |
| GET | `/api/v1/medicines/{id}/batches` | `pharmacy.batch.read` | 200 (plain list) |
| POST | `/api/v1/medicines/{id}/batches` | `pharmacy.batch.create` | 201 |
| PATCH | `/api/v1/medicines/{id}/batches/{batch_id}` | `pharmacy.batch.update` | 200 |
| POST | `/api/v1/medicines/{id}/batches/{batch_id}/adjust` | `pharmacy.batch.update` | 200 |
| POST | `/api/v1/prescriptions` | `pharmacy.prescription.create` | 201 |
| GET | `/api/v1/prescriptions` | `pharmacy.prescription.read` | 200 (paginated) |
| GET | `/api/v1/prescriptions/pending` | `pharmacy.prescription.read` | 200 (paginated) |
| GET | `/api/v1/prescriptions/{id}` | `pharmacy.prescription.read` | 200 |
| POST | `/api/v1/prescriptions/{id}/cancel` | `pharmacy.prescription.create` | 200 |
| POST | `/api/v1/prescriptions/{id}/dispense` | `pharmacy.dispense.execute` | 201 |
| GET | `/api/v1/prescriptions/{id}/dispenses` | `pharmacy.prescription.read` | 200 (plain list) |
| GET | `/api/v1/vendors` | `pharmacy.vendor.read` | 200 (paginated) |
| POST | `/api/v1/vendors` | `pharmacy.vendor.create` | 201 |
| GET | `/api/v1/vendors/{id}` | `pharmacy.vendor.read` | 200 |
| PATCH | `/api/v1/vendors/{id}` | `pharmacy.vendor.update` | 200 |
| GET | `/api/v1/purchase-orders` | `pharmacy.po.read` | 200 (paginated) |
| POST | `/api/v1/purchase-orders` | `pharmacy.po.create` | 201 |
| GET | `/api/v1/purchase-orders/{id}` | `pharmacy.po.read` | 200 |
| POST | `/api/v1/purchase-orders/{id}/send` | `pharmacy.po.update` | 200 |
| POST | `/api/v1/purchase-orders/{id}/cancel` | `pharmacy.po.update` | 200 |
| POST | `/api/v1/purchase-orders/{id}/receive` | `pharmacy.po.receive` | 200 |

A step attempted from the wrong status is a `400` with `error_code:
"BUSINESS_RULE_VIOLATION"`. Anything in another hospital is a `404`.

### 9.2 Roles → permissions

| Permission | Hospital Admin | Doctor | Pharmacist | Inventory Manager |
|---|:--:|:--:|:--:|:--:|
| `pharmacy.medicine.read` | ✅ | ✅ | ✅ | ✅ |
| `pharmacy.medicine.create` / `.update` | ✅ | — | — | — |
| `pharmacy.batch.read` | ✅ | — | ✅ | ✅ |
| `pharmacy.batch.create` / `.update` | ✅ | — | ✅ | — |
| `pharmacy.prescription.read` | ✅ | ✅ | ✅ | — |
| `pharmacy.prescription.create` | ✅ | ✅ | — | — |
| `pharmacy.dispense.execute` | ✅ | — | ✅ | — |
| `pharmacy.po.read` | ✅ | — | ✅ | ✅ |
| `pharmacy.po.create` / `.update` | ✅ | — | — | ✅ |
| `pharmacy.po.receive` | ✅ | — | ✅ | ✅ |
| `pharmacy.vendor.read` | ✅ | — | ✅ | ✅ |
| `pharmacy.vendor.create` / `.update` | ✅ | — | — | ✅ |

The spec gives the catalog to a *Pharmacy Admin*. There is no such seeded role, so today
**only an admin can add or edit medicines**. A doctor prescribes but cannot dispense; a
pharmacist dispenses and receives stock but cannot raise a purchase order. These replace
the earlier `pharmacy.read` / `pharmacy.dispense` placeholders. `pharmacy.interaction.check`
and `pharmacy.ai_substitute` are in the catalog but guard nothing yet.

### 9.3 Medicines and stock

`POST /api/v1/medicines`

```json
{
  "sku": "PARA-500",
  "name": "Paracetamol",
  "generic_name": "Paracetamol",
  "strength": "500 mg",
  "form": "tablet",
  "atc_code": "N02BE01",
  "unit_price": "2.50",
  "requires_prescription": false
}
```

`sku` is uppercased, unique per hospital (`409`), and **cannot be changed**. `unit_price`
is the selling price per unit, a decimal string ≥ 0. `PATCH` takes any of the other
fields plus `is_active`; a new price applies to future dispenses only. `GET /medicines`
takes `q` (prefix of the name or generic name, or an exact SKU), `is_active`, `page`,
`page_size`.

**Stock is held per batch.** `POST /api/v1/medicines/{id}/batches` takes stock in directly:

```json
{ "batch_number": "B2026-041", "expiry_date": "2027-09-30", "quantity": 500, "cost_per_unit": "1.20" }
```

A batch number the medicine already has is topped up, provided `expiry_date` agrees
(`422` if not). A batch that has already expired is a `422`. `BatchResponse`:

```json
{
  "id": "…", "medicine_id": "…",
  "batch_number": "B2026-041", "expiry_date": "2027-09-30", "cost_per_unit": "1.20",
  "initial_quantity": 500, "quantity_on_hand": 500,
  "is_recalled": false,
  "days_to_expiry": 360, "is_expired": false, "expires_soon": false, "is_dispensable": true
}
```

- `expires_soon` is true within **30 days** of expiry. A batch expiring today is still
  dispensable; from the next day it is `is_expired`.
- `is_dispensable` = in stock, not expired, not recalled. Use it, not your own date maths:
  "today" is the hospital's local date.
- `PATCH …/batches/{batch_id}` with `{ "is_recalled": true }` recalls a batch.
- `POST …/batches/{batch_id}/adjust` with `{ "quantity_change": -4, "reason": "expired",
  "note": "Damaged strip" }` corrects a count. `reason` is `adjusted` (default) or
  `expired`; `note` is required; a batch cannot go below zero (`400`).

`GET /api/v1/medicines/{id}/stock` → `{ medicine, quantity_on_hand, dispensable_quantity,
expiring_soon_quantity, expired_quantity, recalled_quantity, batches[] }`, batches earliest
expiry first. `dispensable_quantity` is the number to show as "in stock".

### 9.4 Prescriptions

`POST /api/v1/prescriptions`

```json
{
  "appointment_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "notes": "Review in five days.",
  "items": [
    { "medicine_id": "…", "dosage": "1 tablet", "frequency": "three times daily",
      "duration_days": 5, "instructions": "After food.", "quantity": 15 },
    { "medicine_name": "Vitamin D drops", "dosage": "5 drops", "frequency": "daily", "quantity": 1 }
  ]
}
```

- **`appointment_id` is required**; the patient and prescribing doctor are taken from it.
  A `cancelled` or `no_show` appointment is refused.
- Each line has **either** `medicine_id` (a catalog medicine) **or** `medicine_name` (free
  text, for something the pharmacy does not stock) — both or neither is a `422`. A
  free-text line is recorded but can never be dispensed here.
- `quantity` is whole units. A catalog medicine may appear once per prescription.

`PrescriptionResponse`: `id`, `appointment_id`, `patient_id`, `patient_name`,
`patient_mrn`, `doctor_id`, `doctor_name`, `status`, `notes`, `prescribed_at`,
`cancelled_at`, `cancel_reason`, and `items[]` each with `id`, `medicine_id`,
`medicine_name`, `dosage`, `frequency`, `duration_days`, `instructions`, `quantity`,
`quantity_dispensed`, `quantity_remaining`, and **`available_quantity`** — units that can
be dispensed today (`null` on a free-text line).

`status`: `active` → `partially_dispensed` → `dispensed`, or `cancelled`. Free-text lines
never hold a prescription open.

`GET /api/v1/prescriptions/pending` is the dispensing queue: `active` and
`partially_dispensed`, **longest-waiting first**. `GET /api/v1/prescriptions` is newest
first, with `status`, `patient_id`, `doctor_id`, `appointment_id`. Cancel
(`{ "reason": "…" }`) is allowed only while nothing has been dispensed.

### 9.5 Dispensing

`POST /api/v1/prescriptions/{id}/dispense`

- **No body** dispenses everything outstanding.
- A partial dispense names lines: `{ "items": [{ "prescription_item_id": "…", "quantity": 4 }],
  "notes": "Rest tomorrow." }`. **If anything is left outstanding, `notes` is required**
  (`422` naming `notes`). Asking for more than is outstanding is a `422`.
- The server takes stock **first-expiry-first**, never from an expired or recalled batch.
  A client cannot choose a batch or a price; sending either is a `422`.
- **All or nothing.** If any medicine is short the response is `409`, nothing is
  dispensed, and `errors.shortages` lists what was missing:

```json
{ "shortages": [{ "prescription_item_id": "…", "medicine": "Amoxicillin 500 mg",
                  "requested": 21, "available": 5 }] }
```

  Offer a partial dispense of what `available_quantity` allows.

`DispenseResponse` (201):

```json
{
  "id": "…", "prescription_id": "…",
  "dispensed_at": "2026-10-05T10:00:00Z", "dispensed_by": "…",
  "total_amount": "25.00", "notes": null, "invoice_id": "…",
  "items": [
    { "id": "…", "prescription_item_id": "…", "medicine_id": "…", "medicine_name": "Paracetamol",
      "batch_id": "…", "batch_number": "PA-2401", "expiry_date": "2026-10-25",
      "quantity": 6, "unit_price": "2.50", "total": "15.00" },
    { "…": "…", "batch_number": "PA-2502", "quantity": 4, "total": "10.00" }
  ],
  "warnings": ["Paracetamol batch PA-2401 expires in 20 days (2026-10-25)."]
}
```

One line per batch drawn on, so one prescribed medicine may appear twice. **Show
`warnings` to the pharmacist** — a batch within 30 days of expiry is dispensed but
flagged. `GET …/dispenses` returns a prescription's dispenses, oldest first.

### 9.6 Billing

Each dispense adds one line per prescribed medicine (`Medicine — <name>`, quantity ×
unit price) to a draft invoice for the patient, in the same transaction; `invoice_id` on
the dispense says which. The rules for which draft are the same as for lab orders (§8.7),
so a visit's consultation, tests and medicines land on one bill. The lines are untaxed.

### 9.7 Vendors

`POST /api/v1/vendors` — `{ "name", "contact"?, "address"?, "tax_id"? }`. `name` is unique
per hospital (`409`). `PATCH` adds `is_active`. `GET /vendors` takes `is_active`.
Vendors are shared with the Inventory module when it is built.

### 9.8 Purchase orders

```
draft ──send──▶ sent ──receive──▶ received
  └──── cancel ────┘
```

`POST /api/v1/purchase-orders` creates a **draft**; `po_number` is generated:

```json
{ "vendor_id": "…", "notes": "Deliver before noon.",
  "items": [{ "medicine_id": "…", "quantity": 500, "unit_price": "1.20" }] }
```

The vendor and every medicine must be active; a medicine may appear once. The response
carries `status`, `vendor_name`, `total_amount`, `ordered_at`, `received_at` and `items[]`
with `id`, `medicine_sku`, `medicine_name`, `quantity`, `unit_price`, `total`.

`POST …/{id}/receive` — only on a `sent` order:

```json
{ "items": [
  { "po_item_id": "…", "batch_number": "PA-1", "expiry_date": "2027-08-01", "quantity": 300 },
  { "po_item_id": "…", "batch_number": "PA-2", "expiry_date": "2027-11-01", "quantity": 200,
    "cost_per_unit": "1.25" }
] }
```

One order line may be split across several batches, and what arrived may differ from what
was ordered. `cost_per_unit` defaults to the order line's price. Every batch becomes
stock at once and the order moves to `received`; it cannot be received again. An expired
batch, or an expiry that disagrees with an existing batch of that number, is a `422` and
nothing is received.

### 9.9 Not built yet

These paths from the module spec return `404`. Do not build against them:

- `GET /pharmacy/interactions/check`
- `POST /pharmacy/ai-substitute`

---

## 10. Inventory

`backend/app/api/v1/inventory.py` · `backend/app/schemas/inventory.py`

The core of [modules/09-inventory.md](modules/09-inventory.md): non-pharmacy consumables
kept per location and batch, with consumption, transfers, corrections, low-stock alerts
and purchase orders. **The AI reorder forecast is not built** — see §10.8.

### 10.1 Endpoints

All under `/api/v1/inventory`.

| Method | Path | Permission | Success |
|---|---|---|---|
| GET | `/items` | `inventory.item.read` | 200 (paginated) |
| POST | `/items` | `inventory.item.create` | 201 |
| GET | `/items/{id}` | `inventory.item.read` | 200 |
| PATCH | `/items/{id}` | `inventory.item.update` | 200 |
| GET | `/locations` | `inventory.location.read` | 200 (plain list) |
| POST | `/locations` | `inventory.location.create` | 201 |
| PATCH | `/locations/{id}` | `inventory.location.update` | 200 |
| GET | `/stock` | `inventory.stock.read` | 200 (paginated) |
| GET | `/stock/summary` | `inventory.stock.read` | 200 (paginated) |
| GET | `/movements` | `inventory.stock.read` | 200 (paginated) |
| POST | `/consume` | `inventory.consume` | 200 |
| POST | `/transfer` | `inventory.transfer` | 200 |
| POST | `/adjust` | `inventory.adjust` | 200 |
| GET | `/purchase-orders` | `inventory.po.read` | 200 (paginated) |
| POST | `/purchase-orders` | `inventory.po.create` | 201 |
| GET | `/purchase-orders/{id}` | `inventory.po.read` | 200 |
| POST | `/purchase-orders/{id}/send` | `inventory.po.update` | 200 |
| POST | `/purchase-orders/{id}/cancel` | `inventory.po.update` | 200 |
| POST | `/purchase-orders/{id}/receive` | `inventory.po.receive` | 200 |

**Quantities are decimal strings with two places** (`"4.50"`), in requests and
responses: some items are issued in fractions of a unit of measure.

### 10.2 Roles → permissions

| Permission | Hospital Admin | Inventory Manager | Nurse | Pharmacist |
|---|:--:|:--:|:--:|:--:|
| `inventory.item.read` / `.location.read` / `.stock.read` | ✅ | ✅ | ✅ | ✅ |
| `inventory.item.create` / `.update` | ✅ | ✅ | — | — |
| `inventory.location.create` / `.update` | ✅ | ✅ | — | — |
| `inventory.consume` | ✅ | ✅ | ✅ | — |
| `inventory.transfer` / `inventory.adjust` | ✅ | ✅ | — | — |
| `inventory.po.read` / `.create` / `.update` / `.receive` | ✅ | ✅ | — | — |

A nurse sees stock and records what the ward uses, and nothing else. These replace the
earlier `inventory.read` / `.create` / `.update` placeholders. `inventory.forecast.read` is
in the catalog but guards nothing yet.

### 10.3 Items and locations

`POST /inventory/items`

```json
{
  "sku": "GLOVE-M",
  "name": "Nitrile gloves, medium",
  "category": "Disposables",
  "unit_of_measure": "box of 100",
  "is_batch_tracked": false,
  "reorder_point": 20,
  "target_stock": 80
}
```

- `sku` is uppercased and unique per hospital (`409`). **`sku` and `is_batch_tracked`
  cannot be changed** after creation.
- `reorder_point` and `target_stock` are whole numbers or `null`; the target may not be
  below the reorder point (`422` naming `target_stock`). An item with no reorder point
  never alerts.
- `PATCH` takes `name`, `category`, `unit_of_measure`, `reorder_point`, `target_stock`,
  `is_active`. `GET /items` takes `q` (name prefix or exact SKU), `category`, `is_active`.

`POST /inventory/locations` — `{ "name", "code", "kind" }`, where `kind` is `ward`, `ot`,
`icu` or `store` (default). `code` is uppercased, unique and immutable. `PATCH` takes
`name`, `kind`, `is_active`. Stock can be used up in or moved out of an inactive location,
but nothing can be sent to one.

### 10.4 Reading stock

`GET /inventory/stock` — one row per **batch of an item at a location**, ordered by item,
location, then expiry. Filters: `item_id`, `location_id`, `in_stock_only` (default `true`).

```json
{
  "id": "…",
  "item_id": "…", "item_sku": "CANN-20G", "item_name": "IV cannula 20G", "unit_of_measure": "piece",
  "location_id": "…", "location_code": "STORE", "location_name": "General store",
  "batch_number": "CN-2401", "expiry_date": "2026-10-30",
  "quantity": "80.00",
  "is_expired": false
}
```

`batch_number` and `expiry_date` are `null` for an item that is not batch-tracked. An
expired row is still listed — it is physically there — but `is_expired` is true and it is
never used.

`GET /inventory/stock/summary` — one row per **active item**, hospital-wide:

```json
{
  "item": { "id": "…", "sku": "SYR-5", "name": "Syringe 5 mL", "reorder_point": 20, "target_stock": 60, "…": "…" },
  "quantity_on_hand": "20.00",
  "usable_quantity": "20.00",
  "is_low": true,
  "suggested_order_quantity": "40.00"
}
```

- `usable_quantity` leaves out expired stock; it is the number to show.
- `is_low` is `usable_quantity <= reorder_point`.
- `suggested_order_quantity` is what brings usable stock back to `target_stock` (or to the
  reorder point if no target is set); `"0.00"` when not low.
- **`?low_stock=true` is the reorder alerts panel.** It includes items with no stock at
  all. Also takes `q` and `category`.

`GET /inventory/movements` — the ledger, newest first; filters `item_id`, `location_id`,
`reason` (`received`, `consumed`, `transferred_in`, `transferred_out`, `adjusted`,
`expired`). Each entry has `quantity_change` (signed), `reason`, `batch_number`,
`department_id`, `reference_type`, `reference_id`, `note`, `moved_at`, `moved_by`.

### 10.5 Moving stock

All three return `{ "movements": […], "summary": { … } }` — the ledger entries the request
wrote, and the item's summary (§10.4) afterwards.

`POST /inventory/consume`

```json
{ "item_id": "…", "location_id": "…", "quantity": "2", "department_id": null, "note": null }
```

`POST /inventory/transfer`

```json
{ "item_id": "…", "from_location_id": "…", "to_location_id": "…", "quantity": "10" }
```

`POST /inventory/adjust`

```json
{ "item_id": "…", "location_id": "…", "quantity_change": "-3", "reason": "expired",
  "note": "Damaged in store", "batch_number": null, "expiry_date": null }
```

- Stock is taken **earliest expiry first**, never from an expired batch, and only from
  the location named — stock elsewhere does not count. `batch_number` on consume or
  transfer restricts it to one batch.
- **A shortage is a `409` and changes nothing.** `errors` is
  `{ "requested": "5.00", "available": "3.00" }`.
- A transfer keeps each batch's number and expiry, and writes a `transferred_out` and a
  `transferred_in` entry per batch sharing one `reference_id`. The two locations must
  differ (`422`).
- **Adjust** needs `note`. `reason` is `adjusted` (default) or `expired`; an `expired`
  adjustment must remove stock. A positive adjustment may create the stock row — this is
  how an opening balance is entered. A batch-tracked item needs `batch_number` and an
  untracked one must not have it (`422` naming `batch_number`). Taking a row below zero is
  a `400`.
- An unknown `item_id`, `location_id` or `department_id` is a `422` naming the field.

### 10.6 Low-stock alerts

When a consume or a write-off takes an item's hospital-wide usable stock **from above its
reorder point to at or below it**, every user who can raise a purchase order
(`inventory.po.create`) gets an in-app notification of kind `inventory.low_stock` (§7).
It fires once, on the movement that crosses the line. A transfer never alerts: it moves
nothing out of the hospital. The response's `summary.is_low` tells the person who made the
movement.

The reorder point is one number per item for the whole hospital. The module spec's rule 3
speaks of "per item per location", but its schema keeps one per item; a ward running out
while the store is full needs a transfer, not a purchase.

### 10.7 Purchase orders

Same lifecycle as Pharmacy's (§9.8) — `draft` → `sent` → `received`, or `cancelled` — but
separate orders, numbered `IPO-…`. **Vendors are the same ones** as Pharmacy's
(`GET /api/v1/vendors`, §9.7).

`POST /inventory/purchase-orders`

```json
{ "vendor_id": "…", "notes": null,
  "items": [{ "item_id": "…", "quantity": "40", "unit_price": "210.00" }] }
```

`POST /inventory/purchase-orders/{id}/receive` — only on a `sent` order:

```json
{ "location_id": "…",
  "items": [
    { "po_item_id": "…", "quantity": "40" },
    { "po_item_id": "…", "quantity": "250", "batch_number": "CN-1", "expiry_date": "2027-11-01" }
  ] }
```

Everything on the receipt goes into `location_id`, which must be active. What arrived may
differ from what was ordered, and one order line may be split across batches. A
batch-tracked item needs `batch_number` on every line. An expired batch, or an expiry that
disagrees with stock already held under that batch number, is a `422` and nothing is
received. The response is the order, with `status`, `vendor_name`, `total_amount`,
`received_location_id` and `items[]` (`item_sku`, `item_name`, `quantity`, `unit_price`,
`total`).

### 10.8 Not built yet

This path from the module spec returns `404`. Do not build against it:

- `GET /inventory/forecast`

---

## 11. Frontend ↔ backend mapping (mismatch resolution)

The audit flagged the patient contract as mismatched. It was investigated against
`API_CONTRACTS`/`05-DATABASE_DESIGN.md`, the module spec, the schemas and 944 passing
tests: **the backend contract is canonical and was not changed.** The frontend was wrong
and was corrected in `frontend/src/api/patients.ts`.

| Old frontend | Backend | Resolution |
|---|---|---|
| `name` | `first_name` + `last_name` + `full_name` | Use `full_name` for display; the create form collects both parts |
| `age: number` (input) | `date_of_birth` (input), `age` (computed output) | Form collects DOB; read `age` from the response |
| `gender: 'M' \| 'F'` | `male \| female \| other \| unspecified` | Frontend uses backend values; a `GENDER_LABELS` map handles display |
| `status: Outpatient \| Admitted \| Critical \| Discharged` | `active \| inactive` | **Dropped.** No admissions module exists; the values were invented by the mock |
| `doctor: string` | — | **Dropped.** Patients have no assigned doctor |
| `department: string` | — | **Dropped** from the patient shape; department lives on doctors |
| `?search=` | `?q=` | Renamed |
| `?pageSize=` | `?page_size=` | Renamed |
| — | `mrn` | Server-generated, read-only |

No backend field was renamed, no enum value was added, and no test was relaxed. Anything
the mock displayed that the backend does not model was removed from the UI rather than
faked.

---

## 12. Demo data

`make -C backend seed` — idempotent, safe to re-run; see
[10-DEVELOPMENT_GUIDE.md](10-DEVELOPMENT_GUIDE.md).

Seeded for the demo hospital (`demo-hospital`, timezone `Asia/Kolkata`):

- **6 departments**, one of them deactivated (Dermatology) so `include_inactive` is
  demonstrable.
- **5 doctors**, one deactivated. Four have a weekly availability schedule; the
  neurologist has a two-day leave block starting tomorrow, so the slots read model
  returns `on_leave` slots.
- **12 patients**, one deactivated. Ages 3–82, every gender enum value represented,
  varied blood groups, allergies and chronic conditions — enough to exercise `q`,
  `gender`, `age_gte`/`age_lte` and pagination.
- **14 appointments** covering all six statuses and all four types, spread across
  yesterday, today and the next two days, including two checked-in walk-ins for the
  queue. Each carries its full status history.
- **10 catalog services** across six categories — eight untaxed clinical services, one of
  them retired (`LAB-ESR`) so `is_active` is demonstrable, and two taxable non-clinical
  ones.
- **8 invoices**, covering every state the UI has to render: `paid` (settled by cash and
  UPI), `void`, `partially_paid` (the re-issue of the voided visit, part-paid by card),
  `issued` (nothing paid), a plain `draft`, a `draft` **held for discount approval**, a
  `refunded` invoice, and a `paid` invoice with a **partial refund**. They are numbered
  `INV-{year}-000001` to `000006`; the void invoice keeps its number.
- **5 payments** and **2 refunds**.
- A **10% discount approval threshold** on the demo hospital, so a small discount goes
  straight through and the seeded 20% one sits in the approval queue.
- **10 lab tests** across five categories: eight numeric tests with reference ranges
  (several with critical bounds, three with ranges that differ by sex or age), one text
  test (`URINE-ME`) and one retired test (`ESR`). **The ranges are illustrative, not a
  validated clinical dataset.** No lab orders are seeded — place one live.
- **10 medicines** (one retired) and **10 batches**, arranged so each dispensing rule can
  be shown: Paracetamol has a small batch expiring in 20 days and a large one a year out;
  Amoxicillin has one good batch and one that expired last month; Atorvastatin has only 8
  units; Pantoprazole's only batch is recalled; Insulin glargine has no stock. Plus one
  vendor. No prescriptions or purchase orders are seeded — write one live. Expiry dates
  are relative to the day the database was first seeded.
- **4 stock locations** (general store, a ward, the ICU, a theatre) and **8 inventory items**
  (one retired), with stock arranged to show each rule: syringes sit at 25 against a
  reorder point of 20, so using six trips the low-stock alert live; surgical masks are
  already low; IV cannulas have a batch expiring in 25 days that is used first; sterile
  gauze has an expired batch that is held but unusable; bed sheets have no stock at all.
  No inventory purchase orders are seeded.

The in-flight appointments are deliberately left unbilled, so completing one in a demo
drafts its invoice live (§6.10).

Appointment times land on the doctors' published slot boundaries, so a seeded booking
shows up as `booked` in `GET /doctors/{id}/slots`. `doctor@demohospital.com` is Priya
Sharma, the seeded cardiologist, so signing in as her lands on a doctor with a real
schedule.

Demo logins (development only):

| Email | Password | Role |
|---|---|---|
| `admin@demohospital.com` | `Admin@1234567` | Hospital Admin |
| `doctor@demohospital.com` | `Doctor@1234567` | Doctor |
| `reception@demohospital.com` | `Reception@1234567` | Receptionist |
| `lab@demohospital.com` | `LabTech@1234567` | Lab Technician |
| `pharmacy@demohospital.com` | `Pharmacy@1234567` | Pharmacist |
| `inventory@demohospital.com` | `Inventory@1234567` | Inventory Manager |

All seeded people are fictional. No real patient data exists in this repository.

---

## 13. Known gaps

Things the frontend will ask for that do not exist yet. Do not build against them:

- **Billing:** no invoice PDF or AI explain (§6.12). No way to delete or discard a draft
  invoice. There is no "reject" for a discount awaiting approval — the draft's owner
  lowers or removes it instead. `GET /invoices/{id}/refunds` is not in the module spec's
  endpoint list; it was added so the refund history can be shown.
- **Billing roles:** "a doctor views invoices for their patients" is implemented as *their
  own visits* — not every invoice of a patient they have seen (§6.11). And
  `invoice.payment.record.cash` is a code the module spec's §10 does not list; it was
  added to express the spec's own cash-only rule for receptionists.
- **Billing settings:** the tax rate and the discount threshold are plain keys under
  `settings.billing`, set through `PATCH /hospitals/current`. Sending `settings.billing`
  replaces that whole sub-object, so send both keys together. Nothing validates them on
  write; a malformed value is ignored on read (0% tax; every discount needs approval).
- **Two shapes of `422`.** A request-validation error (wrong type, missing field) puts a
  list in `errors`, as §1.2 shows. A rule checked by the service — an unknown
  `patient_id`, an inactive service — puts an *object* there, with the list one level
  down at `errors.errors`. This is true of every module, not only billing. Read
  `message` for display; handle both shapes if you map errors to fields.
- **Notifications:** staff only — nothing is sent to patients yet, so there is no invoice
  or appointment email (§7.7). No live push: poll `GET /notifications/unread-count`.
  `GET /notifications/unread-count` is not in the module spec's endpoint list; it was added
  so the bell does not have to fetch a page to show a number. An email can take up to ten
  seconds to leave the queue, which is inside the spec's 30-second acceptance criterion but
  not its 5-second target.
- **Laboratory:** no PDF report or AI explain (§8.8). An order must hang off an
  appointment — there is no Consultation module yet. Cancelling an order does not remove
  its charge from the invoice (§8.7). There is no way to reject one sample or cancel one
  test on an order; cancel the order and place another. A text result is never flagged,
  and nobody can override a flag. `POST /lab-orders/{id}/items/{item_id}/amend` is not in
  the module spec's endpoint list; the spec defines the permission but no route.
- **Laboratory roles:** the spec's *Lab Supervisor* is not a seeded role, so only an admin
  can release or amend (§8.2). Nurses see every lab order in the hospital, not only those
  of "their" patients — nothing records which patients a nurse is assigned to.
- **Pharmacy:** no interaction warnings and no AI substitution (§9.9). A prescription
  must hang off an appointment — there is no Consultation module yet — and cannot be
  edited once written; cancel it and write another. A dispense cannot be reversed: there
  is no return-to-stock. Nothing stops a medicine that `requires_prescription: false` from
  needing a prescription here, because there is no counter sale. Medicine lines are
  untaxed (§9.6). There is no low-stock threshold or expiring-soon list across medicines;
  stock is per medicine (§9.3). Purchase orders cannot be edited after drafting, and an
  order is received once, in one go.
- **Pharmacy roles:** the spec's *Pharmacy Admin* is not a seeded role, so only an admin
  can manage the catalog (§9.2). Any doctor can prescribe against any visit in the
  hospital, not only their own. `pharmacy.prescription.read` / `.create` are codes the
  module spec does not list; it leaves prescriptions to Consultation.
- **Inventory:** no AI reorder forecast (§10.8). The reorder point is per item for the
  whole hospital, not per location (§10.6). A low-stock alert fires once, when the point is
  crossed; nothing re-alerts while an item stays low — use the summary for that. Expired
  stock is not written off automatically; it just stops being usable until someone
  adjusts it out. There is no "request supplies" flow for ward staff, only recording
  what was used. Purchase orders cannot be edited after drafting and are received once.
  `GET /inventory/stock/summary`, `GET /inventory/movements`, `GET /inventory/items/{id}`,
  `PATCH /inventory/locations/{id}` and the purchase-order send/cancel routes are not in
  the module spec's endpoint list.
- No `sort` parameter on any of these endpoints (§1.8).
- No patient documents, timeline, or AI summary endpoints — they need object storage.
- No appointment token/queue-number field (§5.5).
- No patient admission/clinical status (§2.2).
- `metadata.request_id` is never populated on a success response (§1.2) — use the
  `X-Request-ID` header. Needs a team decision: populate it, or amend §5.1 of the
  standards doc.
- The refresh token is returned in the response body, not set as the HTTP-only cookie
  `CLAUDE.md` specifies (§1.4). Moving to a cookie is a backend contract change *and* a
  frontend change (drop the body field, send `credentials`), so it needs coordinating —
  do not half-migrate one side.

---

_Last updated: 2026-10-05. §10 (Inventory) added with the module; the then §10–12 are now
§11–13. The `inventory.read` / `.create` / `.update` placeholder codes are gone._

_Earlier on 2026-10-05: §9 (Pharmacy) added; the then §9–11 became §10–12. The `pharmacy.read` /
`pharmacy.dispense` placeholder codes are gone._

_Earlier on 2026-10-05: §8 (Laboratory) added; the then §8–10 became §9–11. The `lab.read` /
`lab.create` / `lab.update` placeholder codes are gone._

_2026-10-04: §7 (Notifications) added with the module; the then §7–9 became §8–10._

_2026-10-03: §6.7 (discounts and approval) and §6.8 (refunds) added, with
the fields and endpoints they bring; the old §6.7–6.10 are now §6.9–6.12. §5.3 changed on
the same day: `date` is the hospital's local day and `tz_offset_hours` is gone._

_2026-10-01: §6 (Billing) added with the module, and checked against the
running app and a freshly seeded database: every endpoint, permission, status code and
response shape in §6, the roles table (now §6.11) against the seeded roles, and the billing rows of the demo data section (then §8).
Sections 6–8 of the revision before that became §7–9._

_§2–5 were last re-verified on 2026-09-22 at commit `e3927e2`: every endpoint, permission,
query parameter, enum and response shape was checked against the running app, the §1.9
table against the seeded roles, and the demo data against a freshly seeded database. §1.4
was corrected then — it previously described a refresh-token cookie that the backend has
never set._
