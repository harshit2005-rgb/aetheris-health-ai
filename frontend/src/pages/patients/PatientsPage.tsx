import { useEffect, useState } from 'react'
import { RotateCw, Search, UserPlus, Users } from 'lucide-react'
import PageHeader from '@/components/layout/PageHeader'
import { DataTable } from '@/components/ui/data-table'
import { EmptyState } from '@/components/ui/empty-state'
import { Button } from '@/components/ui/button'
import { Alert } from '@/components/ui/alert'
import { usePatients } from '@/api/patients'
import { patientColumns } from './columns'
import { RegisterPatientDialog } from './RegisterPatientDialog'

const PAGE_SIZE = 25

export default function PatientsPage() {
  const [searchInput, setSearchInput] = useState('')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)

  // Debounce the free-text term into the query param, and reset to page 1 on change.
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(searchInput.trim())
      setPage(1)
    }, 300)
    return () => clearTimeout(t)
  }, [searchInput])

  // `isPending` (not `isLoading`) stays true across retry backoff until the
  // query first succeeds or terminally errors — so the empty state never flashes
  // in the gap between retries.
  const { data, isPending, isError, isFetching, refetch } = usePatients({
    q: q || undefined,
    page,
    page_size: PAGE_SIZE,
  })

  const patients = data?.items ?? []
  const meta = data?.pagination

  const registerButton = (
    <Button className="rounded-full">
      <UserPlus className="size-4" /> Register Patient
    </Button>
  )

  return (
    <div className="w-full">
      <PageHeader
        title="Patients"
        subtitle="Patient registry, admissions and AI-assisted summaries."
        actions={
          <>
            <div className="relative">
              <Search className="text-outline pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
              <input
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search name, MRN, phone…"
                aria-label="Search patients"
                className="neo-pressed bg-surface font-body text-body-sm text-on-surface placeholder:text-outline-variant focus-visible:ring-secondary w-full rounded-full py-2.5 pr-4 pl-9 outline-none focus-visible:ring-2 sm:w-64"
              />
            </div>
            <RegisterPatientDialog trigger={registerButton} />
          </>
        }
      />

      {isError ? (
        <Alert variant="error" title="Couldn't load patients">
          <div className="flex flex-col items-start gap-3">
            <p>The patient registry could not be reached. Check your connection and try again.</p>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RotateCw className="size-4" /> Retry
            </Button>
          </div>
        </Alert>
      ) : (
        <DataTable
          columns={patientColumns}
          data={patients}
          isLoading={isPending}
          enableSorting={false}
          manualPagination
          emptyState={
            q ? (
              <EmptyState
                icon={Search}
                title="No matches"
                description={`No patients match "${q}". Try a different name, MRN, or phone number.`}
              />
            ) : (
              <EmptyState
                icon={Users}
                title="No patients yet"
                description="Register your first patient to start building the registry."
                action={<RegisterPatientDialog trigger={registerButton} />}
              />
            )
          }
          footer={
            meta && meta.total > 0 ? (
              <div className="flex items-center justify-between gap-4">
                <p className="font-body text-body-sm text-on-surface-variant">
                  Page {meta.page} of {meta.totalPages} · {meta.total} patient
                  {meta.total === 1 ? '' : 's'}
                  {isFetching && <span className="text-outline"> · updating…</span>}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={meta.page <= 1 || isFetching}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={meta.page >= meta.totalPages || isFetching}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            ) : null
          }
        />
      )}
    </div>
  )
}
