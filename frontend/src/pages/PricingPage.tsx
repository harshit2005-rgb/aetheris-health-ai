import { Link } from 'react-router-dom'
import { CheckCircle2 } from 'lucide-react'
import MarketingNav from '@/components/layout/MarketingNav'
import MarketingFooter from '@/components/layout/MarketingFooter'
import { cn } from '@/lib/utils'

interface Plan {
  name: string
  blurb: string
  price: string
  period?: string
  features: string[]
  cta: string
  to: string
  featured?: boolean
}

const PLANS: Plan[] = [
  {
    name: 'Starter',
    blurb: 'Essential AI tools for small clinics.',
    price: '$299',
    period: '/mo',
    features: ['Standard API access', 'Basic analytics', 'Community support', 'Up to 3 clinicians'],
    cta: 'Get Started',
    to: '/login',
  },
  {
    name: 'Professional',
    blurb: 'Advanced integration for growing hospitals.',
    price: '$899',
    period: '/mo',
    features: [
      'FastAPI backend integration',
      'Agentic AI orchestration',
      'Priority support',
      'Real-time vitals monitoring',
    ],
    cta: 'Upgrade to Pro',
    to: '/login',
    featured: true,
  },
  {
    name: 'Enterprise',
    blurb: 'Full-scale deployment with dedicated support.',
    price: 'Custom',
    features: [
      'On-premise or private cloud',
      'Custom AI agent training',
      'Dedicated success engineer',
      'HIPAA & SOC 2 compliance',
    ],
    cta: 'Contact Sales',
    to: '/contact',
  },
]

function PlanCard({ plan }: { plan: Plan }) {
  return (
    <div
      className={cn(
        'flex flex-col rounded-3xl p-8 transition-transform duration-300 hover:-translate-y-1.5',
        plan.featured
          ? 'glassmorphism shadow-glass-panel ring-secondary/40 relative ring-1'
          : 'neo-extruded bg-surface',
      )}
    >
      {plan.featured && (
        <span className="bg-secondary text-on-secondary font-label text-label-caps absolute -top-3 left-8 rounded-full px-3 py-1 font-bold">
          Most Popular
        </span>
      )}
      <h3 className="font-display text-headline-md text-primary mb-2 font-bold">{plan.name}</h3>
      <p className="font-body text-body-sm text-on-surface-variant mb-6">{plan.blurb}</p>
      <div className="text-primary mb-8 text-4xl font-extrabold">
        {plan.price}
        {plan.period && (
          <span className="font-body text-body-sm text-on-surface-variant font-normal">
            {plan.period}
          </span>
        )}
      </div>
      <ul className="mb-8 flex-1 space-y-4">
        {plan.features.map((f) => (
          <li key={f} className="flex items-center gap-3">
            <CheckCircle2 className="text-secondary size-5 shrink-0" />
            <span className="font-body text-body-md text-on-surface">{f}</span>
          </li>
        ))}
      </ul>
      <Link
        to={plan.to}
        className={cn(
          'w-full rounded-full py-3 text-center font-bold transition-all active:scale-[0.98]',
          plan.featured
            ? 'bg-primary text-on-primary shadow-neo-base'
            : 'neo-extruded text-primary hover:text-secondary',
        )}
      >
        {plan.cta}
      </Link>
    </div>
  )
}

export default function PricingPage() {
  return (
    <div className="relative min-h-screen overflow-x-hidden">
      {/* Floating decorative shapes */}
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="bg-primary-fixed-dim/30 absolute -top-[10%] -left-[5%] h-96 w-96 rounded-full blur-3xl" />
        <div className="bg-secondary-fixed/30 absolute right-[-10%] bottom-[10%] h-[500px] w-[500px] rounded-full blur-3xl" />
      </div>

      <MarketingNav />

      <main className="px-container-padding mx-auto max-w-7xl pt-28 pb-16 md:pt-36">
        <div className="mb-14 text-center">
          <h1 className="font-display text-headline-xl text-primary mb-3">Enterprise AI Plans</h1>
          <p className="font-body text-body-md text-on-surface-variant mx-auto max-w-2xl">
            Scalable healthcare intelligence tailored to your operational needs.
          </p>
        </div>

        <div className="grid grid-cols-1 items-stretch gap-6 md:grid-cols-3 lg:gap-8">
          {PLANS.map((plan) => (
            <PlanCard key={plan.name} plan={plan} />
          ))}
        </div>
      </main>

      <MarketingFooter />
    </div>
  )
}
