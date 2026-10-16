# 08 — Pharmacy

**Owner:** TBD
**Phase:** v2.1
**Status:** Approved (spec)

---

## 1. Purpose

Manage the medicine catalog, dispense prescriptions, deduct stock transactionally, warn on drug interactions, track expiry, and generate purchase orders. Close the therapeutic loop from prescription to patient's hand.

## 2. Scope

### In Scope

- Medicine catalog with SKU + batch + expiry
- Prescription dispensing (with transactional stock deduction)
- Drug interaction warnings (from a curated interaction dataset)
- Expiry tracking with alerts
- Purchase orders and goods-receiving
- AI-suggested substitutions for out-of-stock items

### Out of Scope

- Chemotherapy compounding → future
- Narcotics dual-lock workflow → v2.2 with specific regulatory support
- Cross-hospital transfer → v3

## 3. Personas & Permissions

| Role | Can do |
|---|---|
| Pharmacist | Dispense, receive stock, manage batches |
| Pharmacy Admin | Manage catalog, POs, vendors |
| Doctor | Write prescriptions (owned by Consultation, referenced here) |
| Hospital Admin | All |

## 4. Business Rules

1. Stock is tracked per medicine per batch per location.
2. Dispensing deducts stock in FIFO by expiry (earliest first).
3. Dispensing is transactional — if any medicine is short, whole dispense fails.
4. Batches with expiry within 30 days trigger warnings; expired batches are non-dispensable.
5. Prescriptions can be fully or partially dispensed with reason.
6. Every dispense produces a bill line via Billing.
7. AI substitutions are suggestions only; pharmacist confirms.

## 5. Workflow

### 5.1 Dispense

1. Pharmacist opens prescription list.
2. Selects one; system shows items with available stock, batches, expiry.
3. Confirms → transaction: deduct stock rows, insert dispense record, insert bill line.
4. Notification to doctor if any substitution occurred.
5. Audit.

### 5.2 Receive stock

1. Pharmacist opens PO.
2. Enters batches with quantity, expiry, cost per unit.
3. Service inserts stock rows; PO status → received.
4. Audit.

## 6. Functional Requirements

- FR-1: Medicine catalog with strength, form, ATC/therapeutic class.
- FR-2: Multi-batch stock with expiry.
- FR-3: Transactional dispense.
- FR-4: Interaction warnings.
- FR-5: PO / receive workflow.
- FR-6: AI substitution suggestion when out of stock.

## 7. Non-Functional Requirements

- Dispense p95 < 500ms.
- Interaction check < 200ms.
- Stock accuracy 100% (audited monthly).

## 8. Database Design

```
medicines
  id, hospital_id, name, generic_name, strength, form, atc_code,
  requires_prescription BOOLEAN, is_active

medicine_batches
  id, medicine_id, batch_number, expiry_date, cost_per_unit,
  location_id NULLABLE, initial_quantity

stock_movements
  id, batch_id, quantity_change, reason (received/dispensed/adjusted/expired),
  reference_type, reference_id, moved_at, moved_by

prescriptions (already in Consultation) — referenced

dispenses
  id, prescription_id, dispensed_at, dispensed_by,
  total_amount, notes

dispense_items
  id, dispense_id, prescription_item_id, medicine_id,
  batch_id, quantity, unit_price, total

purchase_orders
  id, hospital_id, vendor_id, po_number,
  status (draft/sent/received/cancelled), notes,
  ordered_at, received_at

po_items
  id, po_id, medicine_id, quantity, unit_price, total

drug_interactions
  id, medicine_a_id, medicine_b_id, severity, description, source

vendors
  id, hospital_id, name, contact, address, tax_id, is_active
```

Stock quantity is computed as sum of movements per batch. Cache in a materialized view or Redis with invalidation for performance (v2.2).

## 9. API Design (summary)

```
GET/POST/PATCH  /medicines
GET/POST        /medicines/{id}/batches
GET             /medicines/{id}/stock
GET             /prescriptions/pending           # to be dispensed
POST            /prescriptions/{id}/dispense
GET/POST        /purchase-orders
POST            /purchase-orders/{id}/receive
GET/POST/PATCH  /vendors
GET             /pharmacy/interactions/check     # POST with medicine ids
POST            /pharmacy/ai-substitute          # for out-of-stock item
```

## 10. Permissions

- `pharmacy.medicine.read/create/update`
- `pharmacy.batch.read/create/update`
- `pharmacy.dispense.execute`
- `pharmacy.interaction.check`
- `pharmacy.po.read/create/update/receive`
- `pharmacy.vendor.read/create/update`
- `pharmacy.ai_substitute`

## 11. Validation Rules

- Batch expiry ≥ today.
- Quantity ≥ 0.
- Dispense quantity ≤ prescribed quantity.
- Prescription must be active (not expired, not fully dispensed).

## 12. UI Requirements

- Dispensing queue.
- Prescription detail with per-item stock availability display.
- Batch selection with expiry sort.
- Interaction warning modal.
- Stock overview with low-stock and expiring-soon widgets.
- PO management screens.

## 13. AI Integration Points

- **Prompt:** `pharmacy.substitute` — given out-of-stock medicine + patient allergies + on-hand alternatives, suggest substitution.
- **Provider hint:** `deep`.
- **Data scope:** medicine data, patient allergies, current medications, alternatives on hand.
- **Safety:** suggestion only; requires pharmacist confirmation. Never auto-substitute a controlled/regulated medicine.
- **Interaction data source:** curated dataset — never rely on AI to invent interactions.

## 14. Edge Cases

- Concurrent dispense of the same last unit → DB constraint on stock movement sum wins one; other retries.
- Dispensing during a batch recall → block with clear message.
- Expiry today at midnight — dispensable, warning shown.
- Substitution refused by patient — recorded as partial dispense.

## 15. Cross-Module Dependencies

- Depends on: Consultation (prescriptions), Billing (charge per item), Notification, Audit.
- Provides to: Reports (stock, dispensing volume), AI (context for patient summary).

## 16. Testing Requirements

- Unit: FIFO by expiry, transactional dispense.
- Repository: stock quantity computation.
- API: full dispense lifecycle including failure modes.
- Integration: prescription → dispense → bill line → payment.
- Concurrency: 50 simultaneous dispenses on the same batch.

## 17. Acceptance Criteria

- AC-1: A pharmacist can dispense a 5-item prescription in under 60 seconds.
- AC-2: Stock is deducted in FIFO by expiry.
- AC-3: Dispensing fails atomically if any item is short.
- AC-4: Interactions flag before dispense.
- AC-5: Expired batches are not dispensable.

## 18. Rollout Plan

- Ships v2.1 behind `feature.pharmacy`.
- Interaction dataset seeded during onboarding.

## 19. Future Scope

- Narcotics dual-lock (v2.2)
- Compounding (v3)
- Automated reorder based on inventory forecasts (v2.2 — coupled with Inventory)

## 20. Open Questions

- Interaction dataset licensing: use open Drugbank Open Data or license commercial? Decision needed by v2.1 sprint start.
