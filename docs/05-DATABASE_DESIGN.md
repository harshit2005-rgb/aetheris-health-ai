# 05 — Database Design

**Database:** PostgreSQL 15+
**ORM:** SQLAlchemy 2.x (async)
**Migrations:** Alembic

---

## 1. Conventions

These conventions apply to **every** table without exception.

### 1.1 Primary Keys

- Every business entity uses **UUID v4** as the primary key
- Column name: `id`
- Type: `UUID`, not `SERIAL` or `BIGSERIAL`
- Generated in application code (`uuid.uuid4()`) so we can log the ID before writing

### 1.2 Naming

- Tables: `snake_case`, **plural** (`patients`, `appointments`, `medical_records`)
- Columns: `snake_case`
- Foreign keys: `<table_singular>_id` (`patient_id`, `doctor_id`, `hospital_id`)
- Indexes: `ix_<table>_<column(s)>`
- Unique constraints: `uq_<table>_<column(s)>`
- Check constraints: `ck_<table>_<rule>`

### 1.3 Audit Columns (every table)

```
created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
created_by    UUID NULL  REFERENCES users(id)
updated_by    UUID NULL  REFERENCES users(id)
deleted_at    TIMESTAMPTZ NULL
deleted_by    UUID NULL  REFERENCES users(id)
```

- `updated_at` is set by a trigger or SQLAlchemy `onupdate=`
- Soft delete is the default. Never `DELETE FROM` a business table unless explicitly authorized by the admin workflow.
- `created_by` / `updated_by` are `NULL` only for system-seeded rows.

### 1.4 Multi-tenancy

- Every business table has a `hospital_id UUID NOT NULL REFERENCES hospitals(id)` column
- Every service layer read/write filters by `hospital_id` derived from the authenticated user's context
- We do **not** rely on database roles for tenant isolation in MVP; we rely on service-layer enforcement, backed by row-level security in v2.2+

### 1.5 Types

- Text: `VARCHAR(n)` when length is bounded; `TEXT` otherwise
- Enums: PostgreSQL `ENUM` types, migrated via Alembic
- JSON: `JSONB`, never `JSON`
- Money: `NUMERIC(15, 2)` — never `FLOAT` for money, ever
- Dates: `TIMESTAMPTZ` (always UTC in DB, display in user tz)
- Booleans: `BOOLEAN NOT NULL DEFAULT false`

### 1.6 Nullability

- Default is `NOT NULL`. Justify every `NULL`.
- `NULL` is a business signal, not a "we didn't get to it" signal.

### 1.7 Indexes

- Foreign keys: always indexed
- Frequently searched columns: indexed
- Composite indexes for common query patterns (e.g. `(hospital_id, appointment_date)`)
- Partial indexes for soft-delete-aware queries: `WHERE deleted_at IS NULL`

### 1.8 Constraints

- Every foreign key has an explicit `ON DELETE` policy
- `CASCADE` only for owned children (e.g. `appointment_id` on `appointment_status_history`)
- `RESTRICT` for medical records; we do not allow accidental deletion of clinical data

---

## 2. Core Domain Tables (MVP)

Full DDL is in the migrations. This is the summary reference.

### 2.1 `hospitals`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR(200) NOT NULL | |
| slug | VARCHAR(100) UNIQUE NOT NULL | for URLs |
| address | JSONB NOT NULL | structured address |
| phone | VARCHAR(20) | |
| email | VARCHAR(200) | |
| tax_id | VARCHAR(50) | |
| currency | VARCHAR(3) NOT NULL DEFAULT 'INR' | ISO 4217 |
| timezone | VARCHAR(50) NOT NULL DEFAULT 'Asia/Kolkata' | IANA |
| locale | VARCHAR(10) NOT NULL DEFAULT 'en-IN' | |
| logo_url | TEXT | |
| settings | JSONB NOT NULL DEFAULT '{}' | feature flags, working hours, etc. |
| is_active | BOOLEAN NOT NULL DEFAULT true | |
| + audit columns | | |

### 2.2 `users`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| hospital_id | UUID FK hospitals(id) | NULL only for Super Admin |
| email | VARCHAR(200) NOT NULL | unique per hospital |
| phone | VARCHAR(20) | |
| password_hash | TEXT NOT NULL | Argon2 |
| first_name | VARCHAR(100) NOT NULL | |
| last_name | VARCHAR(100) NOT NULL | |
| status | user_status ENUM | active, suspended, invited |
| last_login_at | TIMESTAMPTZ | |
| password_changed_at | TIMESTAMPTZ | |
| failed_login_attempts | INT NOT NULL DEFAULT 0 | |
| locked_until | TIMESTAMPTZ | |
| mfa_enabled | BOOLEAN NOT NULL DEFAULT false | |
| mfa_secret | TEXT | encrypted at rest |
| + audit columns | | |

**Indexes:** `uq_users_hospital_email (hospital_id, email)`, `ix_users_phone`

### 2.3 `roles`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| hospital_id | UUID FK hospitals(id) | NULL for system roles |
| name | VARCHAR(100) NOT NULL | |
| description | TEXT | |
| is_system | BOOLEAN NOT NULL DEFAULT false | system roles cannot be deleted |
| + audit columns | | |

### 2.4 `permissions`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| code | VARCHAR(100) UNIQUE NOT NULL | e.g. `patient.create`, `billing.approve_discount` |
| description | TEXT | |
| module | VARCHAR(50) NOT NULL | |

Seeded once. Not user-editable.

### 2.5 `role_permissions`

| Column | Type | Notes |
|---|---|---|
| role_id | UUID FK | PK part |
| permission_id | UUID FK | PK part |

Composite PK `(role_id, permission_id)`.

### 2.6 `user_roles`

| Column | Type | Notes |
|---|---|---|
| user_id | UUID FK | PK part |
| role_id | UUID FK | PK part |
| assigned_at | TIMESTAMPTZ NOT NULL | |
| assigned_by | UUID FK users(id) | |

### 2.7 `patients`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| hospital_id | UUID FK hospitals(id) NOT NULL | |
| mrn | VARCHAR(30) NOT NULL | Medical Record Number, unique per hospital |
| first_name | VARCHAR(100) NOT NULL | |
| last_name | VARCHAR(100) NOT NULL | |
| date_of_birth | DATE NOT NULL | |
| gender | gender_enum NOT NULL | male / female / other / unspecified |
| blood_group | VARCHAR(5) | |
| phone | VARCHAR(20) | |
| email | VARCHAR(200) | |
| address | JSONB | |
| emergency_contact | JSONB | name, phone, relation |
| marital_status | VARCHAR(20) | |
| occupation | VARCHAR(100) | |
| allergies | JSONB NOT NULL DEFAULT '[]' | array of allergy objects |
| chronic_conditions | JSONB NOT NULL DEFAULT '[]' | |
| current_medications | JSONB NOT NULL DEFAULT '[]' | |
| notes | TEXT | free-form |
| + audit columns | | |

**Indexes:** `uq_patients_hospital_mrn (hospital_id, mrn)`, `ix_patients_phone`, `ix_patients_name (hospital_id, last_name, first_name)`, `ix_patients_dob (hospital_id, date_of_birth)`

### 2.8 `doctors`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK users(id) UNIQUE NOT NULL | doctor is a user + doctor row |
| hospital_id | UUID FK hospitals(id) NOT NULL | |
| specialization | VARCHAR(100) NOT NULL | |
| qualifications | JSONB NOT NULL DEFAULT '[]' | |
| license_number | VARCHAR(50) NOT NULL | |
| consultation_fee | NUMERIC(15,2) NOT NULL DEFAULT 0 | |
| bio | TEXT | |
| languages | JSONB NOT NULL DEFAULT '[]' | |
| + audit columns | | |

### 2.9 `doctor_availability`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| doctor_id | UUID FK doctors(id) NOT NULL | |
| day_of_week | INT NOT NULL | 0=Mon .. 6=Sun |
| start_time | TIME NOT NULL | |
| end_time | TIME NOT NULL | |
| slot_duration_minutes | INT NOT NULL DEFAULT 15 | |
| + audit columns | | |

Check: `end_time > start_time`.

### 2.10 `doctor_leaves`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| doctor_id | UUID FK doctors(id) NOT NULL | |
| starts_at | TIMESTAMPTZ NOT NULL | |
| ends_at | TIMESTAMPTZ NOT NULL | |
| reason | VARCHAR(200) | |
| + audit columns | | |

### 2.11 `appointments`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| hospital_id | UUID FK hospitals(id) NOT NULL | |
| patient_id | UUID FK patients(id) NOT NULL | |
| doctor_id | UUID FK doctors(id) NOT NULL | |
| scheduled_start | TIMESTAMPTZ NOT NULL | |
| scheduled_end | TIMESTAMPTZ NOT NULL | |
| status | appointment_status ENUM NOT NULL | booked / checked_in / in_progress / completed / cancelled / no_show |
| type | appointment_type ENUM NOT NULL | new / follow_up / walk_in / emergency |
| reason | TEXT | |
| notes | TEXT | reception notes at booking |
| cancelled_reason | TEXT | |
| checked_in_at | TIMESTAMPTZ | |
| started_at | TIMESTAMPTZ | |
| completed_at | TIMESTAMPTZ | |
| + audit columns | | |

**Indexes:** `ix_appointments_hospital_scheduled_start (hospital_id, scheduled_start)`, `ix_appointments_doctor_scheduled_start (doctor_id, scheduled_start)`, `ix_appointments_patient (patient_id)`

### 2.12 `appointment_status_history`

Every status change is recorded here. Immutable.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| appointment_id | UUID FK NOT NULL | |
| from_status | appointment_status | |
| to_status | appointment_status NOT NULL | |
| changed_by | UUID FK users(id) NOT NULL | |
| changed_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| reason | TEXT | |

### 2.13 `consultations`

Clinical documentation created during an appointment.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| appointment_id | UUID FK appointments(id) NOT NULL | |
| doctor_id | UUID FK doctors(id) NOT NULL | |
| patient_id | UUID FK patients(id) NOT NULL | |
| chief_complaint | TEXT | |
| history | TEXT | |
| examination | TEXT | |
| diagnosis | JSONB NOT NULL DEFAULT '[]' | array of {code, description} |
| plan | TEXT | |
| vitals | JSONB | |
| ai_summary | TEXT | if AI drafted |
| ai_summary_model | VARCHAR(100) | provider/model that drafted |
| ai_summary_accepted | BOOLEAN | doctor accepted vs edited |
| finalized_at | TIMESTAMPTZ | once finalized, edits become addenda |
| + audit columns | | |

### 2.14 `consultation_addenda`

Never edit a finalized consultation in place. Add an addendum.

### 2.15 `prescriptions`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| consultation_id | UUID FK NOT NULL | |
| medicine_id | UUID FK medicines(id) | NULL for free-text |
| medicine_name | VARCHAR(200) NOT NULL | denormalized snapshot |
| dosage | VARCHAR(100) NOT NULL | |
| frequency | VARCHAR(100) NOT NULL | |
| duration_days | INT | |
| instructions | TEXT | |
| + audit columns | | |

### 2.16 `services` (billable)

Catalog of services a hospital bills for.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| hospital_id | UUID FK NOT NULL | |
| code | VARCHAR(50) NOT NULL | |
| name | VARCHAR(200) NOT NULL | |
| category | VARCHAR(100) | |
| price | NUMERIC(15,2) NOT NULL | |
| taxable | BOOLEAN NOT NULL DEFAULT true | |
| is_active | BOOLEAN NOT NULL DEFAULT true | |
| + audit columns | | |

### 2.17 `invoices`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| hospital_id | UUID FK NOT NULL | |
| patient_id | UUID FK NOT NULL | |
| appointment_id | UUID FK | may be NULL for ad-hoc billing |
| invoice_number | VARCHAR(30) NOT NULL | unique per hospital, sequential |
| subtotal | NUMERIC(15,2) NOT NULL | |
| tax_amount | NUMERIC(15,2) NOT NULL DEFAULT 0 | |
| discount_amount | NUMERIC(15,2) NOT NULL DEFAULT 0 | |
| discount_reason | VARCHAR(200) | |
| discount_approved_by | UUID FK users(id) | |
| total | NUMERIC(15,2) NOT NULL | |
| amount_paid | NUMERIC(15,2) NOT NULL DEFAULT 0 | |
| status | invoice_status ENUM NOT NULL | draft, issued, partially_paid, paid, void, refunded |
| notes | TEXT | |
| issued_at | TIMESTAMPTZ | |
| voided_at | TIMESTAMPTZ | |
| + audit columns | | |

**Unique:** `(hospital_id, invoice_number)`.

### 2.18 `invoice_items`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| invoice_id | UUID FK NOT NULL ON DELETE CASCADE | |
| service_id | UUID FK services(id) | |
| description | VARCHAR(200) NOT NULL | denormalized |
| quantity | NUMERIC(10,2) NOT NULL DEFAULT 1 | |
| unit_price | NUMERIC(15,2) NOT NULL | |
| tax_rate | NUMERIC(5,2) NOT NULL DEFAULT 0 | |
| line_total | NUMERIC(15,2) NOT NULL | |

### 2.19 `payments`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| invoice_id | UUID FK NOT NULL | |
| amount | NUMERIC(15,2) NOT NULL | |
| method | payment_method ENUM NOT NULL | cash, card, upi, bank_transfer, insurance |
| reference | VARCHAR(100) | txn id, cheque number, UPI ref |
| received_by | UUID FK users(id) NOT NULL | |
| received_at | TIMESTAMPTZ NOT NULL | |
| idempotency_key | VARCHAR(100) NOT NULL UNIQUE | prevents double-recording |
| notes | TEXT | |
| + audit columns | | |

### 2.20 `notifications`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| recipient_user_id | UUID FK users(id) NOT NULL | |
| kind | VARCHAR(50) NOT NULL | |
| title | VARCHAR(200) NOT NULL | |
| body | TEXT NOT NULL | |
| link | TEXT | |
| read_at | TIMESTAMPTZ | |
| sent_email | BOOLEAN NOT NULL DEFAULT false | |
| sent_sms | BOOLEAN NOT NULL DEFAULT false | |
| + audit columns | | |

### 2.21 `audit_logs`

**Immutable.** No updates, no deletes.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| hospital_id | UUID FK | may be NULL for platform events |
| actor_user_id | UUID FK | may be NULL for system |
| actor_type | VARCHAR(20) NOT NULL | user / system / ai |
| action | VARCHAR(100) NOT NULL | e.g. `patient.created` |
| target_type | VARCHAR(50) | |
| target_id | UUID | |
| before | JSONB | state before, optional |
| after | JSONB | state after, optional |
| ip_address | INET | |
| user_agent | TEXT | |
| request_id | UUID | correlates with logs |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**Indexes:** `ix_audit_hospital_created (hospital_id, created_at DESC)`, `ix_audit_actor (actor_user_id)`, `ix_audit_target (target_type, target_id)`

### 2.22 `ai_interactions`

Every AI call is logged for observability, cost tracking, and evaluation.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| hospital_id | UUID FK | |
| user_id | UUID FK | |
| module | VARCHAR(50) NOT NULL | which module invoked AI |
| use_case | VARCHAR(100) NOT NULL | e.g. `patient.summarize` |
| prompt_id | VARCHAR(100) NOT NULL | template id + version |
| provider | VARCHAR(50) NOT NULL | anthropic, groq, openai |
| model | VARCHAR(100) NOT NULL | |
| input_tokens | INT | |
| output_tokens | INT | |
| latency_ms | INT | |
| status | VARCHAR(20) NOT NULL | success, error, rate_limited |
| error_message | TEXT | |
| cost_estimate | NUMERIC(10,6) | in USD |
| request_id | UUID | |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**Never** store the full prompt or response in this table by default — separate opt-in storage with retention policies for those.

---

## 3. Enum Types (Postgres)

```sql
CREATE TYPE user_status AS ENUM ('active', 'suspended', 'invited');
CREATE TYPE gender_enum AS ENUM ('male', 'female', 'other', 'unspecified');
CREATE TYPE appointment_status AS ENUM
  ('booked', 'checked_in', 'in_progress', 'completed', 'cancelled', 'no_show');
CREATE TYPE appointment_type AS ENUM ('new', 'follow_up', 'walk_in', 'emergency');
CREATE TYPE invoice_status AS ENUM
  ('draft', 'issued', 'partially_paid', 'paid', 'void', 'refunded');
CREATE TYPE payment_method AS ENUM
  ('cash', 'card', 'upi', 'bank_transfer', 'insurance');
```

More enums per module are declared in their respective migrations.

---

## 4. Reference Data (Seeded)

Populated by a seed script during initial setup:

- Permissions catalog (~50 permissions across modules)
- System roles (Super Admin, Hospital Admin, Doctor, Nurse, Receptionist, Billing Staff, Lab Tech, Pharmacist, Inventory Manager, Patient)
- Role → permission mapping for system roles
- Sample services catalog (starter list per hospital, editable)

---

## 5. Migration Policy

- Every schema change is an Alembic migration
- No manual `ALTER TABLE` in production
- Migrations are reversible where possible
- Data migrations run separately from schema migrations
- Migration review is part of PR review — one non-author must approve
- Backwards-compatible migrations preferred (add nullable column, backfill, then make NOT NULL in a follow-up)

---

## 6. Query Patterns

### 6.1 Standard filters
Every list query filters by `hospital_id` and `deleted_at IS NULL`.

### 6.2 Pagination
Cursor pagination for large tables; offset pagination acceptable for small admin lists.

### 6.3 Soft delete
Repositories automatically append `WHERE deleted_at IS NULL` unless explicitly asked to include deleted rows.

### 6.4 N+1
`selectinload` / `joinedload` for known access patterns. Every service that iterates over a list and touches a related entity gets an eager loader.

---

## 7. Backups

- Daily full backup + WAL streaming
- Retention: 30 days daily, 12 months monthly
- Restoration drills quarterly
- Backups stored encrypted at rest, off-site (S3-compatible)

---

## 8. Compliance Notes

- Field-level encryption for MRN, phone, and any PII in exported reports (v2.2)
- Row-level security policies enabled once multi-tenant hardening ships (v2.2)
- Retention policies per data category to be documented in a separate compliance module (v2.3)

---

## 9. Extending the Schema

To add a new table:
1. Update the module spec first (this includes the schema section)
2. Get the schema section reviewed
3. Create the Alembic migration
4. Add SQLAlchemy model with all conventions from Section 1
5. Add repository with soft-delete-aware queries
6. Wire into the service layer

No schema change is merged without an updated module spec.
