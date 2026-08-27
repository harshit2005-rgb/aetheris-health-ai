# 06 — Billing

**Owner:** TBD
**Phase:** MVP
**Status:** Approved

---

## 1. Purpose

Turn hospital services into money. Own the services catalog, invoice lifecycle, payments, refunds, and discounts. Every financial action in Aetheris is traceable, idempotent, and audited.

## 2. Scope

### In Scope

- Services catalog (billable items with pricing)
- Invoice creation (draft → issued → paid / void / refunded)
- Multi-line invoices
- Discounts with admin approval workflow
- Taxes configured per hospital
- Multi-method payments (cash, card, UPI, bank, insurance)
- Idempotent payment recording
- Refunds and credit notes
- Payment gateway integration (v2.1)

### Out of Scope

- Insurance claim workflows → v2.2 (Insurance module)
- Payroll / hospital-side accounting → out of platform scope
- Tax filing → out of platform scope

## 3. Personas & Permissions

| Role | Can do |
|---|---|
| Billing Staff | Create/edit invoices, record payments, issue refunds within limits |
| Hospital Admin | Everything, including approving discounts above threshold |
| Doctor | View invoices for their patients |
| Receptionist | View invoices, record cash payments |
| Patient (portal, future) | View own invoices |

## 4. Business Rules

1. Money is `NUMERIC(15,2)` everywhere. No floats. Ever.
2. Invoice numbers are sequential per hospital, gap-free (regulatory-friendly).
3. An issued invoice cannot be edited. Corrections require a void + re-issue, or credit note.
4. Voiding an invoice requires reason + admin.
5. Discounts above a hospital-configured threshold require admin approval before the invoice can be issued.
6. Payments are idempotent by `idempotency_key`.
7. Total is `subtotal + tax_amount - discount_amount`, computed server-side. Client-supplied totals are ignored.
8. Line total is `unit_price * quantity + (tax_rate * unit_price * quantity)`.
9. `amount_paid` cannot exceed `total`.
10. Refunds cannot exceed the invoice's paid amount.
11. Once `amount_paid >= total`, invoice status becomes `paid` automatically.
12. If a completed appointment has a linked invoice draft, updating the appointment does not modify the invoice; edits require an explicit invoice PATCH.

## 5. Workflow

### 5.1 Draft invoice from appointment

1. Appointment completion triggers `BillingService.create_draft_from_appointment(appointment_id)`.
2. Service loads consultation fee, service catalog items configured for the doctor's specialization, adds them as line items.
3. Invoice `status = 'draft'`, `invoice_number = NULL` (assigned at issue).
4. Audit: `invoice.drafted`.

### 5.2 Edit draft

1. Billing staff opens draft.
2. Edits line items, applies discount.
3. If discount > threshold, service marks `discount_pending_approval = true`.
4. Admin reviews and approves via `POST /invoices/{id}/approve-discount`.

### 5.3 Issue invoice

1. `POST /invoices/{id}/issue`.
2. Service allocates next sequential invoice number for the hospital (transactional).
3. Recomputes totals, freezes them.
4. Sets `status = 'issued'`, `issued_at = now()`.
5. Notification: patient receives invoice via email.
6. Audit.

### 5.4 Record payment

1. `POST /invoices/{id}/payments` with `Idempotency-Key`.
2. Body: amount, method, reference.
3. Service validates amount vs remaining; inserts payment; updates `amount_paid`; may transition status.
4. Audit.

### 5.5 Refund

1. `POST /invoices/{id}/refund` (admin only) with amount + reason.
2. Service checks amount ≤ paid; inserts a negative payment or a refund record; adjusts status to `refunded` (full) or leaves paid (partial).
3. Audit.

### 5.6 Void

1. `POST /invoices/{id}/void` with reason.
2. Allowed only from `issued` or `partially_paid` (with no payments recorded — otherwise refund first).
3. Sets `status = 'void'`, `voided_at = now()`.
4. Audit.

## 6. Functional Requirements

- FR-1: The system shall maintain a services catalog per hospital.
- FR-2: The system shall generate invoices from completed appointments.
- FR-3: The system shall enforce idempotent payments.
- FR-4: The system shall generate sequential, gap-free invoice numbers per hospital.
- FR-5: The system shall support discounts with approval workflow.
- FR-6: The system shall support refunds and voiding.
- FR-7: The system shall not allow editing of issued invoices.
- FR-8: The system shall compute totals server-side.

## 7. Non-Functional Requirements

- Payment recording p95 < 500ms.
- Invoice number allocation must be safe under 50 concurrent issuances per hospital.
- Zero double-recording of payments (idempotency test suite).
- All monetary math accurate to two decimal places.

## 8. Database Design

Tables `services`, `invoices`, `invoice_items`, `payments` defined in `05-DATABASE_DESIGN.md`.

Additional sequence table:

```
invoice_number_sequences
  hospital_id     UUID PK FK hospitals(id)
  current_value   BIGINT NOT NULL DEFAULT 0
  format_template VARCHAR(50) NOT NULL DEFAULT 'INV-{year}-{seq:06d}'
  updated_at      TIMESTAMPTZ NOT NULL
```

Allocation via `SELECT ... FOR UPDATE`.

Indexes:
- `uq_invoices_hospital_number (hospital_id, invoice_number)`
- `ix_invoices_status (hospital_id, status, issued_at)`
- `ix_invoices_patient (patient_id, issued_at DESC)`
- `uq_payments_idempotency (idempotency_key)`

## 9. API Design

```
GET    /api/v1/services                    # catalog, filter: category, is_active
POST   /api/v1/services
GET    /api/v1/services/{id}
PATCH  /api/v1/services/{id}

GET    /api/v1/invoices                    # filters: patient_id, status, date range
POST   /api/v1/invoices                    # ad-hoc invoice not tied to an appointment
GET    /api/v1/invoices/{id}
PATCH  /api/v1/invoices/{id}               # draft only
POST   /api/v1/invoices/{id}/issue
POST   /api/v1/invoices/{id}/void
POST   /api/v1/invoices/{id}/approve-discount
POST   /api/v1/invoices/{id}/payments      # Idempotency-Key required
GET    /api/v1/invoices/{id}/payments
POST   /api/v1/invoices/{id}/refund
GET    /api/v1/invoices/{id}/pdf
POST   /api/v1/invoices/{id}/ai-explain    # AI-generated patient-friendly explanation (v2.1)
```

**Request example — POST /invoices/{id}/payments:**

Headers: `Idempotency-Key: 3d1c...`

```json
{
  "amount": "1200.00",
  "method": "upi",
  "reference": "UPI-TXN-8899",
  "notes": "Paid via PhonePe"
}
```

Response 201 with the payment DTO and updated invoice summary.

## 10. Permissions

- `service.read`, `service.create`, `service.update`
- `invoice.read`, `invoice.read.own` (patient portal)
- `invoice.create`, `invoice.update` (draft only)
- `invoice.issue`
- `invoice.void`
- `invoice.approve_discount`
- `invoice.payment.record`
- `invoice.refund`
- `invoice.pdf.download`
- `invoice.ai_explain`

## 11. Validation Rules

- Currency inherited from hospital; not overridable on invoice.
- Line item quantity > 0, unit_price ≥ 0.
- Discount amount ≤ subtotal.
- Discount reason required if discount > 0.
- Payment amount > 0.
- Method ∈ enum.
- Idempotency-Key length 16–100 chars.

## 12. UI Requirements

- Invoices list with status filter, patient filter, date range.
- Draft invoice editor: line items with search-add from services catalog, discount, tax, real-time total preview.
- Issued invoice detail: read-only, actions (record payment, void, refund, download PDF).
- Payment recording modal with method selector.
- Discount approval queue for admin.
- PDF generation with hospital branding.

## 13. AI Integration Points

- **Prompt (v2.1):** `invoice.explain` — generate patient-friendly explanation of the invoice in plain language.
- **Provider hint:** `cheap`
- **Data scope:** invoice + service catalog descriptions + patient's preferred language
- **Safety:** AI never modifies amounts; explanation is descriptive only

## 14. Edge Cases

- Concurrent issue of same invoice from two tabs → DB unique constraint on number wins one.
- Payment recorded twice with same idempotency key → second call returns the first response cached in Redis.
- Refund exceeding paid amount → 400.
- Discount approval race (two admins approve simultaneously) → first commit wins; second gets 409.
- Voided invoice referenced in reports → excluded from revenue metrics but visible in audit.
- Currency rounding: rounding rule = "banker's rounding" (round half to even) per line, then sum.

## 15. Cross-Module Dependencies

- Depends on: Appointment (trigger), Patient (invoice target), Doctor (fees), Hospital Settings (tax, currency), Notification, Audit.
- Provides to: Reports (revenue), Patient portal (future).

## 16. Testing Requirements

- Unit: total calculation, discount thresholds, state transitions.
- Repository: invoice number allocation under concurrency.
- API: full CRUD + all state transitions; idempotency behavior.
- Integration: appointment complete → invoice draft → issue → payment → status transitions.
- Property-based: fuzz money math.

## 17. Acceptance Criteria

- AC-1: An issued invoice cannot be edited.
- AC-2: Invoice numbers are sequential and gap-free per hospital.
- AC-3: Duplicate payments with the same idempotency key return the same result and do not double-charge.
- AC-4: A discount above threshold blocks issue until admin approves.
- AC-5: The invoice PDF matches the on-screen invoice line-for-line.
- AC-6: Voided invoices are excluded from revenue reports.
- AC-7: All money math is accurate to the paisa (INR minor unit).

## 18. Rollout Plan

- Ships with MVP without payment gateway (manual payment recording).
- Payment gateway integration in v2.1 behind `feature.billing.gateway`.

## 19. Future Scope

- Insurance claim submission (v2.2)
- Payment plans / installments (v2.2)
- Recurring / subscription-style billing for wellness packages (v3)
- Advanced tax rules (multi-tax, GST breakdown) (v2.1)
- Statement of account for patients (v2.1)
- Bulk statement generation (v2.2)

## 20. Open Questions

- India-specific: GST breakdown display (CGST/SGST/IGST) — required from Day 1 or v2.1? **Decision needed before invoice PDF work.**
