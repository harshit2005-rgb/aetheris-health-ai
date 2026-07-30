# Module 14: Hospital Settings & Multi-Tenancy

**Priority:** 🟢 MVP (core), 🟡 v2.1+ (advanced tenant features)
**Owner:** Platform Team
**Depends on:** Authentication, User Management

---

## 1. Purpose

Every piece of data in Aetheris belongs to a **hospital (tenant)**. This module owns the hospital record itself: its identity, configuration, branding, feature flags, working hours, and format rules (MRN, invoice number, currency, timezone). It also enforces the **multi-tenant isolation guarantee** that no user of Hospital A can ever see data from Hospital B.

This is the "settings backbone" the rest of the platform reads from.

---

## 2. Scope

### In Scope (MVP)
- Hospital record CRUD (create/read/update; no hard delete)
- Hospital metadata: name, address, contact, registration number, timezone, currency, locale
- Configurable formats: MRN pattern, invoice number pattern
- Working hours (per hospital)
- Branding: logo, primary color, letterhead header/footer
- Tax configuration (GST rate, GSTIN)
- Feature flags per hospital (enable/disable optional modules)
- Superadmin-only hospital provisioning
- Hospital admin can edit their own hospital's settings
- Departments (organisational units: Cardiology, Radiology, Emergency) — CRUD,
  and the assignment target for doctors (feature 5.2)

### In Scope (v2.1+)
- Multi-branch support (one hospital, multiple physical locations)
- Custom fields per hospital (extensible attributes)
- Localization (multi-language UI per hospital)
- Custom email templates per hospital
- Domain/subdomain per hospital (e.g., `apollo.aetheris.health`)

### Out of Scope
- Cross-tenant reporting (Superadmin analytics is a separate future module)
- Tenant-level billing/invoicing (SaaS subscription — separate future module)
- White-label reseller support

---

## 3. Personas & Permissions

| Role | Read own hospital | Edit own hospital | Provision new hospital | Read all hospitals |
|------|-------------------|-------------------|------------------------|--------------------|
| Superadmin (platform) | ✅ | ✅ | ✅ | ✅ |
| Hospital Admin | ✅ | ✅ (limited fields) | ❌ | ❌ |
| All other roles | ✅ (public fields only) | ❌ | ❌ | ❌ |

Superadmin is a platform-level role (not tied to a hospital). Only Superadmin can create new hospitals.

---

## 4. Business Rules

1. **Multi-tenant isolation is absolute.** Every table with a `hospital_id` column MUST filter by the caller's `hospital_id` at the repository layer. There are no exceptions and no admin overrides at the hospital-user level.
2. A hospital record is **never hard-deleted**. Deactivated hospitals are marked `is_active = false`; all their users lose login access immediately.
3. `slug` (URL-safe hospital identifier) is unique and immutable after creation.
4. `timezone` must be a valid IANA timezone (e.g., `Asia/Kolkata`). All datetimes in the hospital's UI are rendered in this zone.
5. `currency` is an ISO 4217 code (e.g., `INR`). All monetary values in the hospital are stored in the minor unit or NUMERIC(15,2) and displayed with this currency.
6. Changing `mrn_pattern` or `invoice_number_pattern` affects only **future** records. Existing MRNs and invoice numbers are never rewritten.
7. Feature flags default to a platform-wide default; a hospital can override individually.
8. Only Superadmin can toggle feature flags that gate paid features (e.g., AI beyond free tier).
9. `working_hours` are informational for staff scheduling and appointment slotting; enforcement lives in Appointment Management.
10. Branding assets (logo) are stored in object storage; only their URLs live in the DB.
11. Department `code` and `name` are **unique per hospital**, compared case-insensitively. `code` is normalised to uppercase on write.
12. A department is **never hard-deleted**. Deactivation is a soft delete, so historical doctor and appointment references stay resolvable.
13. A department **cannot be deactivated while active doctors are assigned to it**. The caller reassigns or deactivates those doctors first.
14. Departments are strictly tenant-scoped. A department belongs to exactly one hospital and is never shared across tenants.

---

## 5. Workflow: Provisioning a New Hospital

1. Superadmin submits `POST /hospitals` with: name, slug, timezone, currency, contact email, initial admin user details.
2. System validates slug uniqueness, IANA timezone, ISO currency code.
3. In a single transaction:
   - Create `hospitals` row (`is_active = true`).
   - Create initial `users` row with role `hospital_admin` and hospital_id linking to new hospital.
   - Create default `roles` and default `permission` assignments for the hospital.
   - Seed default `notification_templates`, `services` catalog placeholders, etc.
4. Send invitation email to initial admin with password setup link.
5. Return created hospital.
6. Audit log: `hospital_provisioned` with actor=Superadmin.

If any step fails, the entire transaction rolls back — no orphaned hospitals.

---

## 6. Functional Requirements

- FR-1: Superadmin can provision, deactivate, and reactivate hospitals.
- FR-2: Hospital Admin can update their hospital's editable fields.
- FR-3: All users can read a limited public view of their own hospital (name, logo, contact) for UI display.
- FR-4: The system exposes a `GET /hospitals/current` endpoint that returns the authenticated user's hospital context.
- FR-5: Feature flags are evaluated server-side; disabled features return 403/404 on their endpoints.
- FR-6: Changing timezone re-renders UI timestamps immediately on next page load.
- FR-7: Deactivating a hospital revokes all sessions of its users (refresh tokens invalidated).
- FR-8: Branding (logo URL, primary color, letterhead) is served to authenticated frontend on login.

---

## 7. Non-Functional Requirements

- NFR-1: `GET /hospitals/current` must respond in <50 ms (cached in Redis per hospital, invalidated on write).
- NFR-2: Feature flag evaluation must be sub-millisecond in the request path (in-memory cache with 60s TTL).
- NFR-3: Hospital list for Superadmin paginates at 50 per page.
- NFR-4: Logo uploads capped at 2 MB, must be PNG/JPG/SVG, dimensions ≤ 1024×1024.

---

## 8. Database Design

### Table: `hospitals`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default uuid_generate_v4() | |
| slug | VARCHAR(50) | UNIQUE, NOT NULL | URL-safe, immutable |
| name | VARCHAR(255) | NOT NULL | Legal name |
| display_name | VARCHAR(255) | NULL | Friendly name shown in UI |
| registration_number | VARCHAR(100) | NULL | Govt registration |
| address_line1 | VARCHAR(255) | NOT NULL | |
| address_line2 | VARCHAR(255) | NULL | |
| city | VARCHAR(100) | NOT NULL | |
| state | VARCHAR(100) | NOT NULL | |
| country | VARCHAR(2) | NOT NULL | ISO 3166-1 alpha-2 |
| postal_code | VARCHAR(20) | NOT NULL | |
| phone | VARCHAR(20) | NOT NULL | E.164 |
| email | VARCHAR(255) | NOT NULL | Primary contact |
| website | VARCHAR(255) | NULL | |
| timezone | VARCHAR(50) | NOT NULL, default 'Asia/Kolkata' | IANA |
| currency | CHAR(3) | NOT NULL, default 'INR' | ISO 4217 |
| locale | VARCHAR(10) | NOT NULL, default 'en-IN' | BCP 47 |
| mrn_pattern | VARCHAR(50) | NOT NULL, default 'MRN-{YYYY}-{SEQ:6}' | Template |
| invoice_number_pattern | VARCHAR(50) | NOT NULL, default 'INV-{YYYY}-{SEQ:6}' | Template |
| gst_number | VARCHAR(20) | NULL | GSTIN |
| gst_rate | NUMERIC(5,2) | NOT NULL, default 0 | Percent |
| logo_url | VARCHAR(500) | NULL | Object storage URL |
| primary_color | VARCHAR(7) | NOT NULL, default '#0EA5E9' | Hex |
| letterhead_header | TEXT | NULL | HTML for reports |
| letterhead_footer | TEXT | NULL | HTML for reports |
| is_active | BOOLEAN | NOT NULL, default true | Soft-deactivation |
| activated_at | TIMESTAMPTZ | NOT NULL, default now() | |
| deactivated_at | TIMESTAMPTZ | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL, default now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, default now() | |
| created_by | UUID | FK users.id, NULL | Superadmin who created |

Indexes: `slug` (unique), `is_active` (partial index for active hospitals).

### Table: `hospital_working_hours`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| hospital_id | UUID | FK hospitals.id, NOT NULL |
| day_of_week | SMALLINT | NOT NULL, 0=Sunday..6=Saturday |
| open_time | TIME | NULL (NULL = closed that day) |
| close_time | TIME | NULL |
| is_24h | BOOLEAN | NOT NULL, default false |

Unique constraint: `(hospital_id, day_of_week)`.

### Table: `hospital_feature_flags`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| hospital_id | UUID | FK hospitals.id, NOT NULL |
| flag_key | VARCHAR(100) | NOT NULL |
| is_enabled | BOOLEAN | NOT NULL |
| enabled_by | UUID | FK users.id, NULL |
| enabled_at | TIMESTAMPTZ | NOT NULL, default now() |
| notes | TEXT | NULL |

Unique constraint: `(hospital_id, flag_key)`.

Well-known flag keys (documented in `/backend/app/core/feature_flags.py`):
- `ai.assistant.enabled`
- `ai.mcp.enabled`
- `module.laboratory.enabled`
- `module.pharmacy.enabled`
- `module.inventory.enabled`
- `notifications.sms.enabled`
- `billing.online_payments.enabled`

### Table: `hospital_settings_history` (audit)

Every mutation to `hospitals` row creates one row here with before/after JSON. Immutable (see Audit Logs module).

### Table: `departments`

Canonical definition lives in `05-DATABASE_DESIGN.md` §2.23; repeated here
because departments are configured from the hospital settings surface.

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| hospital_id | UUID | FK hospitals.id, NOT NULL |
| code | VARCHAR(20) | NOT NULL, uppercase, unique per hospital |
| name | VARCHAR(150) | NOT NULL, unique per hospital (case-insensitive) |
| description | TEXT | NULL |
| phone_extension | VARCHAR(10) | NULL |
| email | VARCHAR(200) | NULL |
| location | VARCHAR(150) | NULL |
| + audit + soft-delete columns | | |

Unique constraints: `(hospital_id, code)`, `(hospital_id, lower(name))`.
Check constraint: `ck_departments_code_format`.

`head_doctor_id UUID FK doctors.id NULL` is added by a follow-up migration in
the Doctor Management module — `doctors` does not exist when this table is
created, and the reference runs both ways.

---

## 9. API Design

### Public (any authenticated user)

- `GET /api/v1/hospitals/current` → returns caller's hospital (public + branding fields).
- `GET /api/v1/hospitals/current/feature-flags` → returns evaluated flags for caller's hospital.

### Hospital Admin

- `GET /api/v1/hospitals/current/full` → returns all fields.
- `PATCH /api/v1/hospitals/current` → update editable fields (name, display_name, address, phone, email, website, logo_url, primary_color, letterhead_*, working_hours). **Cannot** change: slug, timezone, currency, gst_number without Superadmin approval (v2.1+).
- `PUT /api/v1/hospitals/current/working-hours` → replace working hours.
- `POST /api/v1/hospitals/current/logo` → multipart logo upload.

### Superadmin (platform-level)

- `POST /api/v1/admin/hospitals` → provision new hospital.
- `GET /api/v1/admin/hospitals` → list all hospitals (paginated).
- `GET /api/v1/admin/hospitals/{id}` → read any hospital.
- `PATCH /api/v1/admin/hospitals/{id}` → update any field including restricted ones.
- `POST /api/v1/admin/hospitals/{id}/deactivate` → soft-deactivate.
- `POST /api/v1/admin/hospitals/{id}/reactivate` → reactivate.
- `PUT /api/v1/admin/hospitals/{id}/feature-flags/{flag_key}` → toggle a flag.

### Departments

- `POST /api/v1/departments` → create. 409 on duplicate `code` or `name`.
- `GET /api/v1/departments` → list / search (`q`, `include_inactive`, paginated).
- `GET /api/v1/departments/{id}` → read one.
- `PATCH /api/v1/departments/{id}` → partial update.
- `DELETE /api/v1/departments/{id}` → soft-deactivate. 409 while doctors are assigned.
- `POST /api/v1/departments/{id}/activate` → reactivate.

All endpoints follow the standard response envelope (see `06-API_STANDARDS.md`).

---

## 10. Permissions

| Permission | Description | Default roles |
|------------|-------------|---------------|
| `hospital.read` | Read own hospital settings | All authenticated |
| `hospital.update` | Edit own hospital editable fields | Hospital Admin |
| `hospital.branding.update` | Change logo/colors/letterhead | Hospital Admin |
| `hospital.feature_flags.read` | View flags | Hospital Admin |
| `platform.hospital.provision` | Create new hospitals | Superadmin only |
| `platform.hospital.deactivate` | Deactivate hospitals | Superadmin only |
| `platform.feature_flags.toggle` | Toggle any hospital's flags | Superadmin only |
| `department.read` | List and read departments | All authenticated |
| `department.create` | Create departments | Hospital Admin |
| `department.update` | Edit and reactivate departments | Hospital Admin |
| `department.delete` | Deactivate departments | Hospital Admin |

---

## 11. Validation Rules

- `slug`: `^[a-z0-9][a-z0-9-]{2,48}[a-z0-9]$`, must be unique, cannot be a reserved word (`admin`, `api`, `www`, `app`, etc.).
- `timezone`: must be in `pytz.all_timezones`.
- `currency`: must be an ISO 4217 code from the maintained list.
- `country`: must be a valid ISO 3166-1 alpha-2 code.
- `email`: RFC 5322.
- `phone`: E.164 format.
- `primary_color`: `^#[0-9A-Fa-f]{6}$`.
- `mrn_pattern` / `invoice_number_pattern`: must contain a `{SEQ:N}` placeholder; may contain `{YYYY}`, `{YY}`, `{MM}`, `{DD}`.
- `gst_rate`: 0.00–100.00.
- Working hours: `close_time > open_time` unless `is_24h = true`.
- Logo file: PNG/JPG/SVG only, ≤ 2 MB, dimensions ≤ 1024×1024 (validated server-side after upload).
- `department.code`: `^[A-Z0-9][A-Z0-9_-]{1,19}$`, uppercase-normalised on write, unique per hospital (case-insensitive).
- `department.name`: 2–150 chars, non-blank, unique per hospital (case-insensitive).
- `department.email`: RFC 5322 subset. Optional.
- `department.phone_extension`: 1–10 chars, digits and `-` only. Optional.
- `department.location`: ≤ 150 chars. Optional.

---

## 12. UI Requirements

### Settings Page (Hospital Admin)

- **General tab:** name, display name, address, contact, timezone (read-only for hospital admin), currency (read-only), locale.
- **Branding tab:** logo upload (with preview), primary color picker, letterhead header/footer WYSIWYG editor.
- **Formats tab:** MRN pattern, invoice pattern with live preview of next number.
- **Tax tab:** GSTIN, GST rate.
- **Working Hours tab:** grid of 7 days with open/close time pickers, 24h toggle per day, "Closed" toggle.
- **Feature Flags tab:** list of flags with status (read-only for hospital admin; only Superadmin can toggle from platform panel).

### Superadmin Panel

- **Hospitals list:** table with slug, name, active status, created date, user count. Filter by active/inactive.
- **Provision form:** all required fields + initial admin user email/name.
- **Hospital detail:** all tabs above plus deactivate/reactivate action and feature flag toggle controls.

Save actions on all tabs are debounced (no auto-save). Show optimistic UI with rollback on error.

---

## 13. AI Integration Points

- 🤖 **AI-generated hospital description**: Superadmin can request a draft About Us blurb from hospital metadata for the letterhead. Reviewed and edited before persist.
- 🤖 **Anomaly detection** (v2.2+): AI flags unusual configuration changes (e.g., MRN pattern changed mid-day, feature flag toggled at 3am) for Superadmin review.

No AI writes to this table without human approval. Configuration is too critical.

---

## 14. Edge Cases

- **Slug collision on provisioning** → return 409 with specific error_code `hospital.slug.taken`.
- **Timezone change on active hospital** → mid-day change causes scheduled jobs to shift. Warn admin explicitly in UI. Only Superadmin can change.
- **Currency change** → forbidden after any invoice exists in the hospital. Enforce with pre-check.
- **Deactivating a hospital with active sessions** → all refresh tokens for that hospital's users are invalidated in the same transaction; users are logged out on next request.
- **Logo upload fails after DB update** → transaction rolls back; `logo_url` stays at old value.
- **Feature flag toggled off while requests are in flight** → in-progress requests complete; new requests are blocked. Cache TTL (60s) means max 60s propagation delay — acceptable.
- **Working hours with `is_24h = true` and non-null open/close** → normalize: set both to NULL.
- **Reactivating a deactivated hospital** → allowed. Users must reset their password if last activity > 90 days (security).
- **Concurrent edits to hospital settings** → last-write-wins with optimistic concurrency (etag on GET, if-match on PATCH). Return 409 on conflict.

---

## 15. Cross-Module Dependencies

- **Authentication**: JWT payload contains `hospital_id`. Login rejected if hospital is inactive.
- **User Management**: every user belongs to exactly one hospital. Hospital deactivation cascades to sessions.
- **All modules with `hospital_id`**: patients, doctors, appointments, invoices, notifications, audit logs, AI sessions, etc. Repository base class enforces the filter.
- **Patient Management**: reads `mrn_pattern` to generate new MRNs.
- **Billing**: reads `invoice_number_pattern`, `currency`, `gst_rate`, `gst_number`.
- **Notifications**: reads `hospital_name`, `logo_url` for email/SMS templates.
- **Reports & Dashboard**: reads branding for PDF exports.
- **AI Assistant**: reads feature flags (`ai.assistant.enabled`, `ai.mcp.enabled`) and hospital budget.
- **Doctor Management**: doctors are assigned to a department (`doctors.department_id`). A department cannot be deactivated while it has active doctors; Doctor Management supplies that assignment count.

---

## 16. Testing Requirements

### Unit tests
- Slug validation regex.
- MRN pattern parser (all placeholder combinations).
- Invoice pattern parser.
- Timezone validation.
- Currency validation.
- Working hours validation (24h vs specific times).
- Feature flag evaluation with defaults.
- Department `code` normalisation and format validation.
- Department deactivation guard: blocks with assigned doctors, clears without.

### Repository tests
- Hospital CRUD.
- `get_current_hospital(user_id)` returns correct row.
- Feature flag upsert.
- Department CRUD, case-insensitive uniqueness, `hospital_id` filtering on every method.

### API tests
- Superadmin can provision; Hospital Admin cannot.
- Hospital Admin can PATCH allowed fields; cannot PATCH slug/timezone/currency.
- Deactivation invalidates refresh tokens.
- 404 when hospital not found; 403 when accessing another hospital.
- Department CRUD happy paths; 409 on duplicate `code`/`name`; 409 on deactivating a department with assigned doctors; cross-tenant read returns 404.

### Integration tests
- **Multi-tenant isolation**: create Hospital A and B, create patients in each, verify Hospital A's admin cannot query Hospital B's patients even by direct ID.
- Provisioning creates initial admin, default roles, default templates in one transaction.
- Rollback: force failure mid-provisioning, verify no orphan rows.
- Department lifecycle: create → read → update → search → deactivate → reactivate.

### E2E tests
- Full Superadmin provisioning flow → new hospital admin receives email → sets password → logs in → sees their hospital.
- Hospital admin uploads logo → appears in header immediately.

---

## 17. Acceptance Criteria

1. Superadmin can provision a new hospital with initial admin user in one atomic operation.
2. Hospital Admin can update editable fields; restricted fields return 403 on their attempt.
3. Multi-tenant isolation is verified by integration test attempting cross-tenant reads and expecting empty results / 404.
4. Deactivating a hospital immediately revokes all its users' active sessions.
5. Feature flags are respected in <60s of toggle across all backend replicas.
6. Logo upload, branding preview, and letterhead render correctly in generated PDF invoice.
7. Changing MRN pattern affects only subsequent patient creations; existing MRNs unchanged.
8. All configuration changes appear in `hospital_settings_history` and in the audit log.
9. Departments can be created, listed, searched, updated, deactivated and reactivated within a hospital, and are invisible to every other hospital.
10. A department with active doctors assigned cannot be deactivated; the attempt returns 409 naming the blocking assignments.

---

## 18. Rollout Plan

- **v2.0 (MVP):**
  - Single-hospital deployments primarily; multi-tenant schema in place from day one.
  - Superadmin panel minimal (list + provision + deactivate).
  - Feature flags: only the well-known set above, no custom.
- **v2.1:**
  - Add currency/timezone change with migration wizard.
  - Add custom flag keys with schema validation.
  - Add letterhead template versioning.
- **v2.2:**
  - Multi-branch support (one hospital, multiple branches).
  - Custom fields per hospital.
- **v3.0:**
  - Localization (multi-language UI per hospital).
  - Custom subdomain per hospital.

---

## 19. Future Scope

- Multi-branch (locations) inside one hospital tenant.
- SaaS billing / subscription management for hospitals.
- Cross-tenant analytics dashboard for Superadmin.
- White-label reseller mode.
- Hospital groups (parent-child relationships).
- Data residency selection per hospital.
- Configurable audit retention per hospital (subject to regulatory floor).

---

## 20. Open Questions

- Do we need a "trial hospital" status separate from active/inactive? (Deferred to when SaaS billing lands.)
- Should timezone change trigger a background job to shift all future appointments? (Yes, but implementation deferred to v2.1.)
- Should feature flag toggles emit a webhook for external integrations? (Nice-to-have; v2.2+.)
- How do we handle a hospital that wants to change its slug (rebranding)? (v2.2: introduce `slug_aliases` table with 301 redirects.)

---

**Sign-off owner:** Platform Team
**Reviewers required:** Sanjeev, Harshit, Architecture Lead
**Ready for build:** ✅
