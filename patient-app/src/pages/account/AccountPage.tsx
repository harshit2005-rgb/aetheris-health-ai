import { Building2, LogOut, Smartphone } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Alert, Button, Skeleton } from '@atheris/ui'
import { useSignOut } from '@/api/auth'
import { useMe } from '@/api/me'
import { PageHeading } from '@/components/PageHeading'
import { usePageTitle } from '@/lib/usePageTitle'
import { accountStrings as S } from '@/pages/account/strings'

/** The patient's account: the number they sign in with, the way to link a hospital record, and signing out. */
export function AccountPage() {
  usePageTitle(S.title)
  const me = useMe()
  const signOut = useSignOut()

  return (
    <div className="space-y-8">
      <PageHeading>{S.heading}</PageHeading>

      <section aria-labelledby="number-heading" className="bg-card space-y-3 rounded-2xl border p-5">
        <div className="flex items-start gap-3">
          <Smartphone className="text-secondary mt-0.5 size-5 shrink-0" aria-hidden />
          <div className="min-w-0 flex-1 space-y-1">
            <h2 id="number-heading" className="font-display text-title-lg text-primary">
              {S.numberHeading}
            </h2>
            {me.isPending ? (
              <div role="status" aria-label={S.loading}>
                <Skeleton className="h-7 w-40" />
              </div>
            ) : me.isError ? (
              <div className="space-y-3 pt-1">
                <Alert variant="error">{S.loadFailed}</Alert>
                <Button variant="outline" size="touch" onClick={() => void me.refetch()} disabled={me.isFetching}>
                  {S.retry}
                </Button>
              </div>
            ) : (
              <p className="text-body-lg text-on-surface font-semibold tabular-nums">{me.data.account.phone_masked}</p>
            )}
            <p className="text-body-sm text-on-surface-variant">{S.numberBody}</p>
          </div>
        </div>
      </section>

      <section aria-labelledby="records-heading" className="bg-card space-y-3 rounded-2xl border p-5">
        <div className="flex items-start gap-3">
          <Building2 className="text-secondary mt-0.5 size-5 shrink-0" aria-hidden />
          <div className="min-w-0 flex-1 space-y-1">
            <h2 id="records-heading" className="font-display text-title-lg text-primary">
              {S.recordsHeading}
            </h2>
            <p className="text-body-sm text-on-surface-variant">{S.recordsBody}</p>
          </div>
        </div>
        <Button asChild variant="outline" size="touch" className="w-full">
          <Link to="/link-patient">{S.linkCta}</Link>
        </Button>
      </section>

      <section className="space-y-3 border-t pt-6">
        {signOut.isError && <Alert variant="error">{S.signOutFailed}</Alert>}
        <Button
          variant="ghost"
          size="touch"
          className="text-on-surface-variant w-full"
          onClick={() => signOut.mutate()}
          disabled={signOut.isPending}
        >
          <LogOut aria-hidden />
          {signOut.isPending ? S.signingOut : S.signOut}
        </Button>
      </section>
    </div>
  )
}
