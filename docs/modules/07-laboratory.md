# 07 — Laboratory

**Owner:** TBD
**Phase:** v2.1
**Status:** Approved (spec) / Not Started (implementation)

---

## 1. Purpose

Manage lab test orders from consultation, sample collection, result entry, abnormal flagging, PDF report generation, and AI-assisted lay-language explanation of results. Close the diagnostic loop: doctor orders → lab runs → results flow back into the patient record and get flagged for review.

## 2. Scope

### In Scope

- Test catalog with reference ranges per age/sex
- Test order from consultation
- Sample collection tracking (barcode-ready)
- Result entry with reference range validation
- Abnormal value flagging
- Release approval workflow before results are visible to the patient
- PDF lab report generation
- AI lay-language explanation of results

### Out of Scope

- Interfacing with lab analyzer hardware → future (v3, requires HL7/FHIR)
- Radiology / imaging → future (Radiology module in v3)
- Genomic panels → future

## 3. Personas & Permissions

| Role | Can do |
|---|---|
| Doctor | Order tests, view results |
| Lab Technician | Collect samples, enter results, request release |
| Lab Supervisor | Approve release, override abnormal flags |
| Nurse | View orders for their patients |
| Hospital Admin | All |
| Patient (portal, future) | View released results only |

## 4. Business Rules

1. Every test order references an appointment or consultation.
2. Result entry validates against the test's reference range and flags out-of-range values automatically.
3. Results are visible to the ordering doctor immediately; visible to the patient only after release.
4. A released result cannot be edited — corrections go through amendment workflow.
5. Sample identifiers are unique per hospital (barcode-ready).
6. Turn-around time is tracked from order to result release.

## 5. Workflow

1. Doctor orders tests during / after consultation.
2. Lab receives order, collects sample, records `sample_collected_at`.
3. Technician enters results with values.
4. System flags out-of-range values.
5. Supervisor reviews and releases.
6. Notification to ordering doctor.
7. PDF report generated on demand.

## 6. Functional Requirements

- FR-1: Test catalog with per-demographic reference ranges.
- FR-2: Order → collection → result → release lifecycle.
- FR-3: Automatic abnormal flagging.
- FR-4: Release approval before visibility to patient.
- FR-5: PDF report generation with hospital branding.
- FR-6: AI-generated lay-language explanation of results (v2.1 same phase).

## 7. Non-Functional Requirements

- Result entry p95 < 500ms.
- PDF generation p95 < 3s.
- 99% correctness in reference range flagging (validated against a curated dataset).

## 8. Database Design

```
tests_catalog
  id, hospital_id, code, name, category, unit,
  reference_ranges JSONB,        -- array of {sex, age_min, age_max, low, high}
  turnaround_hours INT,
  price NUMERIC(15,2),
  is_active BOOLEAN

lab_orders
  id, hospital_id, patient_id, doctor_id,
  appointment_id NULLABLE, consultation_id NULLABLE,
  ordered_at, priority (routine/urgent/stat),
  status (ordered / collected / in_progress / results_entered / released / cancelled),
  notes
  + audit

lab_order_items
  id, lab_order_id, test_id,
  sample_id VARCHAR(50),
  sample_collected_at, sample_collected_by,
  result_value TEXT,               -- numeric or text
  result_unit VARCHAR(20),
  result_flag ENUM(normal/low/high/critical),
  result_entered_at, result_entered_by,
  released_at, released_by,
  notes

lab_result_amendments
  id, item_id, previous_value, new_value, reason,
  amended_by, amended_at
```

## 9. API Design (summary)

```
GET/POST/PATCH /tests-catalog
GET/POST       /lab-orders
GET/PATCH      /lab-orders/{id}
POST           /lab-orders/{id}/collect
POST           /lab-orders/{id}/enter-results
POST           /lab-orders/{id}/release
POST           /lab-orders/{id}/cancel
GET            /lab-orders/{id}/report.pdf
POST           /lab-orders/{id}/ai-explain
```

## 10. Permissions

- `lab.test.read` / `.create` / `.update`
- `lab.order.read` / `.create` / `.cancel`
- `lab.order.collect_sample`
- `lab.order.enter_results`
- `lab.order.release`
- `lab.order.amend`
- `lab.report.download`
- `lab.ai_explain`

## 11. Validation Rules

- Result value: matches the test's expected type (numeric or text).
- Reference range required for numeric tests.
- Sample id unique per hospital.
- Release only after all items have results.

## 12. UI Requirements

- Test catalog admin.
- Order form: multi-select tests, priority, notes.
- Lab worklist: filter by status, priority.
- Result entry screen: form pre-filled with test names, previous history where relevant.
- Release approval queue.
- Patient timeline: released results with abnormal flag color coding.

## 13. AI Integration Points

- **Prompt:** `lab.explain_results` — lay-language explanation of results for the patient
- **Provider hint:** `deep` (quality matters when discussing clinical values)
- **Scope:** patient demographics + released result values + reference ranges
- **Safety:** output prefixed with "AI-generated. Not medical advice. Speak to your doctor."
- **v2.2:** `lab.pattern_flag` — spot patterns across serial reports (declining hemoglobin, rising creatinine)

## 14. Edge Cases

- Sample lost / rejected → new item required; original marked cancelled with reason.
- Reference range mismatch (patient age changes mid-turnaround) → use age at collection.
- Critical values (e.g. potassium > 6.5) → immediate notification to doctor.
- Amendment after release → notification to prior viewers.

## 15. Cross-Module Dependencies

- Depends on: Patient, Doctor, Appointment, Consultation, Notification, Billing (test prices).
- Provides to: Consultation (results attach), Reports (turnaround time), AI (context for patient summary).

## 16. Testing Requirements

- Unit: reference range flagging across demographics.
- API: full lifecycle including release, amendment.
- Integration: order → collect → result → release → patient sees result.
- AI eval: `lab.explain_results` golden set including critical values.

## 17. Acceptance Criteria

- AC-1: A doctor can order tests from a consultation in under 20 seconds.
- AC-2: Out-of-range values are flagged automatically.
- AC-3: Patients cannot see results before release.
- AC-4: PDF reports match on-screen values exactly.
- AC-5: AI-explained results are graded ≥ 4/5 on clarity by pilot patients.

## 18. Rollout Plan

- Ships with v2.1 behind `feature.laboratory`.
- Test catalog seed per pilot hospital.

## 19. Future Scope

- Instrument integration via HL7/FHIR (v3)
- Home sample collection scheduling (v3)
- Reference laboratory (send-out) tracking (v2.2)

## 20. Open Questions

- Which normal ranges dataset to seed with (LOINC-mapped)? Owner: clinical advisor.
