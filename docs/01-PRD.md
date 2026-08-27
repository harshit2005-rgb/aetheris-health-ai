# 01 — Product Requirements Document (PRD)

**Product:** Aetheris Health AI
**Version:** v2.0
**Status:** Approved for engineering kickoff
**Owners:** Founding team

---

## 1. Vision

Become the intelligent operating system for hospitals worldwide by combining modern software engineering with trustworthy AI.

## 2. Mission

Build one unified intelligent healthcare platform that simplifies hospital operations using Artificial Intelligence while remaining secure, scalable, modular, and production-ready.

## 3. Problem Statement

Small and medium hospitals today run on a fragmented software stack:

- Separate billing software, separate EMR, separate lab system, separate pharmacy inventory, separate appointment tool.
- Data is siloed. Staff duplicate work across systems.
- AI is either absent or added as a token chatbot with no real workflow integration.
- Enterprise HMS platforms exist but are too expensive, too complex, and require dedicated IT teams.
- Legacy systems are hard to extend and impossible to make AI-native without a rewrite.

The result: doctors and nurses spend hours on data entry, receptionists reconcile records manually, billing errors compound, and clinical decisions are made without the assistive intelligence that is now technically possible.

## 4. Solution

Aetheris Health AI is a single unified platform where:

- Every hospital workflow — registration, appointments, clinical documentation, billing, lab, pharmacy, inventory, reporting — lives in one system with one data model.
- AI is a **platform capability**, not a feature. Every module can call the AI layer to summarize records, draft notes, recommend appointments, forecast inventory, interpret lab reports, or automate administrative work.
- The system is designed as a **modular monolith** for MVP speed and **microservice-ready** for future scale.
- The AI layer is **provider-agnostic** — we can swap between OpenAI, Anthropic, Groq, Gemini, or self-hosted models without changing business logic.
- The platform is **MCP-ready** so future AI agents can safely interact with hospital capabilities through validated tool interfaces.

## 5. Target Users

### 5.1 MVP Users (must support at launch)

| Role | Primary Needs |
|---|---|
| **Super Admin** | Manage multiple hospitals, provision tenants, oversee platform |
| **Hospital Admin** | Manage staff, roles, hospital settings, reports |
| **Doctor** | View patient records, document consultations, use AI summaries |
| **Nurse** | Update vitals, view schedules, patient assignments |
| **Receptionist** | Register patients, book appointments, manage front desk |
| **Billing Staff** | Generate invoices, process payments, manage insurance claims |
| **Lab Technician** | Manage test orders, upload results, interpret with AI |
| **Pharmacist** | Dispense prescriptions, manage stock, drug interactions |
| **Inventory Manager** | Track medical supplies, forecast demand with AI |
| **Patient** | View records, appointments, bills, communicate with hospital |

### 5.2 Future Users

Insurance Staff, Radiology Staff, Government/Regulatory Agencies, Independent Auditors, Telemedicine Providers, Emergency/ICU staff.

## 6. Scope

### 6.1 In Scope for v2 (MVP)

- Authentication (JWT + refresh) with RBAC
- User Management with role and permission assignment
- Patient Management (registration, medical record, history)
- Doctor Management (profile, availability, specialization)
- Appointment Management (booking, rescheduling, cancellation, AI-assisted slot recommendation)
- Billing (invoice generation, payment recording, refunds)
- Reports & Dashboard (operational KPIs, revenue, patient flow)
- Notifications (email + in-app, extensible to SMS/WhatsApp)
- Audit Logs (every significant action logged)
- Hospital Settings (multi-tenant configuration)
- Platform AI Assistant (natural-language interface to hospital data)

### 6.2 In Scope for v2.1 – v2.3

- Laboratory Management
- Pharmacy Management
- Inventory Management
- Insurance claim workflows
- Multi-hospital / multi-tenant hardening

### 6.3 Explicitly Out of Scope (v2)

- Radiology / DICOM imaging
- ICU monitoring integrations
- Operation Theatre scheduling
- Emergency response workflows
- Telemedicine (video consultations)
- Native mobile applications
- Third-party government portal integrations

These are documented in the roadmap but not built in v2.

## 7. Product Principles

1. **AI is a first-class citizen.** Every module has AI capability points designed in, not retrofitted.
2. **Documentation before code.** No feature ships without an approved module specification.
3. **Modularity is non-negotiable.** No module reaches into another module's database. Cross-module traffic goes through services.
4. **Security by default.** Data is encrypted in transit. Sensitive fields are encrypted at rest. Every action is logged.
5. **Enterprise ready from day one.** UUIDs, audit columns, soft delete, transactions, RBAC — even in MVP.
6. **AI cannot make clinical decisions.** AI provides decision support. Clinicians decide. This is a product rule, not just a legal one.
7. **Design for extraction.** Every module must be extractable into its own microservice without rewriting business logic.

## 8. Success Metrics

Success is measured per release milestone. Every release has a gate — miss any critical metric and the milestone doesn't ship. Full detail (with delivery cadence) lives in `14-ROADMAP.md`. This section captures the product-level view.

**Target production launch: January 2027.**
**Code freeze: November 30, 2026.**

### 8.1 Release Gate Metrics

#### Alpha (Sep 6, 2026) — Foundation

| Metric | Target |
|--------|--------|
| Pilot hospital instances | 1 (test) |
| Test coverage on auth flows | 100% |
| Auth endpoint response time | < 200ms p95 |
| Concurrent users supported (staging) | 50 |
| Critical security issues | 0 |
| Multi-tenant isolation test | Passing |
| Open P1 bugs | 0 |

#### Beta (Oct 18, 2026) — Clinical Core

| Metric | Target |
|--------|--------|
| Test hospitals in staging | 3 |
| Staging uptime | 99.5% |
| CRUD response time | < 300ms p95 |
| Concurrent users supported | 100 |
| E2E workflows passing | 2 of 4 |
| Open P1 bugs | < 5 |
| Open P2 bugs | < 20 |

#### Release Candidate (Nov 30, 2026) — Feature-Complete

| Metric | Target |
|--------|--------|
| Pilot hospital environment | 1 (production-like) |
| API response time | < 500ms p95 |
| Concurrent users supported | 500 |
| Uptime achievable (SLA readiness) | 99.9% |
| AI response time | < 3s p95 |
| AI helpful-rating (internal eval, ≥ 50 scenarios) | ≥ 90% |
| AI hallucination rate | < 2% |
| E2E workflows passing | 4 of 4 |
| Critical security issues | 0 |
| Open P1 bugs | < 5 |
| Open P2 bugs | < 20 |

#### Production Launch (Jan 2027)

| Metric | Target |
|--------|--------|
| Hospitals live | 1 |
| Uptime SLA | 99.9% |
| MTTR | < 30 min |
| Incident response time | < 15 min |
| 24/7 monitoring | Yes |
| Data backup RPO / RTO | ≤ 1 hour / ≤ 4 hours |

### 8.2 Product Metrics (6 months post-launch — Jul 2027)

- **Hospitals live:** 3+
- **Onboarding time per hospital:** < 3 days from contract to live
- **Time-to-first-value:** a doctor sees their first AI-summarized patient record within 30 minutes of first login
- **AI adoption rate:** ≥ 40% of clinical notes drafted with AI assist by month 3 post-launch
- **User satisfaction:** ≥ 4.5 / 5
- **Support P1 response:** < 2 hours
- **Support ticket rate:** < 1 ticket per 100 active users per week by month 6

### 8.3 Engineering Metrics (continuous)

- **Test coverage:** ≥ 70% overall, 100% on auth and money-handling paths
- **CRUD response time:** p95 < 300ms
- **AI response time:** p95 < 3s for chat, < 4s for summaries, < 2s for structured extraction
- **Uptime:** 99.9% from launch, targeting 99.95% by end of v2.3
- **Zero critical security incidents**
- **AI cost per hospital:** monitored; alerts on budget breach

### 8.4 Workflow Success (release gate)

The four end-to-end workflows defined in `16-END_TO_END_WORKFLOWS.md` are release gates, not nice-to-haves:

- **Workflow 1 (Patient Journey):** Registration → Appointment → Consultation → Billing → Payment — required for RC
- **Workflow 2 (Doctor Journey):** Login → Schedule → Consultation → Prescription — required for Beta
- **Workflow 3 (Admin Journey):** Setup → User Creation → Configuration → Reports — required for Alpha
- **Workflow 4 (Reception Journey):** Walk-in → Registration → Immediate Slot → Payment — required for RC

**A release without its workflows passing does not ship.**

### 8.5 Business Metrics (indicative, aligned with v2.4 Commercial Launch)

Business KPIs are anchored to the Commercial Launch phase (Q4 2027 – Q1 2028) rather than v2.0 MVP:

- **v2.4 target (~Jan 2028):** 50 hospitals live, 30 paying, onboarding < 3 days, NPS ≥ 40
- **v3.0+ target (2028+):** 200+ hospitals, 3+ countries, marketplace live

Path to profitability documented separately in the business plan (not in engineering docs).

## 9. Constraints & Assumptions

### 9.1 Constraints

- Small founding team — architecture must reward small, focused engineering
- Cannot afford AI provider lock-in — provider abstraction is required from day one
- Must be deployable to modest hardware — SME hospitals will not run Kubernetes clusters
- Must respect Indian healthcare data regulations (DPDP Act) and design forward for HIPAA-equivalent regions

### 9.2 Assumptions

- Hospitals have basic internet connectivity
- Staff have at least basic computer literacy
- Docker is an acceptable deployment target for pilot deployments
- English is the primary UI language for MVP; localization is future scope

## 10. Non-Goals

- We are not building a general-purpose EMR that competes with Epic/Cerner. We are building for hospitals those systems ignore.
- We are not building a consumer health app. Patient-facing UI is minimal; the platform is staff-first.
- We are not building AI models. We orchestrate best-in-class provider models through our AI layer.
- We are not building a chat-only interface. AI augments the UI; it doesn't replace it.

## 11. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| AI provider outage | High | Provider abstraction lets us fail over between vendors |
| Healthcare compliance complexity | High | Design for compliance from day one; audit logs on every action; region-specific compliance modules in roadmap |
| Scope creep from pilot hospitals | High | PRD and module specs are the contract; new asks route through documented change management |
| Founding team bandwidth | Medium | Documentation-first workflow lets AI coding assistants and future hires ramp fast |
| Cost of running provider AI at scale | Medium | Cache aggressively; batch summarization jobs; support self-hosted models in the abstraction |

## 12. Change Management

The PRD, architecture documents, and module specifications are versioned in Git. Changes to any of them require:

1. Written proposal in a pull request against the docs
2. Sign-off from at least one non-author founder
3. Update to the affected module spec before code is written

No verbal architecture changes. Ever.

---

*This PRD is the definitive statement of what we are building. If code contradicts it, code is wrong. If reality demands a change, the PRD updates first.*
