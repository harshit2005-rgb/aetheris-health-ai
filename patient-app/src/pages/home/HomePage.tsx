import { Building2, LogOut, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Alert, Button, EmptyState, Skeleton } from '@atheris/ui'
import { useSignOut } from '@/api/auth'
import { useMe, type HospitalLink } from '@/api/me'
import { formatDay } from '@/lib/format'
import { usePageTitle } from '@/lib/usePageTitle'
import { homeStrings as S } from '@/pages/home/strings'

/** Home: who is signed in and which hospital records are linked. */
export function HomePage() {
  usePageTitle(S.title)
  const me = useMe()
  const signOut = useSignOut()

  return (
    <div className="space-y-8">
      <section aria-labelledby="home-heading" className="space-y-1">
        <h1 id="home-heading" className="font-display text-headline-md text-primary">
          {S.heading}
        </h1>
        {me.data && (
          <p className="text-body-lg text-on-surface-variant">
            {S.signedInAs} <span className="text-on-surface font-semibold">{me.data.account.phone_masked}</span>
          </p>
        )}
      </section>

      <section aria-labelledby="hospitals-heading" className="space-y-4">
        <h2 id="hospitals-heading" className="font-display text-title-lg text-primary">
          {S.hospitalsHeading}
        </h2>

        {me.isPending ? (
          <div role="status" aria-label={S.loading} className="space-y-3">
            <Skeleton className="h-20 w-full rounded-2xl" />
            <Skeleton className="h-20 w-full rounded-2xl" />
          </div>
        ) : me.isError ? (
          <div className="space-y-3">
            <Alert variant="error">{S.loadFailed}</Alert>
            <Button variant="outline" size="touch" onClick={() => void me.refetch()} disabled={me.isFetching}>
              {S.retry}
            </Button>
          </div>
        ) : me.data.links.length === 0 ? (
          <EmptyState
            icon={Building2}
            title={S.emptyTitle}
            description={S.emptyBody}
            className="bg-card border py-10"
            action={
              <Button asChild size="touch">
                <Link to="/link-patient">{S.linkFirst}</Link>
              </Button>
            }
          />
        ) : (
          <>
            <ul aria-labelledby="hospitals-heading" className="space-y-3">
              {me.data.links.map((link) => (
                <HospitalCard key={link.hospital_id} link={link} />
              ))}
            </ul>
            <Button asChild variant="outline" size="touch" className="w-full">
              <Link to="/link-patient">
                <Plus aria-hidden />
                {S.linkAnother}
              </Link>
            </Button>
          </>
        )}
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

function HospitalCard({ link }: { link: HospitalLink }) {
  return (
    <li className="bg-card rounded-2xl border p-4">
      <div className="flex items-start gap-3">
        <span className="bg-secondary-fixed/50 text-secondary flex size-11 shrink-0 items-center justify-center rounded-xl">
          <Building2 className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-body-lg text-on-surface font-semibold break-words">{link.hospital_name}</p>
          <p className="text-body-sm text-on-surface-variant">{S.linkedOn(formatDay(link.linked_at))}</p>
        </div>
        <span
          className={
            link.suspended
              ? 'bg-error-container text-on-error-container text-body-sm rounded-full px-2.5 py-0.5 font-medium'
              : 'bg-secondary-fixed/60 text-on-secondary-container text-body-sm rounded-full px-2.5 py-0.5 font-medium'
          }
        >
          {link.suspended ? S.paused : S.active}
        </span>
      </div>
      {link.suspended && <p className="text-body-sm text-on-surface-variant mt-3">{S.pausedHelp}</p>}
    </li>
  )
}
