import { Link } from 'react-router-dom'
import { Icon } from '@/components/ui/icon'
import MarketingNav from '@/components/layout/MarketingNav'
import MarketingFooter from '@/components/layout/MarketingFooter'

const PHASES = [
  {
    icon: 'search_insights',
    title: 'Assess & scope',
    body: 'We map your departments, data sources, and clinical workflows, then agree on the first units to go live.',
    duration: 'Week 1–2',
  },
  {
    icon: 'cable',
    title: 'Integrate data',
    body: 'Connect your EHR, imaging, and device feeds over FHIR and HL7. No rip-and-replace of existing systems.',
    duration: 'Week 2–4',
  },
  {
    icon: 'school',
    title: 'Train & onboard',
    body: 'Clinicians learn the workspace in a half-day session. Agents are tuned to your protocols and specialties.',
    duration: 'Week 4–5',
  },
  {
    icon: 'rocket_launch',
    title: 'Go live & monitor',
    body: 'Roll out ward by ward with a dedicated success engineer tracking accuracy and adoption alongside you.',
    duration: 'Week 6+',
  },
]

const INTEGRATIONS = [
  { icon: 'health_metrics', label: 'EHR systems', note: 'Epic, Cerner, Meditech via FHIR APIs' },
  { icon: 'radiology', label: 'Imaging (PACS)', note: 'DICOM studies streamed for analysis' },
  { icon: 'monitor_heart', label: 'Bedside devices', note: 'Live vitals over HL7 feeds' },
  { icon: 'labs', label: 'Lab systems', note: 'Results ingested as they resolve' },
]

const COMPLIANCE = [
  { icon: 'lock', title: 'HIPAA & SOC 2', body: 'Audited controls, encryption in transit and at rest.' },
  { icon: 'dns', title: 'Your infrastructure', body: 'Deploy in private cloud or fully on-premise.' },
  { icon: 'manage_accounts', title: 'Role-based access', body: 'Granular permissions with full audit trails.' },
]

export default function HowItWorksPage() {
  return (
    <div className="relative min-h-screen overflow-x-hidden">
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="bg-primary-fixed-dim/30 absolute -top-[10%] -left-[5%] h-96 w-96 rounded-full blur-3xl" />
        <div className="bg-secondary-fixed/30 absolute right-[-10%] bottom-[20%] h-[500px] w-[500px] rounded-full blur-3xl" />
      </div>

      <MarketingNav />

      <main className="px-container-padding mx-auto max-w-7xl pt-28 pb-16 md:pt-36">
        {/* Hero */}
        <div className="mb-16 max-w-3xl">
          <p className="font-label text-label-caps text-secondary mb-4 font-bold tracking-wider">
            FOR HOSPITALS
          </p>
          <h1 className="font-display text-headline-xl text-primary">
            Deployed into your hospital in weeks, not years.
          </h1>
          <p className="font-body text-body-md text-on-surface-variant mt-4 max-w-xl">
            Aetheris layers onto the systems you already run. No rip-and-replace, no year-long
            migration, and your team stays in control the whole way.
          </p>
        </div>

        {/* Rollout phases */}
        <section className="mb-20">
          <h2 className="font-display text-headline-lg text-primary mb-8">A guided rollout</h2>
          <div className="grid gap-5 md:grid-cols-4">
            {PHASES.map((phase, i) => (
              <div
                key={phase.title}
                className="neo-extruded bg-surface relative flex flex-col rounded-2xl p-6"
              >
                <span className="font-display text-secondary/30 absolute top-4 right-5 text-4xl font-extrabold">
                  {i + 1}
                </span>
                <span className="bg-secondary/10 text-secondary mb-4 flex h-12 w-12 items-center justify-center rounded-xl">
                  <Icon name={phase.icon} filled />
                </span>
                <h3 className="font-display text-title-lg text-primary font-bold">{phase.title}</h3>
                <p className="font-body text-body-sm text-on-surface-variant mt-2 flex-1">
                  {phase.body}
                </p>
                <span className="font-label text-label-caps text-outline mt-4">
                  {phase.duration}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Integrations */}
        <section className="mb-20">
          <div className="mb-8 max-w-2xl">
            <h2 className="font-display text-headline-lg text-primary">
              Works with the systems you already run.
            </h2>
            <p className="font-body text-body-md text-on-surface-variant mt-3">
              Aetheris connects through open healthcare standards, so your data stays where it lives.
            </p>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {INTEGRATIONS.map((item) => (
              <div key={item.label} className="neo-pressed bg-surface rounded-2xl p-6">
                <Icon name={item.icon} className="text-secondary mb-3 text-3xl" />
                <h3 className="font-body text-body-md text-primary font-bold">{item.label}</h3>
                <p className="font-body text-body-sm text-on-surface-variant mt-1">{item.note}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Compliance */}
        <section className="mb-16">
          <div className="bg-primary-container relative overflow-hidden rounded-3xl p-10">
            <div className="bg-secondary-container/20 absolute -top-16 -right-16 h-64 w-64 rounded-full blur-3xl" />
            <div className="relative">
              <h2 className="font-display text-headline-lg mb-8 font-bold text-white">
                Secure and compliant by design.
              </h2>
              <div className="grid gap-8 md:grid-cols-3">
                {COMPLIANCE.map((c) => (
                  <div key={c.title}>
                    <span className="bg-secondary/20 text-secondary-container mb-4 flex h-11 w-11 items-center justify-center rounded-xl">
                      <Icon name={c.icon} filled />
                    </span>
                    <h3 className="font-display text-title-lg font-bold text-white">{c.title}</h3>
                    <p className="font-body text-body-sm mt-2 text-white/70">{c.body}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* CTA */}
        <div className="text-center">
          <h2 className="font-display text-headline-md text-primary">
            Ready to scope your rollout?
          </h2>
          <div className="mt-6 flex flex-wrap justify-center gap-4">
            <Link
              to="/signup"
              className="shadow-neo-base bg-primary text-on-primary text-body-md inline-block rounded-xl px-8 py-4 font-bold transition-all hover:-translate-y-1"
            >
              Get Started
            </Link>
            <Link
              to="/technology"
              className="glassmorphism shadow-neo-base text-primary text-body-md inline-block rounded-xl px-8 py-4 font-bold transition-all hover:bg-white/50"
            >
              Explore the technology
            </Link>
          </div>
        </div>
      </main>

      <MarketingFooter />
    </div>
  )
}
