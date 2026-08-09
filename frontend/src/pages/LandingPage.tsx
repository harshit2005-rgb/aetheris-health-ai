import { Link } from 'react-router-dom'
import { Icon } from '@/components/ui/icon'
import MarketingNav from '@/components/layout/MarketingNav'
import MarketingFooter from '@/components/layout/MarketingFooter'

const STEPS = [
  {
    icon: 'hub',
    title: 'Connect',
    body: 'Ingest EHR, imaging, and bedside device data into one live view.',
  },
  {
    icon: 'neurology',
    title: 'Analyze',
    body: 'AI reviews vitals, scans, and history the moment they arrive.',
  },
  {
    icon: 'smart_toy',
    title: 'Recommend',
    body: 'Agents surface the next step and flag risks for your approval.',
  },
]

const OUTCOMES = [
  {
    icon: 'bolt',
    title: 'Act faster',
    body: 'Findings surface the instant data arrives, so triage never waits on a full schedule.',
  },
  {
    icon: 'health_and_safety',
    title: 'Miss less',
    body: 'Agentic review catches the anomalies a long clinical shift can easily overlook.',
  },
  {
    icon: 'schedule',
    title: 'Less admin',
    body: 'One unified record cuts the time your team spends hunting for patient context.',
  },
]

const CAPABILITIES = [
  {
    to: '/diagnostics',
    icon: 'clinical_notes',
    title: 'AI Diagnostic Engine',
    body: 'Analyze scans, labs, and vitals in real time, with an agentic second opinion on every finding.',
  },
  {
    to: '/records',
    icon: 'folder_shared',
    title: 'Clinical Records',
    body: 'Every patient history, medication, and result in one searchable, HIPAA-aligned record.',
  },
  {
    to: '/diagnostics',
    icon: 'monitor_heart',
    title: 'Real-time Vitals',
    body: 'Live heart rate, blood pressure, and oxygen tracking with instant anomaly alerts.',
  },
  {
    to: '/dashboard',
    icon: 'smart_toy',
    title: 'Agentic Recommendations',
    body: 'AI agents surface the next step and flag risks. You approve every decision.',
  },
]

export default function LandingPage() {
  return (
    <div className="min-h-screen overflow-x-hidden">
      <MarketingNav />

      {/* Hero */}
      <section className="px-container-padding relative mx-auto max-w-7xl pt-28 pb-12 md:pt-40 md:pb-section-margin">
        <div className="from-secondary-fixed/20 absolute inset-0 -z-10 rounded-3xl bg-gradient-to-br to-transparent opacity-50 blur-3xl" />
        <div className="gap-gutter grid items-center md:grid-cols-12">
          {/* Copy */}
          <div className="space-y-6 md:col-span-6 md:space-y-8">
            <div className="glassmorphism shadow-neo-base inline-block rounded-full px-4 py-2">
              <span className="font-label text-label-caps text-secondary font-bold tracking-wider">
                AGENTIC CLINICAL INTELLIGENCE
              </span>
            </div>
            <h1 className="font-display text-gradient text-[2rem] font-extrabold leading-[1.1] tracking-tight sm:text-4xl md:text-headline-xl">
              Confident clinical decisions, powered by agentic AI.
            </h1>
            <p className="font-body text-body-md text-on-surface-variant max-w-lg">
              Aetheris unifies scans, records, and live vitals, analyzes them in real time, and
              recommends the next step for your team.
            </p>
            <div className="flex flex-wrap gap-4 pt-4">
              <Link
                to="/signup"
                className="shadow-neo-base text-on-primary bg-primary text-body-md rounded-xl px-8 py-4 font-bold transition-all duration-300 hover:-translate-y-1 hover:shadow-lg active:translate-y-0"
              >
                Get Started
              </Link>
              <Link
                to="/how-it-works"
                className="glassmorphism shadow-neo-base text-primary text-body-md flex items-center gap-2 rounded-xl px-8 py-4 font-bold transition-all duration-300 hover:bg-white/50"
              >
                See how it works
                <Icon name="arrow_forward" className="text-lg" />
              </Link>
            </div>
          </div>

          {/* "How Aetheris works" stepper */}
          <div className="relative md:col-span-6">
            <div className="from-secondary-fixed to-primary-fixed absolute -inset-4 z-0 rounded-[2rem] bg-gradient-to-tr opacity-20 blur-2xl" />
            <div className="bg-surface/80 shadow-neo-base relative z-10 rounded-[2rem] border border-white/60 p-8 backdrop-blur-xl">
              <p className="font-label text-label-caps text-outline mb-6">HOW AETHERIS WORKS</p>
              <ol className="space-y-2">
                {STEPS.map((step, i) => (
                  <li key={step.title} className="relative flex gap-4 pb-6 last:pb-0">
                    {i < STEPS.length - 1 && (
                      <span className="bg-outline-variant/40 absolute top-12 left-[23px] h-[calc(100%-2.5rem)] w-px" />
                    )}
                    <span className="neo-extruded bg-secondary/10 text-secondary z-10 flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full">
                      <Icon name={step.icon} filled />
                    </span>
                    <div className="pt-1">
                      <h3 className="font-display text-title-lg text-primary font-bold">
                        {step.title}
                      </h3>
                      <p className="font-body text-body-sm text-on-surface-variant mt-1">
                        {step.body}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>
      </section>

      {/* How it helps — outcomes (divider layout, not cards) */}
      <section className="px-container-padding mx-auto mt-8 max-w-7xl">
        <div className="mb-8 max-w-2xl">
          <h2 className="font-display text-headline-lg text-primary">
            Built to give clinicians time and confidence back.
          </h2>
        </div>
        <div className="grid gap-8 md:grid-cols-3">
          {OUTCOMES.map((o) => (
            <div key={o.title} className="border-outline-variant/40 border-t pt-6">
              <span className="bg-secondary/10 text-secondary mb-4 flex h-11 w-11 items-center justify-center rounded-xl">
                <Icon name={o.icon} filled />
              </span>
              <h3 className="font-display text-title-lg text-primary font-bold">{o.title}</h3>
              <p className="font-body text-body-sm text-on-surface-variant mt-2">{o.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Capabilities */}
      <section id="capabilities" className="px-container-padding mx-auto mt-16 max-w-7xl scroll-mt-28">
        <div className="mb-10 max-w-2xl">
          <h2 className="font-display text-headline-lg text-primary">
            Everything a clinician needs, in one intelligent surface.
          </h2>
          <p className="font-body text-body-md text-on-surface-variant mt-3">
            Aetheris connects diagnostics, records, and live monitoring so the whole clinical
            workflow runs in a single place.
          </p>
        </div>

        {/* Asymmetric bento: tall dark lead tile + three lighter tiles */}
        <div className="grid gap-5 md:grid-cols-3 md:grid-rows-2">
          <Link
            to={CAPABILITIES[0].to}
            className="bg-primary-container shadow-glass-panel group relative flex flex-col justify-between overflow-hidden rounded-2xl p-8 transition-transform duration-300 hover:-translate-y-1 md:row-span-2"
          >
            <div className="bg-secondary-container/20 absolute -top-10 -right-10 h-40 w-40 rounded-full blur-2xl" />
            <div className="bg-secondary/20 text-secondary-container flex h-12 w-12 items-center justify-center rounded-xl">
              <Icon name={CAPABILITIES[0].icon} filled />
            </div>
            <div className="relative">
              <h3 className="font-display text-headline-md font-bold text-white">
                {CAPABILITIES[0].title}
              </h3>
              <p className="font-body text-body-sm mt-2 text-white/70">{CAPABILITIES[0].body}</p>
              <span className="font-label text-label-caps text-secondary-container mt-5 inline-flex items-center gap-1">
                Explore
                <Icon name="arrow_forward" className="text-base transition-transform group-hover:translate-x-1" />
              </span>
            </div>
          </Link>

          {CAPABILITIES.slice(1).map((cap, i) => (
            <Link
              key={cap.title}
              to={cap.to}
              className={`neo-extruded bg-surface group flex flex-col gap-3 rounded-2xl p-6 transition-transform duration-300 hover:-translate-y-1 ${
                i === 2 ? 'md:col-span-2' : ''
              }`}
            >
              <div className="bg-secondary/10 text-secondary flex h-11 w-11 items-center justify-center rounded-xl">
                <Icon name={cap.icon} filled />
              </div>
              <h3 className="font-display text-title-lg text-primary font-bold">{cap.title}</h3>
              <p className="font-body text-body-sm text-on-surface-variant">{cap.body}</p>
            </Link>
          ))}
        </div>
      </section>

      {/* Closing CTA */}
      <section className="px-container-padding mx-auto mt-16 max-w-7xl">
        <div className="glassmorphism shadow-glass-panel relative overflow-hidden rounded-3xl px-8 py-14 text-center">
          <div className="from-secondary-fixed/30 absolute inset-0 -z-10 bg-gradient-to-br to-transparent blur-3xl" />
          <h2 className="font-display text-headline-lg text-gradient mx-auto max-w-2xl">
            Bring agentic intelligence to your hospital.
          </h2>
          <p className="font-body text-body-md text-on-surface-variant mx-auto mt-3 max-w-md">
            See how Aetheris deploys into your existing clinical workflow.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-4">
            <Link
              to="/signup"
              className="shadow-neo-base text-on-primary bg-primary text-body-md inline-block rounded-xl px-8 py-4 font-bold transition-all duration-300 hover:-translate-y-1 active:translate-y-0"
            >
              Get Started
            </Link>
            <Link
              to="/how-it-works"
              className="glassmorphism shadow-neo-base text-primary text-body-md inline-block rounded-xl px-8 py-4 font-bold transition-all duration-300 hover:bg-white/50"
            >
              For Hospitals
            </Link>
          </div>
        </div>
      </section>

      <MarketingFooter />
    </div>
  )
}
