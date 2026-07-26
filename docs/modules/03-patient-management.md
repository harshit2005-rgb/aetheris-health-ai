# 03 — Patient Management

**Owner:** TBD
**Phase:** MVP
**Status:** Approved

---

## 1. Purpose

The patient is the primary entity around which every hospital workflow revolves. This module owns the patient record — demographics, medical history, documents, and identifiers — and provides the read/write surface every other module builds on.

## 2. Scope

### In Scope

- Patient registration
- Auto-generated Medical Record Number (MRN) unique per hospital
- Patient search (name, phone, MRN, DOB)
- Medical history (allergies, chronic conditions, medications, past surgeries)
- Emergency contact
- Document uploads (ID proof, prior records)
- Patient timeline (visits, appointments, prescriptions)
- AI-generated patient summary from history
- Insurance information (v2.1)

### Out of Scope

- Consultation notes → owned by Appointment/Consultation
- Prescriptions → owned by Consultation
- Lab results → owned by Laboratory
- Invoices → owned by Billing
- Duplicate detection (advanced, AI-driven) → v2.1

## 3. Personas & Permissions

| Role | Can do |
|---|---|
| Receptionist | Register patient, edit demographics, view timeline |
| Doctor | View patient, view timeline, view AI summary |
| Nurse | View patient, view timeline |
| Hospital Admin | All patient operations |
| Billing Staff | View limited fields for invoicing (name, MRN, address, phone) |
| Patient (portal, future) | View own record |

## 4. Business Rules

1. MRN is unique per hospital, generated on registration.
2. MRN format: configurable per hospital (default `MRN-YYYY-NNNNN`).
3. First and last name are required; DOB is required; gender is required.
4. A patient cannot be permanently deleted; soft delete only, with admin approval workflow (v2.1).
5. Medical history fields (allergies, conditions, medications) are structured JSON, not free text.
6. Patient search is case-insensitive and supports partial match on name.
7. Document uploads are stored in object storage; only metadata + signed URL live in DB.
8. AI summary is regenerated on demand; the previous summary is cached but marked stale when history changes.
9. Every read of the patient record is logged (v2.2 — read logging).

## 5. Workflow

### 5.1 Register patient

1. Receptionist opens registration form.
2. Enters demographics, contact, emergency contact, initial history.
3. Submits `POST /patients`.
4. Service generates MRN via `MRNService.next(hospital_id)` (transactional, per-hospital counter).
5. Service persists patient, writes audit log.
6. Response includes patient DTO with MRN.

### 5.2 Update medical history

1. Doctor / receptionist navigates to patient detail → "Medical History" tab.
2. Adds allergy / condition / medication with structured fields.
3. Submits `PATCH /patients/{id}`.
4. Service diffs history and writes audit entry with the diff.

### 5.3 Upload document

1. User selects a document on the patient detail page.
2. Client calls `POST /patients/{id}/documents` with multipart file.
3. Service validates mime type + size, uploads to object storage, records metadata.
4. Returns document metadata with a signed URL for immediate viewing.

### 5.4 Request AI summary

1. User clicks "AI Summary" on patient detail.
2. Client calls `GET /patients/{id}/summary`.
3. Service fetches patient + timeline data limited to authorized scope.
4. AI service renders `patient.summarize` prompt.
5. Stream response back to UI.
6. Log to `ai_interactions`.

### 5.5 Search

1. User types in the global patient search.
2. Client calls `GET /patients?q=<term>&page=1&page_size=25`.
3. Service performs case-insensitive prefix match on name; exact on MRN and phone.

## 6. Functional Requirements

- FR-1: The system shall register a patient with unique MRN per hospital.
- FR-2: The system shall support search by name, MRN, phone, DOB.
- FR-3: The system shall record allergies, chronic conditions, and current medications as structured data.
- FR-4: The system shall attach documents to patients.
- FR-5: The system shall generate an AI summary of a patient's history on request.
- FR-6: The system shall log every write to a patient record.
- FR-7: The system shall support soft delete only.

## 7. Non-Functional Requirements

- Registration p95 < 500ms.
- Patient list p95 < 300ms with 100k patients per hospital.
- AI summary p95 < 4s (streaming; first token < 1s).
- Documents up to 25 MB per file, up to 100 documents per patient.

## 8. Database Design

Table `patients` defined in `05-DATABASE_DESIGN.md`.

Additional table for documents:

```
patient_documents
  id              UUID PK
  patient_id      UUID FK patients(id) NOT NULL
  hospital_id     UUID FK hospitals(id) NOT NULL     # denormalized for tenant filtering
  file_name       VARCHAR(255) NOT NULL
  file_size       BIGINT NOT NULL
  mime_type       VARCHAR(100) NOT NULL
  storage_key     TEXT NOT NULL                       # opaque object storage key
  category        VARCHAR(50)                         # id_proof, prior_record, prescription, image, other
  description     TEXT
  uploaded_by     UUID FK users(id) NOT NULL
  + audit columns
  Index: (patient_id, deleted_at)
```

Additional table for MRN sequence:

```
mrn_sequences
  hospital_id     UUID PK FK hospitals(id)
  current_value   BIGINT NOT NULL DEFAULT 0
  format_template VARCHAR(50) NOT NULL DEFAULT 'MRN-{year}-{seq:05d}'
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
```

MRN generation runs inside a DB transaction with `SELECT ... FOR UPDATE` on the row.

## 9. API Design

```
GET    /api/v1/patients                    # paginated list, filters: q, gender, age_gte, age_lte
POST   /api/v1/patients                    # register
GET    /api/v1/patients/{id}
PATCH  /api/v1/patients/{id}
DELETE /api/v1/patients/{id}               # soft delete, admin only
GET    /api/v1/patients/{id}/timeline      # appointments, consultations, invoices
GET    /api/v1/patients/{id}/summary       # AI summary (SSE stream)
POST   /api/v1/patients/{id}/documents     # multipart upload
GET    /api/v1/patients/{id}/documents
GET    /api/v1/patients/{id}/documents/{doc_id}   # returns signed URL
DELETE /api/v1/patients/{id}/documents/{doc_id}
```

**Request example — POST /patients**

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
  },
  "emergency_contact": {
    "name": "Ravi Rao",
    "phone": "+919812340001",
    "relation": "husband"
  },
  "allergies": [{"name": "Penicillin", "severity": "moderate"}],
  "chronic_conditions": [{"name": "Type 2 Diabetes", "since_year": 2019}],
  "current_medications": [{"name": "Metformin", "dosage": "500mg", "frequency": "twice daily"}]
}
```

**Response 201** — patient DTO with generated `id`, `mrn`, and audit fields.

## 10. Permissions

- `patient.read`
- `patient.create`
- `patient.update`
- `patient.delete` (admin only)
- `patient.timeline.read`
- `patient.document.read`
- `patient.document.upload`
- `patient.document.delete`
- `patient.summary.read`

## 11. Validation Rules

- First/last name: 1–100 chars.
- DOB: not in the future, not more than 130 years ago.
- Phone: E.164 or blank.
- Email: RFC 5322 or blank.
- Blood group: enum (A+, A-, B+, B-, AB+, AB-, O+, O-).
- Allergies / conditions / medications: array of typed objects with required fields per schema.

## 12. UI Requirements

- Patient list with search bar (debounced), filters, pagination, empty state.
- Patient registration form (single page for MVP, wizard for v2.1 if fields grow).
- Patient detail page with tabs: Overview, Medical History, Documents, Timeline, AI Summary.
- Document uploader with drag-and-drop, per-file progress, mime/size validation client-side.
- AI Summary panel with streaming display and "Regenerate" button.

## 13. AI Integration Points

- **Prompt:** `patient.summarize`
- **Provider hint:** `fast` (Groq default), fallback to `deep` for older / complex histories
- **Data scope:** patient demographics + allergies + conditions + medications + recent consultations (last 12 months) + latest lab flags (v2.1)
- **PII minimization:** DOB → age; MRN → omitted from prompt
- **Tools available:** none — pure summarization
- **Safety:** output labeled "AI-generated. Verify with the patient." in the UI

Future (v2.1):
- `patient.duplicate_check` — extraction + fuzzy match against existing records at registration time.

## 14. Edge Cases

- Duplicate MRN race: enforced by DB unique constraint; if conflict, retry with next sequence value.
- Very long name / unicode: allowed; DB uses `VARCHAR(100)` with `CHECK` on max length.
- Missing DOB: not allowed; if actually unknown, admin can set a placeholder DOB with a `notes` entry (documented workflow).
- Deleted patient referenced by appointments: soft delete leaves the reference intact but list views exclude the patient.
- Very large document uploads: chunked upload in v2.1; MVP uses direct multipart up to 25 MB.

## 15. Cross-Module Dependencies

- Provides to: Appointment, Consultation, Billing, Laboratory, Pharmacy (patient reference).
- Depends on: User Management (actor), Notification (welcome email v2.1), AI service (summary), Object storage (documents), Audit service.

## 16. Testing Requirements

- Unit: MRN generation (concurrency safe), history diffing, permission checks.
- Repository: search queries, tenant filter.
- API: full CRUD + AI summary streaming + document upload.
- Integration: register → book appointment → complete consultation → verify timeline.
- AI eval: `patient.summarize` golden set with ≥ 10 cases.

## 17. Acceptance Criteria

- AC-1: A receptionist can register a new patient in under 60 seconds.
- AC-2: MRN is unique per hospital and follows the configured format.
- AC-3: Patient search finds a patient by first three letters of name, exact MRN, or full phone.
- AC-4: A doctor can view a patient's AI summary within 4 seconds (streaming; first token < 1s).
- AC-5: Every write to a patient record produces an audit entry with actor + diff.
- AC-6: Documents up to 25 MB upload successfully; larger files return 422.
- AC-7: Non-authorized roles cannot see patient details.

## 18. Rollout Plan

- Ships with MVP.
- Object storage credentials configured per environment before rollout.
- AI summary behind a feature flag `feature.ai.patient_summary` for first 2 weeks post-launch, defaulting on.

## 19. Future Scope

- AI-driven duplicate detection at registration (v2.1)
- Family / relationship linking (v3)
- Patient consent management (v2.2)
- Patient portal — self-service view (v3)
- Bulk import from prior systems (per-pilot, custom scripts)

## 20. Open Questions

- Should MRN format be user-editable at hospital settings or only on hospital creation? → **Decision needed by Week 2 of MVP sprint.**
