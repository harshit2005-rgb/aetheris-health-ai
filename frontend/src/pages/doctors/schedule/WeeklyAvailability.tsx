import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { CalendarClock, Copy, Loader2, Pencil, Plus, RotateCw, Trash2 } from 'lucide-react'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  SLOT_DURATIONS,
  useDoctorAvailability,
  useSetAvailability,
  type AvailabilityWindow,
} from '@/api/doctors'
import { ApiError } from '@/api/types'
import { apiErrorMessage } from '@/lib/apiErrors'
import {
  DAY_NAMES,
  copyDay,
  entriesFromWeek,
  newWindow,
  slotCount,
  weekErrors,
  weekFromWindows,
  type DraftWeek,
  type DraftWindow,
} from './scheduleModel'

const SAVE_FAILED = "Couldn't save the schedule. Try again."
const WEEKDAYS = [1, 2, 3, 4]

function saveErrorMessage(err: unknown): string {
  if (err instanceof ApiError && err.status === 403) return "You can change only your own schedule."
  return apiErrorMessage(err, SAVE_FAILED)
}

/**
 * A doctor's weekly hours (module spec §5.2, §12): read by anyone who may see
 * availability, edited by someone who may change this doctor's schedule.
 *
 * The editor is a form, one row per window, rather than a drag grid (decided
 * 2026-10-16): exact times, keyboard and phone friendly. Saving sends the whole
 * week, which is how the API works: days left empty have no hours.
 */
export function WeeklyAvailability({ doctorId, canEdit }: { doctorId: string; canEdit: boolean }) {
  const { data: windows, isPending, isError, refetch } = useDoctorAvailability(doctorId)
  const save = useSetAvailability(doctorId)
  const [draft, setDraft] = useState<DraftWeek | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [showErrors, setShowErrors] = useState(false)
  const busy = useRef(false)

  const editing = draft !== null
  const errors = draft ? weekErrors(draft) : {}

  function startEditing() {
    setDraft(weekFromWindows(windows ?? []))
    setNotice(null)
    setShowErrors(false)
  }

  function update(day: number, key: string, change: Partial<DraftWindow>) {
    setDraft((week) => week && week.map((d, i) => (i === day ? d.map((w) => (w.key === key ? { ...w, ...change } : w)) : d)))
  }

  async function submit() {
    if (!draft || busy.current) return
    if (Object.keys(errors).length > 0) {
      setShowErrors(true)
      return
    }
    busy.current = true
    setNotice(null)
    try {
      await save.mutateAsync(entriesFromWeek(draft))
      toast.success('Schedule saved')
      setDraft(null)
    } catch (err) {
      setNotice(saveErrorMessage(err))
    } finally {
      busy.current = false
    }
  }

  return (
    <section aria-labelledby="hours-heading" className="neo-extruded bg-surface space-y-4 rounded-2xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="hours-heading" className="font-display text-title-lg text-primary flex items-center gap-2 font-bold">
          <CalendarClock className="size-5" aria-hidden /> Weekly hours
        </h2>
        {canEdit && !editing && windows && (
          <Button variant="outline" size="sm" onClick={startEditing}>
            <Pencil className="size-4" aria-hidden /> Edit hours
          </Button>
        )}
      </div>

      {isPending ? (
        <Skeleton className="h-40 w-full rounded-xl" aria-label="Loading weekly hours" />
      ) : isError ? (
        <Alert variant="error" title="Couldn't load the weekly hours">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RotateCw className="size-4" aria-hidden /> Retry
          </Button>
        </Alert>
      ) : editing ? (
        <form
          className="space-y-4"
          aria-label="Edit weekly hours"
          onSubmit={(e) => {
            e.preventDefault()
            void submit()
          }}
        >
          <p className="font-body text-body-sm text-on-surface-variant">
            Times are the hospital&apos;s local time. A day with no hours can&apos;t be booked.
          </p>
          {notice && <Alert variant="error">{notice}</Alert>}
          {draft.map((day, dayIndex) => (
            <fieldset key={DAY_NAMES[dayIndex]} className="border-outline-variant/40 space-y-2 border-t pt-3">
              <legend className="font-body text-body-md text-on-surface float-left pt-1 font-semibold">
                {DAY_NAMES[dayIndex]}
              </legend>
              <div className="flex flex-wrap items-center justify-end gap-2">
                <div className="flex flex-wrap gap-2">
                  {dayIndex === 0 && day.length > 0 && (
                    <Button type="button" variant="ghost" size="sm" onClick={() => setDraft(copyDay(draft, 0, WEEKDAYS))}>
                      <Copy className="size-4" aria-hidden /> Copy Monday to Tuesday–Friday
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setDraft(draft.map((d, i) => (i === dayIndex ? [...d, newWindow(d)] : d)))}
                    aria-label={`Add hours on ${DAY_NAMES[dayIndex]}`}
                  >
                    <Plus className="size-4" aria-hidden /> Add hours
                  </Button>
                </div>
              </div>
              {day.length === 0 && <p className="font-body text-body-sm text-on-surface-variant clear-both">No hours</p>}
              {day.map((w, index) => {
                const label = `${DAY_NAMES[dayIndex]}, hours ${index + 1}`
                const error = showErrors ? errors[w.key] : undefined
                return (
                  <div key={w.key} role="group" aria-label={label} className="clear-both space-y-1">
                    <div className="flex flex-wrap items-end gap-2">
                      <label className="font-body text-body-sm text-on-surface-variant flex flex-col gap-1">
                        From
                        <Input
                          type="time"
                          value={w.start}
                          aria-invalid={!!error}
                          onChange={(e) => update(dayIndex, w.key, { start: e.target.value })}
                          className="w-32"
                        />
                      </label>
                      <label className="font-body text-body-sm text-on-surface-variant flex flex-col gap-1">
                        To
                        <Input
                          type="time"
                          value={w.end}
                          aria-invalid={!!error}
                          onChange={(e) => update(dayIndex, w.key, { end: e.target.value })}
                          className="w-32"
                        />
                      </label>
                      <div className="font-body text-body-sm text-on-surface-variant flex flex-col gap-1">
                        <span id={`${w.key}-len`}>Slot length</span>
                        <Select
                          value={String(w.duration)}
                          onValueChange={(v) => update(dayIndex, w.key, { duration: Number(v) })}
                        >
                          <SelectTrigger className="w-32" aria-labelledby={`${w.key}-len`}>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {SLOT_DURATIONS.map((m) => (
                              <SelectItem key={m} value={String(m)}>
                                {m} min
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="text-error"
                        aria-label={`Remove ${label}`}
                        onClick={() => setDraft(draft.map((d, i) => (i === dayIndex ? d.filter((x) => x.key !== w.key) : d)))}
                      >
                        <Trash2 className="size-4" aria-hidden />
                      </Button>
                      {!errors[w.key] && (
                        <span className="font-body text-body-sm text-on-surface-variant pb-2">
                          {slotCount(w)} slots
                        </span>
                      )}
                    </div>
                    {error && (
                      <p role="alert" className="font-body text-body-sm text-error">
                        {error}
                      </p>
                    )}
                  </div>
                )
              })}
            </fieldset>
          ))}
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setDraft(null)} disabled={save.isPending}>
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending} aria-busy={save.isPending}>
              {save.isPending && <Loader2 className="size-4 animate-spin" aria-hidden />}
              {save.isPending ? 'Saving…' : 'Save hours'}
            </Button>
          </div>
        </form>
      ) : (
        <WeekSummary windows={windows} />
      )}
    </section>
  )
}

function WeekSummary({ windows }: { windows: AvailabilityWindow[] }) {
  const week = weekFromWindows(windows)
  if (week.every((day) => day.length === 0)) {
    return <p className="font-body text-body-md text-on-surface-variant">No weekly hours set, so this doctor can&apos;t be booked.</p>
  }
  return (
    <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-[10rem_1fr]">
      {week.map((day, index) => (
        <div key={DAY_NAMES[index]} className="contents">
          <dt className="font-body text-body-md text-on-surface font-semibold">{DAY_NAMES[index]}</dt>
          <dd className="font-body text-body-md text-on-surface-variant">
            {day.length === 0
              ? 'Off'
              : day.map((w) => `${w.start}–${w.end} (${w.duration}-min slots)`).join(', ')}
          </dd>
        </div>
      ))}
    </dl>
  )
}
