# 16 — Consultation (EMR)

**Owner:** Harshit (drafted overnight by Claude; review pending)
**Phase:** v2.1
**Status:** Draft — approved by the founder for overnight build on 2026-10-16, to be reviewed with the PR
**Last updated:** 2026-10-16

---

## 1. Purpose

The doctor's working screen. During a visit the doctor records why the patient
came, what they found, what they think it is and what happens next, and from the
same place writes the prescription and orders lab tests. Today a visit goes from
"in progress" to "completed" with nothing written down: there is nowhere for the
clinical record to live. This module gives every visit one structured clinical
note, so a hospital can run its OPD on Atheris rather than on paper.

## 2. Scope

### In Scope

- One consultation note per appointment, owned by the appointment's doctor
- Structured sections: chief complaint, history, examination, diagnoses, plan, follow-up date
- Vitals: blood pressure, pulse, temperature, SpO₂, respiratory rate, weight, height (BMI derived)
- Vitals may be recorded by a nurse before the doctor sees the patient
- Draft → finalized lifecycle; a finalized note is never edited, only added to (addenda)
- The visit's prescriptions and lab orders shown on the note (written through the existing Pharmacy and Laboratory endpoints)
- A patient's consultation history, newest first

### Out of Scope

- Writing prescriptions and ordering tests — the existing Pharmacy (08) and Laboratory (07) endpoints, which already hang off the appointment
- ICD-10 lookup/catalog — diagnoses carry an optional free-text code for now (v2.2)
- AI-drafted notes and summaries (Module 13; columns reserved, not built)
- File attachments to a visit (future)
- Consultation PDF / printable visit summary (future; the prescription PDF exists)

## 3. Personas & Permissions

| Role | Can do | Cannot do |
|---|---|---|
| Doctor | Create, edit, finalize and add addenda to notes for **their own** appointments; record vitals; read all notes in the hospital | Edit another doctor's note; edit a finalized note |
| Nurse | Record vitals on a draft note (creating it if needed); read notes | Write clinical sections, finalize, add addenda |
| Hospital Admin | Read notes | Write clinical content (clinical documentation is the doctor's) |
| Super Admin | Read notes | — |
| Others | Nothing | — |

## 4. Business Rules

1. A consultation belongs to exactly one appointment; an appointment has at most one consultation (unique per hospital).
2. A consultation can be started only for an appointment that is checked in, in progress or completed.
3. Only the appointment's doctor (the user linked to that doctor) may write the clinical sections, finalize, or add addenda — holding `consultation.write` is necessary but not sufficient.
4. Vitals may be recorded by anyone holding `consultation.vitals.record`, while the note is a draft.
5. Finalizing requires a chief complaint and at least one diagnosis.
6. A finalized consultation is never edited. Corrections and later information are added as addenda, each with its author and time.
7. Patient, doctor and appointment are taken from the appointment, never from the request.
8. Every create, update, vitals change, finalize and addendum writes an audit entry.

## 5. Workflow

### 5.1 Happy path

1. Patient is checked in. A nurse opens the visit, records vitals (the note is created as a draft if it does not exist).
2. The doctor starts the visit and opens the consultation: sees the vitals, writes complaint, history, examination, diagnoses and plan; saves as they go.
3. From the same screen the doctor writes the prescription and orders lab tests (existing dialogs, existing endpoints).
4. The doctor finalizes the note. It becomes read-only.
5. Later, a lab result changes the picture: the doctor adds an addendum.

### 5.2 Alternative flows

- 5.2.1 Doctor opens the note with no nurse step → the note is created on first save.
- 5.2.2 Finalize without a diagnosis → 422, nothing changes.
- 5.2.3 Another doctor tries to edit → 403.
- 5.2.4 Appointment still `booked` → 400 "check the patient in first".

## 6. Functional Requirements

- FR-1: Create a draft consultation for an appointment.
- FR-2: Update clinical sections of a draft (partial update).
- FR-3: Record/replace vitals on a draft; BMI derived from weight and height.
- FR-4: Finalize a draft.
- FR-5: Add an addendum to a finalized consultation.
- FR-6: Read one consultation with its addenda, the visit's prescriptions and lab orders.
- FR-7: List consultations (by patient, doctor, appointment), newest first, paginated.

## 7. Non-Functional Requirements

- Save p95 < 500 ms.
- Notes are PHI: responses are `Cache-Control: no-store` where files are involved; nothing clinical is logged.

## 8. Database Design

```
consultations
  id, hospital_id, appointment_id UNIQUE(hospital_id, appointment_id),
  patient_id, doctor_id,
  status ENUM(draft, finalized),
  chief_complaint TEXT, history TEXT, examination TEXT,
  diagnoses JSONB NOT NULL DEFAULT '[]',   -- [{code?, description}]
  plan TEXT, follow_up_date DATE,
  vitals JSONB,                             -- {bp_systolic, bp_diastolic, pulse, temperature_c, spo2, respiratory_rate, weight_kg, height_cm}
  vitals_recorded_at TIMESTAMPTZ, vitals_recorded_by UUID,
  finalized_at TIMESTAMPTZ, finalized_by UUID
  + audit columns

consultation_addenda
  id, hospital_id, consultation_id,
  text TEXT NOT NULL, added_by UUID NOT NULL, added_at TIMESTAMPTZ NOT NULL
  + audit columns
```

Departures from `docs/05-DATABASE_DESIGN.md` §2.13–2.14: `diagnoses` (plural) instead of `diagnosis`; a `status` column so draft vs finalized is explicit; vitals provenance columns; `follow_up_date`; `hospital_id` on addenda (CLAUDE.md rules 4–5). The `ai_summary*` columns are left for Module 13. Prescriptions and lab orders keep hanging off the appointment (1:1 with the consultation), so no `consultation_id` is added to them.

## 9. API Design (summary)

```
POST   /consultations                        create a draft for an appointment
GET    /consultations                        list (?patient_id, ?doctor_id, ?appointment_id, ?status)
GET    /consultations/{id}                   one, with addenda, prescriptions, lab orders
PATCH  /consultations/{id}                   update clinical sections (draft only, own doctor)
PUT    /consultations/{id}/vitals            record vitals (draft only)
POST   /consultations/{id}/finalize          finalize (own doctor)
POST   /consultations/{id}/addenda           add an addendum (finalized only, own doctor)
GET    /appointments/{id}/consultation       the visit's consultation (404 if none yet)
```

`PUT /consultations/{id}/vitals` may also be called as `PUT /appointments/{id}/consultation/vitals`, which creates the draft first if needed (the nurse's entry point).

## 10. Permissions

- `consultation.read`
- `consultation.write` — create, edit, finalize, addenda (plus rule 3)
- `consultation.vitals.record`

## 11. Validation Rules

- Text sections ≤ 10,000 characters; addendum 1–5,000.
- Diagnoses: 0–20 entries; description 1–500; code ≤ 20.
- Vitals (all optional, at least one): systolic 50–300, diastolic 20–200 (and < systolic), pulse 20–250, temperature 30–45 °C, SpO₂ 50–100, respiratory rate 4–80, weight 0.5–400 kg, height 30–250 cm.
- Follow-up date not in the past (hospital's clock).

## 12. UI Requirements

- Consultation screen per visit, reached from the appointment's actions ("Consultation").
- Vitals card with inline form; BMI shown.
- Clinical sections as a form with autosave-free explicit "Save draft"; diagnoses as an editable list.
- Visit panel: prescriptions and lab orders of this visit, with "Write prescription" and "Order lab tests".
- "Finalize" with confirmation; after that, read-only with addenda and "Add addendum".

## 13. AI Integration Points

N/A for this release — AI-drafted SOAP notes (feature 8.5) belong to Module 13 and will write into the draft through the same PATCH.

## 14. Edge Cases

- Two tabs creating the same note → second create gets 409 and the UI loads the existing note.
- Appointment cancelled after the note was started → the note stays readable; no further edits.
- Doctor reassigned on the appointment → ownership follows `consultation.doctor_id`, fixed at creation.

## 15. Cross-Module Dependencies

- Depends on: Appointment, Patient, Doctor, Pharmacy (prescriptions read), Laboratory (orders read), Audit.
- Provides to: Patient record (history), future Discharge summary (IPD), AI summaries.

## 16. Testing Requirements

- Unit: service rules 1–7, vitals validation, BMI.
- API: lifecycle, ownership (403 for another doctor), nurse vitals, tenancy, 401/403/404/409.
- Repository: unique per appointment, tenant filter.

## 17. Acceptance Criteria

- AC-1: A doctor documents a visit and finalizes it in one screen without leaving to write the prescription or order tests.
- AC-2: A finalized note cannot be changed; addenda are shown with author and time.
- AC-3: A nurse's vitals appear on the doctor's note.

## 18. Rollout Plan

Ships with v2.1 for all hospitals; permissions added to the seeded Doctor, Nurse, Hospital Admin and Super Admin roles.

## 19. Future Scope

ICD-10 catalog search; AI SOAP drafts; templates per specialty; attachments; printable visit summary; patient-app view of finalized notes (with consent).

## 20. Open Questions

- Should Hospital Admin see clinical notes at all? Drafted as read-only access; confirm with clinical advisor.
