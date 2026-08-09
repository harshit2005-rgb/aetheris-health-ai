import { Link } from 'react-router-dom'
import { Icon } from '@/components/ui/icon'
import MarketingNav from '@/components/layout/MarketingNav'
import MarketingFooter from '@/components/layout/MarketingFooter'

const PILLARS = [
  {
    icon: 'smart_toy',
    title: 'Agentic orchestration',
    body: 'Specialized AI agents review each case in parallel, reason over the evidence, and escalate only what needs a human. Every recommendation is explainable and traceable.',
  },
  {
    icon: 'bolt',
    title: 'Real-time pipeline',
    body: 'A streaming data layer processes vitals, labs, and imaging the moment they arrive, so analysis keeps pace with the bedside instead of running overnight.',
  },
  {
    icon: 'sync_alt',
    title: 'Interoperability',
    body: 'Native FHIR and HL7 support plus DICOM ingestion means Aetheris speaks the languages your EHR, PACS, and devices already use.',
  },
  {
    icon: 'security',
    title: 'Security core',
    body: 'End-to-end encryption, role-based access, and immutable audit logs are built into every layer, not bolted on afterward.',
  },
]

const STACK = [
  {
    group: 'Frontend',
    icon: 'devices',
    items: ['React 19 + TypeScript', 'Vite build tooling', 'Tailwind CSS + shadcn/ui', 'TanStack Query'],
  },
  {
    group: 'Backend & AI',
    icon: 'dns',
    items: ['Python + FastAPI services', 'Agentic LLM orchestration', 'Streaming inference', 'Vector + relational stores'],
  },
  {
    group: 'Data & standards',
    icon: 'hub',
    items: ['HL7 FHIR APIs', 'DICOM imaging', 'HL7 v2 device feeds', 'Event-driven ingestion'],
  },
]

const SECURITY = [
  { icon: 'enhanced_encryption', title: 'Encrypted end to end', body: 'TLS in transit, AES-256 at rest.' },
  { icon: 'badge', title: 'Role-based access', body: 'Least-privilege permissions per role.' },
  { icon: 'history_edu', title: 'Immutable audit logs', body: 'Every access and action is recorded.' },
  { icon: 'verified_user', title: 'HIPAA & SOC 2', body: 'Independently audited controls.' },
]

export default function TechnologyPage() {
  return (
    <div className="relative min-h-screen overflow-x-hidden">
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="bg-secondary-fixed/30 absolute -top-[10%] right-[-5%] h-96 w-96 rounded-full blur-3xl" />
        <div className="bg-primary-fixed-dim/30 absolute bottom-[10%] left-[-10%] h-[500px] w-[500px] rounded-full blur-3xl" />
      </div>

      <MarketingNav />

      <main className="px-container-padding mx-auto max-w-7xl pt-28 pb-16 md:pt-36">
        {/* Hero */}
        <div className="mb-16 max-w-3xl">
          <p className="font-label text-label-caps text-secondary mb-4 font-bold tracking-wider">
            TECHNOLOGY
          </p>
          <h1 className="font-display text-headline-xl text-primary">
            The platform behind the intelligence.
          </h1>
          <p className="font-body text-body-md text-on-surface-variant mt-4 max-w-xl">
            Aetheris is built for the realities of clinical environments: real-time data, strict
            compliance, and decisions that a clinician has to trust and defend.
          </p>
        </div>

        {/* Architecture pillars */}
        <section className="mb-20">
          <h2 className="font-display text-headline-lg text-primary mb-8">How it is built</h2>
          <div className="grid gap-5 md:grid-cols-2">
            {PILLARS.map((p) => (
              <div key={p.title} className="neo-extruded bg-surface rounded-2xl p-8">
                <span className="bg-secondary/10 text-secondary mb-5 flex h-12 w-12 items-center justify-center rounded-xl">
                  <Icon name={p.icon} filled />
                </span>
                <h3 className="font-display text-title-lg text-primary font-bold">{p.title}</h3>
                <p className="font-body text-body-sm text-on-surface-variant mt-2">{p.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Stack */}
        <section className="mb-20">
          <div className="mb-8 max-w-2xl">
            <h2 className="font-display text-headline-lg text-primary">A modern, proven stack.</h2>
            <p className="font-body text-body-md text-on-surface-variant mt-3">
              Nothing exotic. We build on the tools clinical engineering teams can maintain and
              audit.
            </p>
          </div>
          <div className="grid gap-5 md:grid-cols-3">
            {STACK.map((col) => (
              <div key={col.group} className="neo-pressed bg-surface rounded-2xl p-6">
                <div className="mb-4 flex items-center gap-3">
                  <Icon name={col.icon} className="text-secondary text-2xl" />
                  <h3 className="font-display text-title-lg text-primary font-bold">{col.group}</h3>
                </div>
                <ul className="space-y-3">
                  {col.items.map((item) => (
                    <li key={item} className="font-body text-body-sm text-on-surface flex items-center gap-2">
                      <Icon name="check" className="text-secondary text-base" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>

        {/* Security */}
        <section className="mb-16">
          <div className="mb-8 max-w-2xl">
            <h2 className="font-display text-headline-lg text-primary">
              Security is the foundation, not a feature.
            </h2>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {SECURITY.map((s) => (
              <div key={s.title} className="border-outline-variant/40 border-t pt-6">
                <Icon name={s.icon} className="text-secondary mb-3 text-3xl" />
                <h3 className="font-body text-body-md text-primary font-bold">{s.title}</h3>
                <p className="font-body text-body-sm text-on-surface-variant mt-1">{s.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* CTA */}
        <div className="text-center">
          <h2 className="font-display text-headline-md text-primary">
            Want the deployment details?
          </h2>
          <div className="mt-6 flex flex-wrap justify-center gap-4">
            <Link
              to="/how-it-works"
              className="shadow-neo-base bg-primary text-on-primary text-body-md inline-block rounded-xl px-8 py-4 font-bold transition-all hover:-translate-y-1"
            >
              See how we deploy
            </Link>
            <Link
              to="/pricing"
              className="glassmorphism shadow-neo-base text-primary text-body-md inline-block rounded-xl px-8 py-4 font-bold transition-all hover:bg-white/50"
            >
              View pricing
            </Link>
          </div>
        </div>
      </main>

      <MarketingFooter />
    </div>
  )
}
