import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { ArrowLeft, CheckCircle, Eye, EyeOff, KeyRound, Loader2 } from 'lucide-react'
import { Logo } from '@/components/brand/Logo'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

const resetSchema = z
  .object({
    password: z
      .string()
      .min(12, 'Password must be at least 12 characters')
      .max(128, 'Password must be at most 128 characters'),
    confirmPassword: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  })

type ResetValues = z.infer<typeof resetSchema>

/**
 * Reset Password page (task 5).
 *
 * Receives the reset token from the URL query string (?token=...).
 * Validates the new password (min 12 chars per backend schema),
 * submits to POST /auth/password/reset, and shows a success state.
 */
export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [success, setSuccess] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetValues>({
    resolver: zodResolver(resetSchema),
    defaultValues: { password: '', confirmPassword: '' },
  })

  // No token in URL — invalid reset link.
  if (!token) {
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

          <div className="flex flex-col items-center text-center">
            <h1 className="font-display text-headline-lg text-primary mb-2">Invalid reset link</h1>
            <p className="font-body text-body-sm text-on-surface-variant mb-8 max-w-xs">
              This password reset link is invalid or has expired. Please request a new one.
            </p>
            <Link
              to="/forgot-password"
              className="font-body text-body-sm text-secondary hover:underline flex items-center gap-1"
            >
              <ArrowLeft className="size-4" />
              Request a new link
            </Link>
          </div>
        </div>
      </div>
    )
  }

  // Success state
  if (success) {
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

          <div className="flex flex-col items-center text-center">
            <div className="bg-success/10 mb-4 flex size-16 items-center justify-center rounded-full">
              <CheckCircle className="text-success size-8" />
            </div>
            <h1 className="font-display text-headline-lg text-primary mb-2">Password reset!</h1>
            <p className="font-body text-body-sm text-on-surface-variant mb-8 max-w-xs">
              Your password has been changed. You can now sign in with your new password.
            </p>
            <Link
              to="/login"
              className="shadow-neo-base bg-primary text-on-primary font-label text-label-caps flex items-center gap-2 rounded-xl px-6 py-3 font-bold transition-all duration-300 hover:-translate-y-0.5 active:translate-y-0"
            >
              Sign in
            </Link>
          </div>
        </div>
      </div>
    )
  }

  // Form state
  async function onSubmit(values: ResetValues) {
    try {
      await api.post('/auth/password/reset', {
        token,
        new_password: values.password,
      })
      setSuccess(true)
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Reset link may be invalid or expired.';
      toast.error(msg);
    }
  }

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
          <div className="bg-secondary/10 mx-auto mb-4 flex size-14 items-center justify-center rounded-full">
            <KeyRound className="text-secondary size-7" />
          </div>
          <h1 className="font-display text-headline-lg text-primary">Reset your password</h1>
          <p className="font-body text-body-sm text-on-surface-variant mt-2">
            Enter your new password below.
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
          {/* New password */}
          <div className="space-y-2">
            <label htmlFor="password" className="font-label text-label-caps text-on-surface-variant">
              New password
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                placeholder="••••••••••••"
                aria-invalid={!!errors.password}
                className={cn(
                  'neo-pressed bg-surface font-body text-body-sm text-on-surface placeholder:text-outline-variant w-full rounded-xl px-4 py-3 pr-11 outline-none focus:ring-2',
                  errors.password ? 'focus:ring-error' : 'focus:ring-secondary',
                )}
                {...register('password')}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                className="text-outline hover:text-secondary absolute top-1/2 right-3 -translate-y-1/2 transition-colors"
              >
                {showPassword ? <EyeOff className="size-5" /> : <Eye className="size-5" />}
              </button>
            </div>
            {errors.password && (
              <p className="font-body text-error text-xs">{errors.password.message}</p>
            )}
          </div>

          {/* Confirm password */}
          <div className="space-y-2">
            <label htmlFor="confirmPassword" className="font-label text-label-caps text-on-surface-variant">
              Confirm password
            </label>
            <div className="relative">
              <input
                id="confirmPassword"
                type={showConfirm ? 'text' : 'password'}
                autoComplete="new-password"
                placeholder="••••••••••••"
                aria-invalid={!!errors.confirmPassword}
                className={cn(
                  'neo-pressed bg-surface font-body text-body-sm text-on-surface placeholder:text-outline-variant w-full rounded-xl px-4 py-3 pr-11 outline-none focus:ring-2',
                  errors.confirmPassword ? 'focus:ring-error' : 'focus:ring-secondary',
                )}
                {...register('confirmPassword')}
              />
              <button
                type="button"
                onClick={() => setShowConfirm((v) => !v)}
                aria-label={showConfirm ? 'Hide password' : 'Show password'}
                className="text-outline hover:text-secondary absolute top-1/2 right-3 -translate-y-1/2 transition-colors"
              >
                {showConfirm ? <EyeOff className="size-5" /> : <Eye className="size-5" />}
              </button>
            </div>
            {errors.confirmPassword && (
              <p className="font-body text-error text-xs">{errors.confirmPassword.message}</p>
            )}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="shadow-neo-base bg-primary text-on-primary font-label text-label-caps flex w-full items-center justify-center gap-2 rounded-xl py-3.5 font-bold transition-all duration-300 hover:-translate-y-0.5 active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="size-5 animate-spin" />
                Resetting…
              </>
            ) : (
              'Reset password'
            )}
          </button>
        </form>

        <p className="font-body text-body-sm text-on-surface-variant mt-8 text-center">
          <Link to="/login" className="text-secondary font-bold hover:underline flex items-center justify-center gap-1">
            <ArrowLeft className="size-4" />
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
