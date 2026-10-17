import { useState } from 'react'
import { toast } from 'sonner'
import { Loader2, MessageSquarePlus } from 'lucide-react'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Textarea } from '@/components/ui/textarea'
import { useAddAddendum, type Consultation } from '@/api/consultations'
import { apiErrorMessage } from '@/lib/apiErrors'
import { formatDate, formatDateTime } from '@/lib/format'

function Section({ title, text }: { title: string; text: string | null }) {
  if (!text) return null
  return (
    <div>
      <h3 className="font-body text-on-surface-variant text-xs font-semibold tracking-wide uppercase">{title}</h3>
      <p className="font-body text-on-surface text-body-md mt-1 whitespace-pre-wrap">{text}</p>
    </div>
  )
}

/** A note read-only: finalized, or someone else's. Its doctor can add addenda once finalized. */
export function NoteView({ appointmentId, note }: { appointmentId: string; note: Consultation }) {
  const add = useAddAddendum(appointmentId, note.id)
  const [text, setText] = useState('')
  const [adding, setAdding] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const canAdd = note.is_own && note.status === 'finalized'

  async function submit() {
    if (!text.trim()) {
      setProblem('Write the addendum first.')
      return
    }
    try {
      await add.mutateAsync(text.trim())
      toast.success('Addendum added')
      setText('')
      setAdding(false)
      setProblem(null)
    } catch (err) {
      setProblem(apiErrorMessage(err, "Couldn't add the addendum. Try again."))
    }
  }

  return (
    <section aria-labelledby="note-title" className="neo-extruded bg-surface space-y-5 rounded-2xl p-6">
      <h2 id="note-title" className="font-display text-title-lg text-primary font-bold">
        Consultation note
      </h2>
      {note.status === 'draft' && (
        <Alert variant="info" title="Draft">
          {note.doctor_name} is still writing this note.
        </Alert>
      )}
      <Section title="Chief complaint" text={note.chief_complaint} />
      <Section title="History" text={note.history} />
      <Section title="Examination" text={note.examination} />
      {note.diagnoses.length > 0 && (
        <div>
          <h3 className="font-body text-on-surface-variant text-xs font-semibold tracking-wide uppercase">Diagnoses</h3>
          <ul className="mt-1 list-disc space-y-1 pl-5" aria-label="Diagnoses">
            {note.diagnoses.map((d, i) => (
              <li key={i} className="font-body text-on-surface text-body-md">
                {d.description}
                {d.code && <span className="text-outline ml-2 font-mono text-sm">{d.code}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
      <Section title="Plan and advice" text={note.plan} />
      {note.follow_up_date && <Section title="Follow-up" text={formatDate(note.follow_up_date)} />}
      {note.finalized_at && (
        <p className="font-body text-outline text-xs">Finalized {formatDateTime(note.finalized_at)}</p>
      )}

      {(note.addenda.length > 0 || canAdd) && (
        <div className="border-outline-variant space-y-3 border-t pt-4">
          <h3 className="font-display text-title-md text-primary font-bold">Addenda</h3>
          {note.addenda.length === 0 && (
            <p className="font-body text-on-surface-variant text-sm">
              Nothing has been added since the note was finalized.
            </p>
          )}
          <ol className="space-y-3" aria-label="Addenda">
            {note.addenda.map((a) => (
              <li key={a.id} className="bg-surface-container-low rounded-xl p-3">
                <p className="font-body text-on-surface text-body-md whitespace-pre-wrap">{a.text}</p>
                <p className="font-body text-outline mt-1 text-xs">{formatDateTime(a.added_at)}</p>
              </li>
            ))}
          </ol>
          {canAdd &&
            (adding ? (
              <form
                className="space-y-3"
                onSubmit={(e) => {
                  e.preventDefault()
                  void submit()
                }}
              >
                <Field label="Addendum" error={problem ?? undefined}>
                  {(ids) => (
                    <Textarea
                      {...ids}
                      rows={3}
                      maxLength={5000}
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                      placeholder="e.g. CBC normal; continue the plan."
                    />
                  )}
                </Field>
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="ghost" onClick={() => setAdding(false)} disabled={add.isPending}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={add.isPending} aria-busy={add.isPending}>
                    {add.isPending && <Loader2 className="size-4 animate-spin" aria-hidden />}
                    Add addendum
                  </Button>
                </div>
              </form>
            ) : (
              <Button variant="outline" size="sm" onClick={() => setAdding(true)}>
                <MessageSquarePlus className="size-4" aria-hidden /> Add addendum
              </Button>
            ))}
        </div>
      )}
    </section>
  )
}
