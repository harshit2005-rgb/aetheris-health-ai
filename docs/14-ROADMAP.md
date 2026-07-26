# Aetheris Health AI — Roadmap

**Living document. Owner: Co-founders. Last updated: 2026-07-26.**

This roadmap replaces the initial draft. It reflects the actual delivery plan agreed for v2 and beyond.

---

## Timeline Overview

| Phase | Dates | Outcome |
|-------|-------|---------|
| **Build** | Jul 28 – Nov 30, 2026 (18 weeks) | All v2.0 MVP features complete |
| **Code Freeze** | Nov 30, 2026 | No new features; only critical fixes |
| **Pilot Beta** | Dec 1 – Dec 31, 2026 | Deploy to first pilot hospital, hardening, load testing |
| **Production Launch** | January 2027 | v2.0 live in production |
| **v2.1 Clinical Depth** | Q1–Q2 2027 | Lab, Pharmacy, MCP, SMS |
| **v2.2 Business & Scale** | Q2–Q3 2027 | Inventory, Insurance, multi-tenant hardening |
| **v2.3 Enterprise Readiness** | Q3–Q4 2027 | SSO, compliance, FHIR |
| **v2.4 Commercial Launch** | Q4 2027 – Q1 2028 | Pricing, docs, onboarding, support, customer acquisition |
| **v3.0 Platform Expansion** | 2028+ | Multi-branch, marketplace, international |

See `15-SPRINT_PLAN.md` for the sprint-by-sprint delivery plan of v2.0.

---

## v2.0 — MVP (Aug – Nov 2026)

v2.0 is split into three release tracks to make progress trackable and to allow early integration testing. Each track ends with an internal release milestone with defined acceptance criteria.

### Alpha — Foundation (Aug 10 – Sep 6)

**Modules included:**
- Authentication
- RBAC (roles & permissions)
- User Management
- Hospital Settings (multi-tenancy backbone)
- Dashboard shell (role-based routing)
- Audit Logs foundation

**Definition of done:**
- All modules pass unit + integration tests
- Auth flow (login, refresh, logout, password reset, MFA) works end-to-end
- User CRUD works for all roles
- Multi-tenant isolation validated by cross-tenant read test
- Dashboard renders correctly per role
- Deployed to internal staging

### Beta — Clinical Core (Sep 7 – Oct 18)

**Modules included:**
- Patient Management
- Doctor Management
- Appointment Management

**Definition of done:**
- Full patient lifecycle: register → search → view → edit → archive
- Doctor profile + availability + leave management
- Appointment booking, rescheduling, cancellation, no-show
- Double-booking prevention verified
- Walk-in flow working
- E2E workflows 1 (Patient Journey) and 2 (Doctor Journey) passing
- 3 test hospitals in staging with isolated data

### Release Candidate — Business & AI (Oct 19 – Nov 30)

**Modules included:**
- Billing
- AI Assistant (all 5 milestones — see below)
- Reports & Dashboard (basic analytics)
- Notifications (in-app + email)
- Audit Logs (complete)

**Definition of done:**
- Full invoice → payment → receipt flow
- All AI milestones delivered and instrumented
- Role-specific dashboards with basic analytics
- Notifications delivered reliably (email + in-app)
- All 4 E2E workflows passing
- Performance targets hit (see Success Metrics below)
- Zero critical security issues
- Nov 30 code freeze

---

## AI Milestones (delivered within v2.0 RC track)

AI is not one deliverable — it's a stack of five capabilities, each independently trackable.

| # | Milestone | Sprint | Purpose |
|---|-----------|--------|---------|
| 1 | **AI Chat** | 6 | Basic conversational interface. Provider abstraction (Groq default, others swappable). Streaming SSE responses. Chat sessions and messages persisted per hospital. |
| 2 | **Function Calling** | 6 | AI can invoke module services as typed tools (e.g., `search_patients`, `list_appointments`). Every tool call goes through the standard service layer (permissions, audit, tenancy enforced). |
| 3 | **Hospital Memory** | 7 | Conversational memory in Redis, scoped to hospital + user + session. Context window management. Configurable retention. |
| 4 | **RAG** | 7 | Retrieval-augmented generation over hospital documents (SOPs, formularies, past summaries) using pgvector. Per-hospital knowledge base. |
| 5 | **AI Observability** | 8 | Interaction logging (`ai_interactions` table), token/cost tracking per hospital, safety monitoring, prompt version tracking, eval harness. Budget enforcement. |

Each milestone has its own acceptance test and appears in release notes independently.

---

## v2.0 Baseline (in from Day 1, not later)

These are architectural commitments, not features to add later:

- **Multi-tenant architecture** — every table with `hospital_id`, base repository enforces filter. Even if we launch with one hospital, the isolation is real and tested.
- **API versioning** — every endpoint under `/api/v1/`. Deprecation policy documented.
- **Basic analytics** — dashboard metrics (patient count, appointments today, revenue this month, top diagnoses) available from launch.
- **Full audit logging** — every mutating operation logged, immutable table.
- **Feature flags per hospital** — even if we don't toggle much in v2.0, the framework is in place.

Everything above ships in v2.0. There is no "we'll add multi-tenancy later" version.

---

## v2.0 Success Metrics

Every release track has measurable acceptance criteria. Miss any critical metric = the milestone doesn't ship.

### Alpha (Sep 6, 2026)

| Category | Target |
|----------|--------|
| Pilot hospitals | 1 test instance |
| Test coverage (auth flows) | 100% |
| Auth endpoint response time | < 200ms p95 |
| Concurrent users supported | 50 (staging) |
| Critical security issues | 0 |
| Multi-tenant isolation test | Passing |
| Open P1 bugs | 0 |

### Beta (Oct 18, 2026)

| Category | Target |
|----------|--------|
| Test hospitals in staging | 3 |
| Staging uptime | 99.5% |
| Core CRUD response time | < 300ms p95 |
| Concurrent users supported | 100 |
| E2E workflows passing | 2 of 4 |
| Open P1 bugs | < 5 |
| Open P2 bugs | < 20 |

### Release Candidate (Nov 30, 2026)

| Category | Target |
|----------|--------|
| Pilot hospital environments | 1 production-like |
| API response time | < 500ms p95 |
| Concurrent users supported | 500 |
| Uptime achievable (SLA readiness) | 99.9% |
| AI response time | < 3s p95 |
| AI helpful-rating on internal eval set | ≥ 90% |
| AI hallucination rate on eval set | < 2% |
| E2E workflows passing | 4 of 4 |
| Critical security issues | 0 |
| Open P1 bugs | < 5 |
| Open P2 bugs | < 20 |
| Code freeze | Nov 30 met |

### Production Launch (Jan 2027)

| Category | Target |
|----------|--------|
| Hospitals live | 1 |
| Uptime SLA | 99.9% |
| MTTR (mean time to recovery) | < 30 min |
| Incident response time | < 15 min |
| 24/7 monitoring | Yes |
| Data backup RPO | ≤ 1 hour |
| Data backup RTO | ≤ 4 hours |

### Operational Success (6 months post-launch, ~Jul 2027)

| Category | Target |
|----------|--------|
| Hospitals live | 3+ |
| Uptime | 99.9% |
| User satisfaction score | ≥ 4.5 / 5 |
| Support ticket P1 response | < 2 hours |
| AI helpful-rating (production) | ≥ 85% |
| Open P1 bugs at any time | < 10 |

---

## End-to-End Workflows (must-pass before RC)

Modules can be individually correct and still fail together. v2.0 acceptance requires four end-to-end workflows to pass — see `16-END_TO_END_WORKFLOWS.md` for full details.

| # | Workflow | Blocks release at |
|---|----------|-------------------|
| 1 | Patient Journey (Registration → Appointment → Consultation → Billing → Payment) | RC |
| 2 | Doctor Journey (Login → Schedule → Consultation → Prescription → Notes) | Beta |
| 3 | Admin Journey (Hospital Setup → User Creation → Configuration → Reports) | Alpha |
| 4 | Reception Journey (Walk-in → Registration → Immediate Slot → Payment) | RC |

---

## v2.1 — Clinical Depth (Q1–Q2 2027)

**New modules:**
- Laboratory (test catalog, orders, sample tracking, reports, AI lay-language explanation)
- Pharmacy (medicine catalog, batches, FIFO dispensing, drug interactions, POs)
- SMS notifications (Twilio/MSG91)

**Platform improvements:**
- MCP (Model Context Protocol) integration — external tools available to AI Assistant
- AI provider fallback (primary + secondary provider auto-switch)
- Prompt A/B testing framework
- Prescription printing with letterhead
- Bulk data import wizard

### Success Metrics (v2.1)

| Category | Target |
|----------|--------|
| Hospitals live | 3–5 |
| Uptime | 99.9% |
| Lab report generation time | < 10s |
| Pharmacy dispensing accuracy | 100% (no wrong batch) |
| AI provider fallback time | < 2s |
| MCP tools integrated | ≥ 3 (calendar, EHR reference, drug DB) |

---

## v2.2 — Business & Scale (Q2–Q3 2027)

**New modules:**
- Inventory management
- Insurance claims workflow
- Custom fields per hospital
- Multi-branch support (one hospital, multiple locations)

**Platform improvements:**
- Advanced reporting (custom report builder)
- Data warehousing for cross-hospital analytics (Superadmin only)
- Rate limiting per plan tier
- Audit log partitioning
- Performance testing at 5000 concurrent users
- Redis Sentinel for cache HA

### Success Metrics (v2.2)

| Category | Target |
|----------|--------|
| Hospitals live | 10+ |
| Uptime | 99.95% |
| Peak concurrent users | 2000 |
| Custom report generation | < 30s |
| Inventory accuracy | ≥ 99% vs physical count |

---

## v2.3 — Enterprise Readiness (Q3–Q4 2027)

**New capabilities:**
- SSO / SAML for enterprise customers
- Advanced RBAC (custom roles per hospital, permission delegation)
- HL7 FHIR integration for interoperability
- Compliance certifications (ISO 27001 prep, SOC 2 Type I preparation)
- Configurable data retention per hospital (regulatory floors respected)
- Dedicated data residency options
- Kubernetes deployment (moving from docker-compose)

### Success Metrics (v2.3)

| Category | Target |
|----------|--------|
| Hospitals live | 25+ |
| Enterprise customers (SSO users) | 3+ |
| Uptime | 99.95% |
| FHIR-compliant endpoints | Patient, Encounter, Observation |
| Compliance audit | ISO 27001 gap analysis complete |

---

## v2.4 — Commercial Launch (Q4 2027 – Q1 2028)

Before expanding into v3.0 platform features, we invest a phase in **commercializing what we have**. Great product, unshipped commercial motion = zero customers.

**Deliverables:**
- **Pricing tiers formalized:** Starter / Professional / Enterprise, published pricing page
- **Customer-facing documentation portal:** self-serve knowledge base
- **Self-service onboarding flow:** hospital sign-up → provisioning → first user in < 15 minutes
- **Support ticketing + SLA framework:** ticket system, defined SLAs by tier, escalation paths
- **Sales enablement materials:** decks, one-pagers, ROI calculator, demo scripts
- **Marketing site launch:** product pages, case studies, blog, SEO
- **Customer acquisition funnel:** lead capture, CRM (HubSpot/Zoho), nurture sequences
- **Billing infrastructure (SaaS):** subscription management, invoicing, dunning
- **Customer success playbook:** onboarding checklist, health scores, QBRs

### Success Metrics (v2.4)

| Category | Target |
|----------|--------|
| Hospitals live (total) | 50+ |
| Paying hospitals | 30+ |
| Monthly Recurring Revenue | Target set with co-founders |
| Onboarding time (new hospital) | < 3 days from contract to live |
| Support P1 response | < 2 hours |
| Support P2 response | < 8 hours |
| NPS | ≥ 40 |
| Marketing site → trial conversion | ≥ 5% |

**Why this exists as a phase:** Product-market fit needs a product AND a market motion. Building v3.0 features while ignoring commercial fundamentals is how startups die with a great codebase and no customers.

---

## v3.0 — Platform Expansion (2028+)

**Platform-level features:**
- Multi-branch per hospital (already scaffolded in v2.2)
- White-label reseller mode
- Public API for third-party integrations (with dev portal, keys, rate limits, docs)
- Marketplace for hospital add-ons (third-party plugins)
- International expansion: localization (multi-language UI), multi-currency, regional compliance (HIPAA-US, GDPR-EU)
- Advanced AI: fine-tuned hospital-specific models, custom RAG pipelines
- Mobile apps (patient-facing + staff-facing)
- Telemedicine module (video consultations)

### Success Metrics (v3.0)

| Category | Target |
|----------|--------|
| Hospitals live | 200+ |
| Countries served | 3+ |
| Marketplace partners | 10+ |
| Public API integrations | 20+ |
| Mobile app rating | ≥ 4.5 stars |

---

## Continuous Investments (every release)

These are ongoing tracks with no fixed release date:

- **Security:** quarterly penetration tests, dependency updates, secrets rotation, security review of every new module
- **Performance:** monthly load tests, query optimization, cache tuning
- **AI quality:** eval set expansion, prompt regression testing, cost monitoring
- **Documentation:** internal docs kept current, customer docs updated per release
- **Developer experience:** CI/CD improvements, local dev speedups, better error messages
- **Accessibility:** WCAG 2.1 AA compliance progressive rollout
- **Observability:** metric coverage, log quality, dashboard curation

---

## Explicitly NOT on the Roadmap

Saying no is as important as saying yes. These are not being built, and pushing back on them protects our focus:

- **Blockchain / Web3 anything** — no legitimate use case for hospital operations
- **Building our own foundation LLM** — we're a product company, not a research lab
- **Fully custom UI framework** — we use React + Shadcn, we don't reinvent
- **Real-time video for consultations before v3.0** — separate specialty, distraction from core
- **HIPAA compliance for US market before v3.0** — India-first, US only after Indian PMF proven
- **Multi-cloud deployment** — one cloud (AWS), well-run, until scale demands otherwise
- **On-premises deployment for small hospitals** — SaaS-first, on-prem is enterprise-only after v2.3

If someone asks for one of these, refer them to this list. If they think it's critical, we discuss it at a founders' meeting — not in a Slack thread.

---

## Roadmap Change Log

| Date | Change | Approved by |
|------|--------|-------------|
| 2026-07-26 | Initial roadmap draft | — |
| 2026-07-26 | Restructured: Alpha/Beta/RC tracks for v2.0; AI split into 5 milestones; success metrics per release; Commercial Launch phase inserted at v2.4; multi-tenant/API-versioning/analytics moved to v2.0 baseline; timeline updated to Nov 30 code freeze / Jan 2027 launch | Sanjeev, co-founders |

---

## Notes for the Team

- Milestones are **hard**, not aspirational. Missing a milestone = we cut scope (per the pre-agreed cut list in the sprint plan), not schedule.
- Success metrics are the release gate. A feature that ships without meeting its metric is not "done."
- Roadmap is reviewed at the end of every sprint. Changes require co-founder sign-off and land here in the Change Log.
- If a customer/investor asks "what's on the roadmap?" — this document is the answer. Nothing else counts.
