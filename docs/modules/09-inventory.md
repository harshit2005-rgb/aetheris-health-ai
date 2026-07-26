# 09 — Inventory

**Owner:** TBD
**Phase:** v2.2
**Status:** Approved (spec)

---

## 1. Purpose

Manage non-pharmacy hospital consumables and equipment — gloves, syringes, gauze, oxygen cylinders, linens, small equipment. Track stock per location, generate reorder alerts, and forecast demand with AI to avoid stockouts.

## 2. Scope

### In Scope

- Item catalog (non-pharmacy)
- Stock levels per storage location (ward, OT, ICU, general store)
- Purchase orders and goods-receiving
- Low-stock alerts
- Batch and expiry tracking (relevant for sterile disposables)
- Vendor management (shared with Pharmacy)
- AI-forecasted reorder recommendations

### Out of Scope

- Medicine inventory → Pharmacy
- Capital equipment lifecycle management → future
- Biomedical maintenance schedules → future

## 3. Personas & Permissions

| Role | Can do |
|---|---|
| Inventory Manager | Full CRUD |
| Nurse / Ward Staff | Request supplies, view local stock |
| Hospital Admin | All + reports |

## 4. Business Rules

1. Stock tracked per (item, location, batch).
2. Consumption recorded per department; ties into cost allocation (v3).
3. Reorder point per item per location; alerts when crossed.
4. AI reorder recommendation considers usage velocity, lead time, and seasonality.
5. Received stock updates on-hand quantity atomically.

## 5. Workflow

- Manager sets reorder points per item/location.
- Stock consumed by ward staff via `POST /inventory/consume`.
- Low-stock threshold trip → notification + AI reorder suggestion.
- Manager creates PO (draft, sent, received).
- Received PO adds stock movements.

## 6. Functional Requirements

- FR-1: Multi-location stock.
- FR-2: Batch + expiry tracking.
- FR-3: Reorder alerts.
- FR-4: PO lifecycle.
- FR-5: AI reorder forecasting.
- FR-6: Consumption tracking by department.

## 7. Non-Functional Requirements

- Consumption entry p95 < 300ms.
- AI forecast run nightly for the whole hospital in < 5 minutes.

## 8. Database Design

```
inventory_items
  id, hospital_id, sku, name, category,
  unit_of_measure, is_batch_tracked, reorder_point INT NULLABLE,
  target_stock INT NULLABLE

inventory_locations
  id, hospital_id, name, code, kind (ward/ot/icu/store), is_active

inventory_stock
  id, item_id, location_id, batch_number NULLABLE, expiry_date NULLABLE,
  quantity NUMERIC(12,2) NOT NULL DEFAULT 0

inventory_movements
  id, item_id, location_id, batch_id NULLABLE,
  quantity_change NUMERIC(12,2),
  reason (received/consumed/transferred_in/transferred_out/adjusted/expired),
  reference_type, reference_id, moved_at, moved_by

inventory_purchase_orders (may share schema with pharmacy POs; separate table for clarity)
  ...similar to pharmacy...
```

## 9. API Design (summary)

```
GET/POST/PATCH  /inventory/items
GET/POST        /inventory/locations
GET             /inventory/stock              # filter by item, location, low_stock=true
POST            /inventory/consume
POST            /inventory/transfer
POST            /inventory/adjust             # requires reason
GET/POST        /inventory/purchase-orders
POST            /inventory/purchase-orders/{id}/receive
GET             /inventory/forecast           # AI reorder recommendations
```

## 10. Permissions

- `inventory.item.read/create/update`
- `inventory.location.read/create/update`
- `inventory.stock.read`
- `inventory.consume`
- `inventory.transfer`
- `inventory.adjust`
- `inventory.po.read/create/update/receive`
- `inventory.forecast.read`

## 11. Validation Rules

- Quantity ≥ 0 after any movement.
- Adjustments require reason.
- Transfers require both source and destination locations.

## 12. UI Requirements

- Item catalog with categorization.
- Stock dashboard per location.
- Reorder alerts panel.
- PO management.
- Forecast dashboard with AI-recommended quantities.

## 13. AI Integration Points

- **Prompt / Model:** `inventory.forecast_reorder` (mixed: statistical baseline + LLM narrative)
- **Provider hint:** `deep` for narrative, statistical model runs in Python (Prophet or ETS)
- **Data scope:** historical consumption (last 12 months), lead times, current stock
- **Output:** ranked reorder recommendations with rationale
- **Safety:** advisory only; manager approves each PO

## 14. Edge Cases

- Adjustments after a physical count → variance report generated.
- Expired batches → auto-flag as `expired`, quantity available drops.
- Transferring across locations concurrently → last-write-wins on the source movement — verified with transaction test.

## 15. Cross-Module Dependencies

- Depends on: Vendor Management (shared with Pharmacy), Audit, Notification.
- Provides to: Reports, AI (future: cost allocation), Pharmacy (shared vendor list).

## 16. Testing Requirements

- Unit: consumption + transfer + adjustment stock deltas.
- Repository: quantity computation.
- API: full lifecycle.
- AI eval: forecast against historical holdout.

## 17. Acceptance Criteria

- AC-1: A ward nurse can record consumption in under 15 seconds.
- AC-2: Low-stock alerts fire at the configured threshold.
- AC-3: AI reorder recommendations are within ±20% of historical actuals in backtest.
- AC-4: Movement history reconstructs current stock exactly.

## 18. Rollout Plan

- Ships v2.2 behind `feature.inventory`.
- Location seeding as part of hospital onboarding.

## 19. Future Scope

- Cost allocation across departments (v3)
- RFID / barcode integration (v3)
- Capital equipment lifecycle (v3)
- Predictive maintenance (v3)

## 20. Open Questions

- Should Inventory and Pharmacy share the `vendors` table now, or split? — Decision: **share** to avoid double vendor management. Move to a shared `procurement` module in v2.3 if needed.
