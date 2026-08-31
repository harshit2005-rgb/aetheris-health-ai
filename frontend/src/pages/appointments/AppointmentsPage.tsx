import { useState } from 'react'
import { CalendarClock, RotateCw } from 'lucide-react'
import PageHeader from '@/components/layout/PageHeader'
import { DataTable } from '@/components/ui/data-table'
import { EmptyState } from '@/components/ui/empty-state'
import { Button } from '@/components/ui/button'
import { Alert } from '@/components/ui/alert'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useAppointments, type AppointmentStatus } from '@/api/appointments'
import { appointmentColumns } from './columns'

const PAGE_SIZE = 25
const ALL = 'all'

const STATUS_OPTIONS: { value: AppointmentStatus; label: string }[] = [
  { value: 'booked', label: 'Booked' },
  { value: 'checked_in', label: 'Checked in' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'no_show', label: 'No show' },
]

function todayLocal(): string {
  const d = new Date()
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}

export default function AppointmentsPage() {
  const [date, setDate] = useState<string>(todayLocal)
  const [status, setStatus] = useState<string>(ALL)
  const [page, setPage] = useState(1)

  const { data, isPending, isError, isFetching, refetch } = useAppointments({
    appointment_date: date,
    appointment_status: status === ALL ? undefined : (status as AppointmentStatus),
    page,
    page_size: PAGE_SIZE,
  })

  const appointments = data?.items ?? []
  const meta = data?.pagination
  const isToday = date === todayLocal()

  return (
    <div className="w-full">
      <PageHeader
        title="Appointments"
        subtitle="The day's queue — check-ins, consultations and their status."
        actions={
          <>
            <input
              type="date"
              value={date}
              onChange={(e) => {
                setDate(e.target.value || todayLocal())
                setPage(1)
              }}
              aria-label="Appointment date"
              className="neo-pressed bg-surface font-body text-body-sm text-on-surface focus-visible:ring-secondary rounded-full px-4 py-2.5 outline-none focus-visible:ring-2"
            />
            {!isToday && (
              <Button
                variant="outline"
                className="rounded-full"
                onClick={() => {
                  setDate(todayLocal())
                  setPage(1)
                }}
              >
                Today
              </Button>
            )}
            <Select
              value={status}
              onValueChange={(v) => {
                setStatus(v)
                setPage(1)
              }}
            >
              <SelectTrigger aria-label="Filter by status" className="w-40 rounded-full py-2.5">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All statuses</SelectItem>
                {STATUS_OPTIONS.map((s) => (
                  <SelectItem key={s.value} value={s.value}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        }
      />

      {isError ? (
        <Alert variant="error" title="Couldn't load appointments">
          <div className="flex flex-col items-start gap-3">
            <p>The appointment queue could not be reached. Check your connection and try again.</p>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RotateCw className="size-4" /> Retry
            </Button>
          </div>
        </Alert>
      ) : (
        <DataTable
          columns={appointmentColumns}
          data={appointments}
          isLoading={isPending}
          enableSorting={false}
          manualPagination
          emptyState={
            <EmptyState
              icon={CalendarClock}
              title={isToday ? 'No appointments today' : 'No appointments'}
              description={
                status === ALL
                  ? 'Nothing is scheduled for this day yet.'
                  : 'No appointments match this status for the selected day.'
              }
            />
          }
          footer={
            meta && meta.total > 0 ? (
              <div className="flex items-center justify-between gap-4">
                <p className="font-body text-body-sm text-on-surface-variant">
                  Page {meta.page} of {meta.totalPages} · {meta.total} appointment
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
