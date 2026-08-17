import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Users,
  CalendarDays,
  Receipt,
  Pill,
  BarChart3,
  Sparkles,
  ShieldCheck,
  Lock,
  BadgeCheck,
  Server,
  UserPlus,
  Stethoscope,
  FlaskConical,
} from 'lucide-react'
import MarketingNav from '@/components/layout/MarketingNav'
import MarketingFooter from '@/components/layout/MarketingFooter'
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from '@/components/ui/accordion'

// Compliance standards (not customer logos — honest signals for a healthcare buyer).
const COMPLIANCE = [
  { icon: ShieldCheck, label: 'HIPAA aligned' },
  { icon: BadgeCheck, label: 'SOC 2 Type II' },
  { icon: Lock, label: 'End-to-end encryption' },
  { icon: Server, label: 'Cloud or on-premise' },
]

// The clinical journey the platform runs end to end (Spec 2A workflow).
const WORKFLOW = [
  { icon: UserPlus, title: 'Register', body: 'Admit a patient and open their record in seconds.' },
  { icon: CalendarDays, title: 'Schedule', body: 'Book the right doctor into an open slot.' },
  { icon: Stethoscope, title: 'Diagnose', body: 'Chart vitals and history in one clinical view.' },
  { icon: FlaskConical, title: 'Treat', body: 'Order labs and prescriptions, track results.' },
  { icon: Receipt, title: 'Bill', body: 'Generate the invoice and reconcile payment.' },
]

const OUTCOMES = [
  {
    title: 'Less time hunting for context',
    body: 'One record holds every result, note, and medication, so staff stop switching between systems.',
  },
  {
    title: 'Fewer things slip through',
    body: 'The AI Copilot flags risks and pending work for review, backing up a long clinical shift.',
  },
  {
    title: 'Faster front desk',
    body: 'Registration, scheduling, and billing share one workflow instead of three disconnected tools.',
  },
]

const FAQ = [
  {
    q: 'Is patient data secure and HIPAA aligned?',
    a: 'Every record is encrypted in transit and at rest, access is scoped by role, and every change is written to an immutable audit log. We operate to HIPAA and SOC 2 Type II controls.',
  },
  {
    q: 'Does the AI make clinical decisions on its own?',
    a: 'No. The AI Copilot surfaces findings, risks, and next steps as suggestions. A clinician reviews and approves every action. The platform is a decision-support tool, not an autonomous one.',
  },
  {
    q: 'Can it run on our own infrastructure?',
    a: 'Yes. Aetheris deploys to our managed cloud or to your own environment, so data can stay inside your network where policy requires it.',
  },
  {
    q: 'Will it connect to our existing EHR and lab systems?',
    a: 'The platform is built around standard integration seams for records, imaging, and lab results. Our team scopes the connections your hospital needs during onboarding.',
  },
  {
    q: 'How long does implementation take?',
    a: 'A single department can be live in a few weeks. A full multi-department rollout is phased with your team so day-to-day care is never interrupted.',
  },
]

/** Module card — informational (public visitors are not signed in), no app link. */
function ModuleCard({
  icon: Icon,
  title,
  body,
  className,
  dark,
}: {
  icon: typeof Users
  title: string
  body: string
  className?: string
  dark?: boolean
}) {
  return (
    <div
      className={[
        'flex flex-col gap-3 rounded-2xl p-6',
        dark ? 'bg-primary-container relative overflow-hidden' : 'neo-extruded bg-surface',
        className ?? '',
      ].join(' ')}
    >
      {dark && (
        <div className="bg-secondary-container/20 pointer-events-none absolute -top-10 -right-10 size-40 rounded-full blur-2xl" />
      )}
      <span
        className={[
          'flex size-11 items-center justify-center rounded-xl',
          dark ? 'bg-secondary/20 text-secondary-container' : 'bg-secondary/10 text-secondary',
        ].join(' ')}
      >
        <Icon className="size-6" />
      </span>
      <h3
        className={[
          'font-display text-title-lg font-bold',
          dark ? 'text-white' : 'text-primary',
        ].join(' ')}
      >
        {title}
      </h3>
      <p
        className={[
          'font-body text-body-sm',
          dark ? 'text-white/70' : 'text-on-surface-variant',
        ].join(' ')}
      >
        {body}
      </p>
    </div>
  )
}

export default function LandingPage() {
  return (
    <div className="min-h-screen overflow-x-hidden">
      <MarketingNav />

      {/* ── Hero: asymmetric split ─────────────────────────────────────────── */}
      <section className="px-container-padding relative mx-auto max-w-7xl pt-28 pb-16 md:pt-40">
        <div className="from-secondary-fixed/20 absolute inset-0 -z-10 rounded-3xl bg-gradient-to-br to-transparent opacity-50 blur-3xl" />
        <div className="gap-gutter grid items-center md:grid-cols-12">
          <div className="space-y-6 md:col-span-6">
            <div className="glassmorphism inline-block rounded-full px-4 py-2">
              <span className="font-label text-label-caps text-secondary font-bold tracking-wider">
                AI HOSPITAL MANAGEMENT PLATFORM
              </span>
            </div>
            <h1 className="font-display text-gradient text-[2rem] leading-[1.1] font-extrabold tracking-tight sm:text-4xl md:text-headline-xl">
              Run your whole hospital on one intelligent platform.
            </h1>
            <p className="font-body text-body-md text-on-surface-variant max-w-lg">
              Patients, scheduling, billing, and clinical work in a single system, with an AI
              Copilot that reviews the record alongside your team.
            </p>
            <div className="flex flex-wrap gap-4 pt-2">
              <Link
                to="/contact"
                className="neo-extruded bg-primary text-on-primary text-body-md rounded-xl px-8 py-4 font-bold transition-transform duration-300 hover:-translate-y-0.5 active:translate-y-0"
              >
                Book a demo
              </Link>
              <a
                href="#modules"
                className="glassmorphism text-primary text-body-md hover:bg-secondary/10 flex items-center gap-2 rounded-xl px-8 py-4 font-bold transition-colors"
              >
                Explore the platform
                <ArrowRight className="size-5" />
              </a>
            </div>
          </div>

          {/* Asset: honest 3-step process diagram (not a fake screenshot) */}
          <div className="relative md:col-span-6">
            <div className="from-secondary-fixed to-primary-fixed absolute -inset-4 z-0 rounded-[2rem] bg-gradient-to-tr opacity-20 blur-2xl" />
            <div className="glassmorphism relative z-10 rounded-[2rem] p-8">
              <p className="font-label text-label-caps text-outline mb-6">
                HOW THE COPILOT ASSISTS
              </p>
              <ol className="space-y-2">
                {[
                  { icon: Users, title: 'Connect', body: 'Records, vitals, and results land in one live view.' },
                  { icon: Sparkles, title: 'Review', body: 'The AI reads the record and flags what needs attention.' },
                  { icon: ShieldCheck, title: 'Approve', body: 'Your clinician confirms every recommended step.' },
                ].map((step, i, arr) => (
                  <li key={step.title} className="relative flex gap-4 pb-6 last:pb-0">
                    {i < arr.length - 1 && (
                      <span className="bg-outline-variant/40 absolute top-12 left-[23px] h-[calc(100%-2.5rem)] w-px" />
                    )}
                    <span className="neo-extruded bg-secondary/10 text-secondary z-10 flex size-12 shrink-0 items-center justify-center rounded-full">
                      <step.icon className="size-6" />
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

      {/* ── Compliance band ────────────────────────────────────────────────── */}
      <section className="px-container-padding mx-auto max-w-7xl">
        <div className="neo-pressed bg-surface flex flex-wrap items-center justify-center gap-x-10 gap-y-4 rounded-2xl px-6 py-5">
          {COMPLIANCE.map(({ icon: Icon, label }) => (
            <div key={label} className="text-on-surface-variant flex items-center gap-2">
              <Icon className="text-secondary size-5" />
              <span className="font-label text-label-caps">{label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ── Modules: bento (1 wide dark feature + 4 tiles) ─────────────────── */}
      <section id="modules" className="px-container-padding mx-auto mt-24 max-w-7xl scroll-mt-28">
        <div className="mb-10 max-w-2xl">
          <h2 className="font-display text-headline-lg text-primary">
            Every hospital function, in one place.
          </h2>
          <p className="font-body text-body-md text-on-surface-variant mt-3">
            Each department works in its own module and shares the same patient record, so nothing is
            re-entered and nothing is lost between teams.
          </p>
        </div>

        {/* 3x3: tall AI feature (col 1) + 2x2 modules (cols 2-3) + full-width Reports footer */}
        <div className="grid gap-5 md:grid-cols-3">
          <ModuleCard
            dark
            icon={Sparkles}
            title="AI Copilot"
            body="A context-aware assistant that reads the record, drafts summaries, and flags risks for clinician review across every module."
            className="md:row-span-2"
          />
          <ModuleCard
            icon={Users}
            title="Patients"
            body="A searchable registry with full history, admissions, and documents per patient."
          />
          <ModuleCard
            icon={CalendarDays}
            title="Appointments"
            body="Doctor availability, booking, and the daily queue in one calendar."
          />
          <ModuleCard
            icon={Receipt}
            title="Billing"
            body="Invoices, payments, and refunds tied to each visit."
          />
          <ModuleCard
            icon={Pill}
            title="Pharmacy & Lab"
            body="Prescriptions and lab orders tracked from request to result."
          />
          <ModuleCard
            icon={BarChart3}
            title="Reports & Analytics"
            body="Revenue, occupancy, and clinical activity in live dashboards across the hospital."
            className="md:col-span-3"
          />
        </div>
      </section>

      {/* ── Workflow: horizontal clinical journey ──────────────────────────── */}
      <section className="px-container-padding mx-auto mt-24 max-w-7xl">
        <div className="mb-10 max-w-2xl">
          <h2 className="font-display text-headline-lg text-primary">
            One patient journey, start to finish.
          </h2>
        </div>
        <ol className="relative grid gap-8 md:grid-cols-5">
          <span
            aria-hidden
            className="bg-outline-variant/40 absolute top-6 right-6 left-6 hidden h-px md:block"
          />
          {WORKFLOW.map((step, i) => (
            <li key={step.title} className="relative flex flex-col gap-3">
              <span className="neo-extruded bg-surface text-secondary z-10 flex size-12 items-center justify-center rounded-full">
                <step.icon className="size-6" />
              </span>
              <div>
                <p className="font-label text-label-caps text-outline">
                  {String(i + 1).padStart(2, '0')}
                </p>
                <h3 className="font-display text-title-lg text-primary font-bold">{step.title}</h3>
                <p className="font-body text-body-sm text-on-surface-variant mt-1">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {/* ── Outcomes: divider layout ───────────────────────────────────────── */}
      <section className="px-container-padding mx-auto mt-24 max-w-7xl">
        <div className="grid gap-8 md:grid-cols-3">
          {OUTCOMES.map((o) => (
            <div key={o.title} className="border-outline-variant/40 border-t pt-6">
              <h3 className="font-display text-title-lg text-primary font-bold">{o.title}</h3>
              <p className="font-body text-body-sm text-on-surface-variant mt-2">{o.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── FAQ: accordion ─────────────────────────────────────────────────── */}
      <section className="px-container-padding mx-auto mt-24 max-w-3xl">
        <h2 className="font-display text-headline-lg text-primary mb-10 text-center">
          Questions hospitals ask us
        </h2>
        <Accordion type="single" collapsible className="flex flex-col gap-4">
          {FAQ.map((item, i) => (
            <AccordionItem key={item.q} value={`faq-${i}`}>
              <AccordionTrigger>{item.q}</AccordionTrigger>
              <AccordionContent>{item.a}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </section>

      {/* ── Final CTA ──────────────────────────────────────────────────────── */}
      <section className="px-container-padding mx-auto mt-24 max-w-7xl">
        <div className="glassmorphism relative overflow-hidden rounded-3xl px-8 py-16 text-center">
          <div className="from-secondary-fixed/30 absolute inset-0 -z-10 bg-gradient-to-br to-transparent blur-3xl" />
          <h2 className="font-display text-headline-lg text-gradient mx-auto max-w-2xl">
            See Aetheris run your hospital.
          </h2>
          <p className="font-body text-body-md text-on-surface-variant mx-auto mt-3 max-w-md">
            Walk through the platform with our team and map it to your departments.
          </p>
          <div className="mt-8 flex justify-center">
            <Link
              to="/contact"
              className="neo-extruded bg-primary text-on-primary text-body-md inline-flex items-center gap-2 rounded-xl px-8 py-4 font-bold transition-transform duration-300 hover:-translate-y-0.5 active:translate-y-0"
            >
              Book a demo
              <ArrowRight className="size-5" />
            </Link>
          </div>
        </div>
      </section>

      <MarketingFooter />
    </div>
  )
}
