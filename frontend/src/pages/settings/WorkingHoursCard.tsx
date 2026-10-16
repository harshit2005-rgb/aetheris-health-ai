import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { Clock, Loader2, Pencil, RotateCw } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { useSetWorkingHours, useWorkingHours } from '@/api/hospitals'
import { usePermissions } from '@/hooks/usePermissions'
import { apiErrorMessage } from '@/lib/apiErrors'
import {
  DAY_NAMES,
  daysFromDraft,
  describeDay,
  draftErrors,
  draftFromDays,
  type DayMode,
  type DraftDay,
} from './workingHours'

const MODE_LABEL: Record<DayMode, string> = { open: 'Open', closed: 'Closed', all_day: 'Open 24 hours' }

/**
 * The hospital's opening hours (module 14 §12, Working Hours tab): seven days,
 * each open between two times, open 24 hours, or closed. Read by everyone with
 * the settings tab; edited with `settings.update`. Saving sends the whole week.
 */
export function WorkingHoursCard() {
  const { can } = usePermissions()
  const { data, isPending, isError, refetch } = useWorkingHours()
  const save = useSetWorkingHours()
  const [draft, setDraft] = useState<DraftDay[] | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [showErrors, setShowErrors] = useState(false)
  const busy = useRef(false)
  const errors = draft ? draftErrors(draft) : {}

  function change(index: number, update: Partial<DraftDay>) {
    setDraft((week) => week && week.map((day, i) => (i === index ? { ...day, ...update } : day)))
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
      await save.mutateAsync(daysFromDraft(draft))
      toast.success('Working hours saved')
      setDraft(null)
    } catch (err) {
      setNotice(apiErrorMessage(err, "Couldn't save the working hours. Try again."))
    } finally {
      busy.current = false
    }
  }

  return (
    <Card className="gap-4" aria-labelledby="working-hours-title" role="region">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle id="working-hours-title" className="flex items-center gap-2">
              <Clock className="size-5" aria-hidden /> Working hours
            </CardTitle>
            <CardDescription>When the hospital is open, on its own clock.</CardDescription>
          </div>
          {can('settings.update') && !draft && data && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setDraft(draftFromDays(data))
                setNotice(null)
                setShowErrors(false)
              }}
            >
              <Pencil className="size-4" aria-hidden /> Edit hours
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <Skeleton className="h-40 w-full rounded-xl" aria-label="Loading working hours" />
        ) : isError ? (
          <Alert variant="error" title="Couldn't load the working hours">
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RotateCw className="size-4" aria-hidden /> Retry
            </Button>
          </Alert>
        ) : draft ? (
          <form
            className="space-y-3"
            aria-label="Edit working hours"
            onSubmit={(e) => {
              e.preventDefault()
              void submit()
            }}
          >
            {notice && <Alert variant="error">{notice}</Alert>}
            {draft.map((day, index) => {
              const name = DAY_NAMES[index]
              const error = showErrors ? errors[index] : undefined
              return (
                <div key={name} role="group" aria-label={name} className="space-y-1">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="font-body text-body-md text-on-surface w-28 font-semibold">{name}</span>
                    <Select value={day.mode} onValueChange={(v) => change(index, { mode: v as DayMode })}>
                      <SelectTrigger className="w-40" aria-label={`${name} status`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(Object.keys(MODE_LABEL) as DayMode[]).map((mode) => (
                          <SelectItem key={mode} value={mode}>
                            {MODE_LABEL[mode]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {day.mode === 'open' && (
                      <>
                        <Input
                          type="time"
                          aria-label={`${name} opens`}
                          aria-invalid={!!error}
                          value={day.open}
                          onChange={(e) => change(index, { open: e.target.value })}
                          className="w-32"
                        />
                        <span aria-hidden>–</span>
                        <Input
                          type="time"
                          aria-label={`${name} closes`}
                          aria-invalid={!!error}
                          value={day.close}
                          onChange={(e) => change(index, { close: e.target.value })}
                          className="w-32"
                        />
                      </>
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
            <div className="flex flex-wrap justify-end gap-2 pt-2">
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
          <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-[10rem_1fr]">
            {DAY_NAMES.map((name, index) => (
              <div key={name} className="contents">
                <dt className="font-body text-body-md text-on-surface font-semibold">{name}</dt>
                <dd className="font-body text-body-md text-on-surface-variant">
                  {describeDay(data.find((d) => d.day_of_week === index))}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </CardContent>
    </Card>
  )
}
