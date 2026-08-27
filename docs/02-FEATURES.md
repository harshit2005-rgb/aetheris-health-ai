# 02 — Feature Catalog

Complete list of Aetheris Health AI features, prioritized by release phase.

**Legend**
- 🟢 **MVP (v2.0)** — must ship for kickoff release
- 🟡 **v2.x** — ships in v2.1, v2.2, or v2.3
- 🔵 **Future** — post v2.3, tracked in roadmap
- 🤖 = AI-augmented feature
- 🔒 = Security-critical feature

---

## 1. Authentication & Session Management

| # | Feature | Phase |
|---|---|---|
| 1.1 | Email + password login | 🟢 🔒 |
| 1.2 | JWT access token (short-lived) | 🟢 🔒 |
| 1.3 | Refresh token with rotation | 🟢 🔒 |
| 1.4 | Password reset via email | 🟢 🔒 |
| 1.5 | Force password change on first login | 🟢 🔒 |
| 1.6 | Account lockout after failed attempts | 🟢 🔒 |
| 1.7 | Session revocation (logout everywhere) | 🟢 🔒 |
| 1.8 | Multi-factor authentication (TOTP) | 🟡 🔒 |
| 1.9 | SSO / OAuth for hospital identity providers | 🔵 🔒 |
| 1.10 | Biometric login (mobile app) | 🔵 🔒 |

## 2. Authorization & Access Control

| # | Feature | Phase |
|---|---|---|
| 2.1 | Role-Based Access Control (RBAC) | 🟢 🔒 |
| 2.2 | Permission-based fine-grained checks | 🟢 🔒 |
| 2.3 | Predefined system roles (10 roles) | 🟢 🔒 |
| 2.4 | Custom role creation by Hospital Admin | 🟡 🔒 |
| 2.5 | Permission inheritance and grouping | 🟡 🔒 |
| 2.6 | Row-level access rules (e.g. doctor sees only their patients) | 🟡 🔒 |
| 2.7 | Delegated access (temporary permission grants) | 🔵 🔒 |

## 3. User Management

| # | Feature | Phase |
|---|---|---|
| 3.1 | Create / update / soft-delete users | 🟢 |
| 3.2 | Assign roles and permissions | 🟢 |
| 3.3 | User profile with contact and employment details | 🟢 |
| 3.4 | Bulk user import (CSV) | 🟡 |
| 3.5 | User activity feed | 🟡 |
| 3.6 | Deactivation vs deletion workflows | 🟢 |
| 3.7 | Directory search across staff | 🟢 |

## 4. Patient Management

| # | Feature | Phase |
|---|---|---|
| 4.1 | Patient registration with demographics | 🟢 |
| 4.2 | Auto-generated Medical Record Number (MRN) | 🟢 |
| 4.3 | Patient search (name, phone, MRN, DOB) | 🟢 |
| 4.4 | Medical history capture (allergies, chronic conditions, past surgeries, medications) | 🟢 |
| 4.5 | Emergency contact & next of kin | 🟢 |
| 4.6 | Insurance information | 🟡 |
| 4.7 | Document uploads (ID proof, past records) | 🟢 |
| 4.8 | Patient timeline (visits, appointments, prescriptions) | 🟢 |
| 4.9 | 🤖 AI-generated patient summary from history | 🟢 🤖 |
| 4.10 | 🤖 Duplicate patient detection at registration | 🟡 🤖 |
| 4.11 | Family / relationship linking | 🔵 |
| 4.12 | Patient consent management | 🟡 🔒 |
| 4.13 | Patient portal (self-service view) | 🔵 |

## 5. Doctor Management

| # | Feature | Phase |
|---|---|---|
| 5.1 | Doctor profile (credentials, specialization, license) | 🟢 |
| 5.2 | Department assignment | 🟢 |
| 5.3 | Weekly availability schedule | 🟢 |
| 5.4 | Time-off / leave management | 🟢 |
| 5.5 | Consultation fee configuration | 🟢 |
| 5.6 | Doctor performance metrics | 🟡 |
| 5.7 | Multi-hospital affiliation | 🔵 |

## 6. Nurse & Staff Management

| # | Feature | Phase |
|---|---|---|
| 6.1 | Nurse profile and shift assignment | 🟡 |
| 6.2 | Ward / floor assignment | 🟡 |
| 6.3 | Shift schedules | 🟡 |
| 6.4 | 🤖 AI-suggested shift optimization | 🔵 🤖 |

## 7. Appointment Management

| # | Feature | Phase |
|---|---|---|
| 7.1 | Book appointment with doctor & time slot | 🟢 |
| 7.2 | Reschedule appointment | 🟢 |
| 7.3 | Cancel appointment with reason | 🟢 |
| 7.4 | Walk-in queue management | 🟢 |
| 7.5 | Appointment status workflow (booked → checked-in → in-progress → completed → no-show) | 🟢 |
| 7.6 | Doctor calendar view | 🟢 |
| 7.7 | Reception dashboard for the day | 🟢 |
| 7.8 | 🤖 AI slot recommendation based on urgency & doctor load | 🟢 🤖 |
| 7.9 | 🤖 AI-generated appointment reminder text | 🟢 🤖 |
| 7.10 | Recurring appointments (follow-ups) | 🟡 |
| 7.11 | Video consultation booking | 🔵 |

## 8. Clinical Documentation

| # | Feature | Phase |
|---|---|---|
| 8.1 | Consultation notes with structured sections | 🟢 |
| 8.2 | Vitals capture | 🟢 |
| 8.3 | Diagnosis coding (ICD-10 lookup) | 🟡 |
| 8.4 | Prescription writing | 🟡 |
| 8.5 | 🤖 AI-drafted SOAP notes from voice/text input | 🟡 🤖 |
| 8.6 | 🤖 AI summarization of long visit history | 🟢 🤖 |
| 8.7 | Attach files (images, PDFs) to visit | 🟢 |
| 8.8 | Amend / addendum workflow (never overwrite) | 🟢 |

## 9. Billing

| # | Feature | Phase |
|---|---|---|
| 9.1 | Service catalog with pricing | 🟢 |
| 9.2 | Invoice generation from appointment/services | 🟢 |
| 9.3 | Line-item edits (with audit trail) | 🟢 |
| 9.4 | Discount application with approval workflow | 🟢 |
| 9.5 | Tax configuration per hospital | 🟢 |
| 9.6 | Payment recording (cash, card, UPI, insurance) | 🟢 |
| 9.7 | Partial payments & receivables | 🟢 |
| 9.8 | Refunds & credit notes | 🟢 |
| 9.9 | Idempotent payment processing | 🟢 🔒 |
| 9.10 | 🤖 AI-drafted invoice explanation for patient | 🟡 🤖 |
| 9.11 | Insurance claim submission | 🟡 |
| 9.12 | Payment gateway integration | 🟡 |

## 10. Laboratory

| # | Feature | Phase |
|---|---|---|
| 10.1 | Test catalog | 🟡 |
| 10.2 | Test order from consultation | 🟡 |
| 10.3 | Sample collection tracking | 🟡 |
| 10.4 | Result entry with reference ranges | 🟡 |
| 10.5 | Abnormal value flagging | 🟡 |
| 10.6 | 🤖 AI-generated lay-language result explanation | 🟡 🤖 |
| 10.7 | 🤖 AI-flagged patterns across serial reports | 🔵 🤖 |
| 10.8 | Result release approval workflow | 🟡 |
| 10.9 | PDF report generation | 🟡 |

## 11. Pharmacy

| # | Feature | Phase |
|---|---|---|
| 11.1 | Medicine catalog with SKU & batch | 🟡 |
| 11.2 | Prescription dispensing | 🟡 |
| 11.3 | Stock deduction on dispense (transactional) | 🟡 |
| 11.4 | Drug interaction warnings | 🟡 |
| 11.5 | Expiry tracking | 🟡 |
| 11.6 | Purchase order generation | 🟡 |
| 11.7 | 🤖 AI-suggested substitutions for out-of-stock items | 🟡 🤖 |

## 12. Inventory

| # | Feature | Phase |
|---|---|---|
| 12.1 | Item catalog | 🟡 |
| 12.2 | Stock levels per location | 🟡 |
| 12.3 | Low-stock alerts | 🟡 |
| 12.4 | Purchase orders and receiving | 🟡 |
| 12.5 | Vendor management | 🟡 |
| 12.6 | 🤖 AI-forecasted reorder recommendations | 🟡 🤖 |
| 12.7 | Batch and expiry tracking | 🟡 |
| 12.8 | Cycle count / audit | 🔵 |

## 13. Reports & Dashboard

| # | Feature | Phase |
|---|---|---|
| 13.1 | Hospital Admin dashboard (KPIs) | 🟢 |
| 13.2 | Doctor dashboard (my patients, my schedule) | 🟢 |
| 13.3 | Reception dashboard (today's appointments) | 🟢 |
| 13.4 | Billing dashboard (revenue, outstanding) | 🟢 |
| 13.5 | Standard operational reports | 🟢 |
| 13.6 | Custom report builder | 🔵 |
| 13.7 | Scheduled report email delivery | 🟡 |
| 13.8 | 🤖 AI-generated natural language summary of dashboard | 🟢 🤖 |
| 13.9 | 🤖 AI-answered ad-hoc data questions | 🟡 🤖 |
| 13.10 | Export to CSV / PDF | 🟢 |

## 14. Notifications

| # | Feature | Phase |
|---|---|---|
| 14.1 | In-app notification center | 🟢 |
| 14.2 | Email notifications | 🟢 |
| 14.3 | Notification preferences per user | 🟢 |
| 14.4 | Template management | 🟡 |
| 14.5 | SMS notifications | 🟡 |
| 14.6 | WhatsApp notifications | 🔵 |
| 14.7 | Push notifications (mobile) | 🔵 |

## 15. Audit Logs

| # | Feature | Phase |
|---|---|---|
| 15.1 | Immutable audit log for every significant action | 🟢 🔒 |
| 15.2 | Search and filter audit logs | 🟢 🔒 |
| 15.3 | Actor, target, action, before/after fields | 🟢 🔒 |
| 15.4 | Export for compliance review | 🟢 🔒 |
| 15.5 | Tamper-evident storage (append-only) | 🟡 🔒 |
| 15.6 | Anomaly detection on audit stream | 🔵 🤖 🔒 |

## 16. AI Assistant (Platform Layer)

| # | Feature | Phase |
|---|---|---|
| 16.1 | Provider-agnostic model layer (OpenAI, Anthropic, Groq, Gemini) | 🟢 🤖 |
| 16.2 | Prompt template registry with versioning | 🟢 🤖 |
| 16.3 | Function calling into services | 🟢 🤖 |
| 16.4 | Conversational memory (per user, per session) | 🟢 🤖 |
| 16.5 | Streaming responses to UI | 🟢 🤖 |
| 16.6 | Token usage & cost tracking | 🟢 🤖 |
| 16.7 | Model fallback on provider outage | 🟡 🤖 |
| 16.8 | MCP tool registration | 🟡 🤖 |
| 16.9 | RAG over approved hospital knowledge sources | 🟡 🤖 |
| 16.10 | AI evaluation harness (regression tests on prompt changes) | 🟡 🤖 |
| 16.11 | Multi-agent workflows | 🔵 🤖 |

## 17. Hospital Settings & Multi-tenancy

| # | Feature | Phase |
|---|---|---|
| 17.1 | Hospital profile (name, address, tax IDs, branding) | 🟢 |
| 17.2 | Departments & specializations | 🟢 |
| 17.3 | Working hours & holidays | 🟢 |
| 17.4 | Currency & locale | 🟢 |
| 17.5 | Feature flags per hospital | 🟢 |
| 17.6 | Branch / multi-location support | 🟡 |
| 17.7 | Multi-tenant data isolation | 🟢 🔒 |

## 18. Platform / Cross-cutting

| # | Feature | Phase |
|---|---|---|
| 18.1 | Health check endpoints | 🟢 |
| 18.2 | Structured logging | 🟢 |
| 18.3 | Error tracking integration | 🟢 |
| 18.4 | Metrics endpoints (Prometheus format) | 🟡 |
| 18.5 | Background job queue | 🟢 |
| 18.6 | Scheduled jobs (nightly reports, cleanups) | 🟢 |
| 18.7 | Redis caching for hot reads | 🟢 |
| 18.8 | Rate limiting per user / IP | 🟢 🔒 |
| 18.9 | Feature flag service | 🟡 |
| 18.10 | Data export (per hospital, for portability) | 🟡 🔒 |

---

## MVP Feature Count

- 🟢 MVP features: **~70**
- 🟡 v2.x features: **~45**
- 🔵 Future features: **~25**
- 🤖 AI-augmented features (all phases): **~20**
- 🔒 Security-critical features: **~20**

MVP is scoped tight. Every 🟢 feature above has (or will have) a corresponding module specification. If a feature is not on this list, it doesn't get built in v2. If a feature is on this list but not in a module spec, the module spec is missing and must be added before implementation.
