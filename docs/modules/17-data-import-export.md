# 17 — Data Import & Export

**Owner:** Harshit (drafted overnight by Claude; review pending)
**Phase:** v2.1
**Status:** Draft — approved by the founder for overnight build on 2026-10-16, to be reviewed with the PRs
**Last updated:** 2026-10-17

---

## 1. Purpose

A hospital moving to Atheris has years of patients and a price list in another
system or in Excel. Without import, onboarding means typing it all in; without
export, a hospital fears being locked in. This module answers both objections:
bring your data in from a spreadsheet, take all of it out at any time.

## 2. Scope

### In Scope

- **Import** from `.xlsx` or `.csv`: patients, billing services, medicines, lab tests
- Downloadable templates with the expected columns and an instructions sheet
- A dry run that validates every row and reports problems without saving anything
- **Export** (second PR): every record of the hospital as one `.xlsx` workbook, one sheet per entity, clinical notes included

### Out of Scope

- **Importing doctors.** Every doctor is a staff login and must be invited (email) through Users → Invite; a spreadsheet cannot create logins safely. Their profiles can then be filled in.
- Importing appointments, invoices, lab results or stock history (historical transactions) — future
- Scheduled / automatic exports, exports to other systems' formats (Tally is roadmap item 19)

## 3. Personas & Permissions

| Role | Can do | Cannot do |
|---|---|---|
| Hospital Admin | Import, download templates, export everything | — |
| Super Admin | Same | — |
| Everyone else | Nothing | Import or export |

## 4. Business Rules

1. Import and export act on the caller's hospital only.
2. A file is at most 5 MB and 2,000 data rows; `.xlsx` or `.csv` only, checked by extension, declared type and content signature.
3. Every row is validated with the same rules as creating the record through its own screen; the record is created through that module's service, so MRNs, audit entries and uniqueness work exactly as they do by hand.
4. A row that matches an existing record is **skipped and reported**, never overwritten: same code (services, lab tests), same SKU (medicines), same first name + last name + date of birth (patients).
5. A dry run saves nothing. A real run saves every valid, non-duplicate row and reports the rest by row number and column.
6. Uploaded files are parsed in memory and never stored.
7. Every import and export writes an audit entry with its counts (export: the sheets included).
8. Exports include clinical notes (founder's decision, 2026-10-16) and are `Cache-Control: no-store`.

## 5. Workflow

### 5.1 Import

1. Admin opens Settings → Data → Import, picks what to import, downloads the template.
2. Fills it in (or pastes from the old system), uploads it. A dry run runs first.
3. Sees "N ready, M duplicates, K problems" with the problem rows listed.
4. Fixes the file and re-uploads, or imports the valid rows as they are.

### 5.2 Export

1. Admin clicks Export all data; the workbook downloads.

## 6. Functional Requirements

- FR-1: Templates per entity (`.xlsx`).
- FR-2: Dry-run validation report.
- FR-3: Import valid rows; skip duplicates; report errors per row.
- FR-4: Full export workbook.

## 7. Non-Functional Requirements

- 2,000 rows import in under 60 s.
- Export of 50,000 rows streams in under 60 s.

## 8. Database Design

No new tables. Patient import writes the old system's record number, when given, into the patient's notes ("Previous record no.: …").

## 9. API Design (summary)

```
GET  /imports/{kind}/template            kind = patients | services | medicines | lab-tests
POST /imports/{kind}?dry_run=true|false  body: the file itself (Content-Type: xlsx or csv); X-Filename header
GET  /exports/all                        the workbook (second PR)
```

The file is sent as the raw request body rather than `multipart/form-data`, so no new upload library is needed.

## 10. Permissions

- `data.import`
- `data.export`

## 11. Validation Rules

- Header row must contain every required column (case- and space-insensitive); unknown columns are ignored and reported once.
- Dates: `YYYY-MM-DD`, `DD/MM/YYYY`, or an Excel date cell.
- Indian 10-digit mobile numbers are normalised to `+91…`.
- Booleans: yes/no, true/false, y/n, 1/0.
- A patient address needs both Address line 1 and City, as on the registration screen; otherwise leave all address columns empty.

## 12. UI Requirements

- Settings → Data tab (admins only): Import card (kind picker, template link, file input, report table, Import button), Export card.

## 13. AI Integration Points

N/A — column mapping by AI is a possible v2.2 helper.

## 14. Edge Cases

- Empty rows are ignored. A file with only headers → "nothing to import".
- The same patient twice in one file → the second is a duplicate.
- A formula cell → its cached value is read.

## 15. Cross-Module Dependencies

- Depends on: Patients, Billing (services), Pharmacy (medicines), Laboratory (tests), Audit.

## 16. Testing Requirements

- Unit: parsing (xlsx, csv, dates, phones, booleans, headers), limits.
- API: dry run vs real run, duplicates, errors per row, permissions, tenancy.

## 17. Acceptance Criteria

- AC-1: An admin imports 500 patients from a spreadsheet in one go, with duplicates reported, not created.
- AC-2: An admin downloads all of the hospital's data as one workbook.

## 18. Rollout Plan

Permissions seeded to Hospital Admin and Super Admin.

## 19. Future Scope

Doctor import with batch invitations; historical visits and bills; column mapping UI; scheduled exports.

## 20. Open Questions

- Should patients be matched on phone as well as name + date of birth?
