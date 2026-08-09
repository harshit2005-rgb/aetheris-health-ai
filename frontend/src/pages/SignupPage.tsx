import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Icon } from '@/components/ui/icon'
import { Logo } from '@/components/brand/Logo'
import { useAuthStore } from '@/store/auth-store'
import { cn } from '@/lib/utils'

const signupSchema = z.object({
  name: z.string().min(2, 'Enter your full name'),
  email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
  organization: z.string().min(2, 'Enter your hospital or clinic'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
})

type SignupValues = z.infer<typeof signupSchema>

export default function SignupPage() {
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)
  const [showPassword, setShowPassword] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: { name: '', email: '', organization: '', password: '' },
  })

  async function onSubmit(values: SignupValues) {
    // ── Backend seam ─────────────────────────────────────────────
    // TODO(backend): replace with a real registration call, e.g.
    //   const { data } = await api.post('/auth/register', values)
    //   setAuth(data.user, data.token)
    await new Promise((r) => setTimeout(r, 700))
    setAuth(
      { id: 'demo-user', name: values.name, email: values.email, role: 'clinician' },
      'demo-token',
    )
    toast.success('Account created. Welcome to Aetheris.')
    navigate('/dashboard', { replace: true })
  }

  const fieldClass = (invalid: boolean) =>
    cn(
      'neo-pressed bg-surface font-body text-body-sm text-on-surface placeholder:text-outline-variant w-full rounded-xl px-4 py-3 outline-none focus:ring-2',
      invalid ? 'focus:ring-error' : 'focus:ring-secondary',
    )

  return (
    <div className="relative flex min-h-[100dvh] items-center justify-center overflow-hidden px-4 py-12">
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="bg-primary-fixed-dim/30 absolute -top-[10%] -left-[5%] h-96 w-96 rounded-full blur-3xl" />
        <div className="bg-secondary-fixed/30 absolute right-[-10%] bottom-[5%] h-[500px] w-[500px] rounded-full blur-3xl" />
      </div>

      <div className="glassmorphism shadow-glass-panel animate-in fade-in zoom-in-95 w-full max-w-md rounded-3xl p-8 duration-500 sm:p-10">
        <Link to="/" className="mb-8 flex justify-center">
          <Logo variant="mark" className="h-14" />
        </Link>

        <div className="mb-8 text-center">
          <h1 className="font-display text-headline-lg text-primary">Get started</h1>
          <p className="font-body text-body-sm text-on-surface-variant mt-2">
            Create your clinical workspace in a minute.
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
          <div className="space-y-2">
            <label htmlFor="name" className="font-label text-label-caps text-on-surface-variant">
              Full name
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
            {errors.email && <p className="font-body text-error text-xs">{errors.email.message}</p>}
          </div>

          <div className="space-y-2">
            <label
              htmlFor="organization"
              className="font-label text-label-caps text-on-surface-variant"
            >
              Hospital or clinic
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
            <label htmlFor="password" className="font-label text-label-caps text-on-surface-variant">
              Password
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                placeholder="At least 8 characters"
                aria-invalid={!!errors.password}
                className={cn(fieldClass(!!errors.password), 'pr-11')}
                {...register('password')}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                className="text-outline hover:text-secondary absolute top-1/2 right-3 -translate-y-1/2 transition-colors"
              >
                <Icon name={showPassword ? 'visibility_off' : 'visibility'} className="text-lg" />
              </button>
            </div>
            {errors.password && (
              <p className="font-body text-error text-xs">{errors.password.message}</p>
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
                Creating account...
              </>
            ) : (
              'Create account'
            )}
          </button>
        </form>

        <p className="font-body text-body-sm text-on-surface-variant mt-8 text-center">
          Already have an account?{' '}
          <Link to="/login" className="text-secondary font-bold hover:underline">
            Log in
          </Link>
        </p>
      </div>
    </div>
  )
}
