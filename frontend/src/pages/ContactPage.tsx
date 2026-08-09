import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Icon } from '@/components/ui/icon'
import MarketingNav from '@/components/layout/MarketingNav'
import MarketingFooter from '@/components/layout/MarketingFooter'
import { cn } from '@/lib/utils'

const contactSchema = z.object({
  name: z.string().min(2, 'Enter your name'),
  email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
  organization: z.string().min(2, 'Enter your organization'),
  message: z.string().min(10, 'Tell us a little more (at least 10 characters)'),
})

type ContactValues = z.infer<typeof contactSchema>

const CHANNELS = [
  { icon: 'mail', label: 'Sales', value: 'sales@aetheris.health' },
  { icon: 'support_agent', label: 'Support', value: 'support@aetheris.health' },
  { icon: 'shield_lock', label: 'Privacy & compliance', value: 'privacy@aetheris.health' },
]

export default function ContactPage() {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ContactValues>({
    resolver: zodResolver(contactSchema),
    defaultValues: { name: '', email: '', organization: '', message: '' },
  })

  async function onSubmit(_values: ContactValues) {
    // ── Backend seam ─────────────────────────────────────────────
    // TODO(backend): POST to a real endpoint / CRM, e.g.
    //   await api.post('/contact', _values)
    await new Promise((r) => setTimeout(r, 700))
    toast.success("Thanks — we'll be in touch shortly.")
    reset()
  }

  const fieldClass = (invalid: boolean) =>
    cn(
      'neo-pressed bg-surface font-body text-body-sm text-on-surface placeholder:text-outline-variant w-full rounded-xl px-4 py-3 outline-none focus:ring-2',
      invalid ? 'focus:ring-error' : 'focus:ring-secondary',
    )

  return (
    <div className="relative min-h-screen overflow-x-hidden">
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="bg-secondary-fixed/30 absolute -top-[10%] right-[-5%] h-96 w-96 rounded-full blur-3xl" />
        <div className="bg-primary-fixed-dim/30 absolute bottom-[10%] left-[-10%] h-[500px] w-[500px] rounded-full blur-3xl" />
      </div>

      <MarketingNav />

      <main className="px-container-padding mx-auto grid max-w-7xl gap-12 pt-28 pb-16 md:grid-cols-2 md:pt-36">
        {/* Left: intro + channels */}
        <div>
          <p className="font-label text-label-caps text-secondary mb-4 font-bold tracking-wider">
            CONTACT
          </p>
          <h1 className="font-display text-headline-xl text-primary">Talk to our team.</h1>
          <p className="font-body text-body-md text-on-surface-variant mt-4 max-w-md">
            Whether you are scoping a rollout or have a compliance question, we will route you to the
            right person.
          </p>

          <div className="mt-10 space-y-4">
            {CHANNELS.map((c) => (
              <div key={c.label} className="flex items-center gap-4">
                <span className="neo-extruded bg-secondary/10 text-secondary flex h-11 w-11 items-center justify-center rounded-xl">
                  <Icon name={c.icon} filled />
                </span>
                <div>
                  <p className="font-label text-label-caps text-outline">{c.label}</p>
                  <p className="font-body text-body-md text-primary font-bold">{c.value}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: form */}
        <div className="glassmorphism shadow-glass-panel rounded-3xl p-8">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
            <div className="space-y-2">
              <label htmlFor="name" className="font-label text-label-caps text-on-surface-variant">
                Name
              </label>
              <input
                id="name"
                autoComplete="name"
                placeholder="Dr. Alex Chen"
                aria-invalid={!!errors.name}
                className={fieldClass(!!errors.name)}
                {...register('name')}
              />
              {errors.name && <p className="font-body text-error text-xs">{errors.name.message}</p>}
            </div>

            <div className="space-y-2">
              <label htmlFor="email" className="font-label text-label-caps text-on-surface-variant">
                Work email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="clinician@hospital.org"
                aria-invalid={!!errors.email}
                className={fieldClass(!!errors.email)}
                {...register('email')}
              />
              {errors.email && (
                <p className="font-body text-error text-xs">{errors.email.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <label
                htmlFor="organization"
                className="font-label text-label-caps text-on-surface-variant"
              >
                Organization
              </label>
              <input
                id="organization"
                autoComplete="organization"
                placeholder="Mercy General Hospital"
                aria-invalid={!!errors.organization}
                className={fieldClass(!!errors.organization)}
                {...register('organization')}
              />
              {errors.organization && (
                <p className="font-body text-error text-xs">{errors.organization.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <label
                htmlFor="message"
                className="font-label text-label-caps text-on-surface-variant"
              >
                How can we help?
              </label>
              <textarea
                id="message"
                rows={4}
                placeholder="Tell us about your team and what you are looking to solve."
                aria-invalid={!!errors.message}
                className={cn(fieldClass(!!errors.message), 'resize-none')}
                {...register('message')}
              />
              {errors.message && (
                <p className="font-body text-error text-xs">{errors.message.message}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="shadow-neo-base bg-primary text-on-primary font-label text-label-caps flex w-full items-center justify-center gap-2 rounded-xl py-3.5 font-bold transition-all duration-300 hover:-translate-y-0.5 active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {isSubmitting ? (
                <>
                  <Icon name="progress_activity" className="animate-spin text-lg" />
                  Sending...
                </>
              ) : (
                'Send message'
              )}
            </button>
          </form>
        </div>
      </main>

      <MarketingFooter />
    </div>
  )
}
