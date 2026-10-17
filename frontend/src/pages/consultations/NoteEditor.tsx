import { useState } from 'react'
import { toast } from 'sonner'
import { CheckCircle2, Loader2, Plus, Save, Trash2 } from 'lucide-react'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  useFinalizeConsultation,
  useSaveConsultation,
  useStartConsultation,
  type Consultation,
  type ConsultationSections,
  type Diagnosis,
} from '@/api/consultations'
import { apiErrorMessage, fieldErrorsOf } from '@/lib/apiErrors'

const TEXT_SECTIONS = [
  {
    key: 'chief_complaint',
    label: 'Chief complaint',
    rows: 2,
    placeholder: 'Why the patient came, in their words',
  },
  {
    key: 'history',
    label: 'History',
    rows: 4,
    placeholder: 'Present illness, past history, medicines, allergies',
  },
  {
    key: 'examination',
    label: 'Examination',
    rows: 4,
    placeholder: 'Findings on examination',
  },
  {
    key: 'plan',
    label: 'Plan and advice',
    rows: 4,
    placeholder: 'Treatment, advice, investigations, referral',
  },
] as const

type TextKey = (typeof TEXT_SECTIONS)[number]['key']

interface Draft {
  chief_complaint: string
  history: string
  examination: string
  plan: string
  follow_up_date: string
  diagnoses: { code: string; description: string }[]
}

function draftFrom(note: Consultation | null): Draft {
  return {
    chief_complaint: note?.chief_complaint ?? '',
    history: note?.history ?? '',
    examination: note?.examination ?? '',
    plan: note?.plan ?? '',
    follow_up_date: note?.follow_up_date ?? '',
    diagnoses: note?.diagnoses.length
      ? note.diagnoses.map((d) => ({
          code: d.code ?? '',
          description: d.description,
        }))
      : [{ code: '', description: '' }],
  }
}

function bodyFrom(draft: Draft): ConsultationSections {
  const diagnoses: Diagnosis[] = draft.diagnoses
    .filter((d) => d.description.trim())
    .map((d) => ({
      code: d.code.trim() || null,
      description: d.description.trim(),
    }))
  return {
    chief_complaint: draft.chief_complaint.trim() || null,
    history: draft.history.trim() || null,
    examination: draft.examination.trim() || null,
    plan: draft.plan.trim() || null,
    follow_up_date: draft.follow_up_date || null,
    diagnoses,
  }
}

/**
 * The doctor's note for a visit: write it, save it as a draft, finalize it.
 * Shown only to the visit's doctor (or anyone with `consultation.write` before
 * the note exists — the server refuses anyone but the visit's doctor).
 */
export function NoteEditor({ appointmentId, note }: { appointmentId: string; note: Consultation | null }) {
  const start = useStartConsultation(appointmentId)
  const save = useSaveConsultation(appointmentId, note?.id)
  const finalize = useFinalizeConsultation(appointmentId, note?.id)
  const [draft, setDraft] = useState<Draft>(() => draftFrom(note))
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [refusal, setRefusal] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)
  const busy = start.isPending || save.isPending || finalize.isPending

  function report(err: unknown, fallback: string) {
    const fields = fieldErrorsOf(err)
    setErrors(Object.fromEntries(fields.map((f) => [f.field, f.message])))
    setRefusal(fields.length ? null : apiErrorMessage(err, fallback))
  }

  async function persist(): Promise<Consultation | null> {
    setErrors({})
    setRefusal(null)
    try {
      const saved = note ? await save.mutateAsync(bodyFrom(draft)) : await start.mutateAsync(bodyFrom(draft))
      return saved
    } catch (err) {
      report(err, "Couldn't save the note. Try again.")
      return null
    }
  }

  async function onSave() {
    if (await persist()) toast.success('Draft saved')
  }

  async function onFinalize() {
    const saved = await persist()
    if (!saved) {
      setConfirming(false)
      return
    }
    try {
      await finalize.mutateAsync()
      toast.success('Consultation finalized')
    } catch (err) {
      report(err, "Couldn't finalize the note. Try again.")
    } finally {
      setConfirming(false)
    }
  }

  const setText = (key: TextKey | 'follow_up_date', value: string) => setDraft((d) => ({ ...d, [key]: value }))
  const setDiagnosis = (i: number, part: 'code' | 'description', value: string) =>
    setDraft((d) => ({
      ...d,
      diagnoses: d.diagnoses.map((x, j) => (j === i ? { ...x, [part]: value } : x)),
    }))

  return (
    <section aria-labelledby="note-title" className="neo-extruded bg-surface space-y-5 rounded-2xl p-6">
      <h2 id="note-title" className="font-display text-title-lg text-primary font-bold">
        Consultation note
      </h2>

      {refusal && (
        <Alert variant="error" title="Not saved">
          {refusal}
        </Alert>
      )}

      {TEXT_SECTIONS.map(({ key, label, rows, placeholder }) => (
        <Field key={key} label={label} error={errors[key]} required={key === 'chief_complaint'}>
          {(ids) => (
            <Textarea
              {...ids}
              rows={rows}
              maxLength={10_000}
              placeholder={placeholder}
              value={draft[key]}
              onChange={(e) => setText(key, e.target.value)}
            />
          )}
        </Field>
      ))}

      <fieldset className="space-y-3">
        <legend className="font-body text-on-surface text-sm font-medium">
          Diagnoses <span className="text-error">*</span>
        </legend>
        {draft.diagnoses.map((d, i) => (
          <div key={i} className="flex items-end gap-2">
            <Field label={`Diagnosis ${i + 1}`} className="flex-1">
              {(ids) => (
                <Input
                  {...ids}
                  maxLength={500}
                  placeholder="e.g. Acute pharyngitis"
                  value={d.description}
                  onChange={(e) => setDiagnosis(i, 'description', e.target.value)}
                />
              )}
            </Field>
            <Field label="Code" className="w-28">
              {(ids) => (
                <Input
                  {...ids}
                  maxLength={20}
                  placeholder="ICD-10"
                  value={d.code}
                  onChange={(e) => setDiagnosis(i, 'code', e.target.value)}
                />
              )}
            </Field>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={`Remove diagnosis ${i + 1}`}
              disabled={draft.diagnoses.length === 1}
              onClick={() =>
                setDraft((x) => ({
                  ...x,
                  diagnoses: x.diagnoses.filter((_, j) => j !== i),
                }))
              }
            >
              <Trash2 className="size-4" aria-hidden />
            </Button>
          </div>
        ))}
        {errors.diagnoses && (
          <p role="alert" className="font-body text-error text-xs">
            {errors.diagnoses}
          </p>
        )}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={draft.diagnoses.length >= 20}
          onClick={() =>
            setDraft((x) => ({
              ...x,
              diagnoses: [...x.diagnoses, { code: '', description: '' }],
            }))
          }
        >
          <Plus className="size-4" aria-hidden /> Add diagnosis
        </Button>
      </fieldset>

      <Field label="Follow-up date" error={errors.follow_up_date} className="max-w-xs">
        {(ids) => (
          <Input
            {...ids}
            type="date"
            value={draft.follow_up_date}
            onChange={(e) => setText('follow_up_date', e.target.value)}
          />
        )}
      </Field>

      {confirming ? (
        <Alert variant="warning" title="Finalize this note?">
          <p>Once finalized the note can't be edited. Later information is added as an addendum.</p>
          <div className="mt-3 flex gap-2">
            <Button onClick={() => void onFinalize()} disabled={busy} aria-busy={busy}>
              {busy && <Loader2 className="size-4 animate-spin" aria-hidden />}
              Finalize
            </Button>
            <Button variant="ghost" onClick={() => setConfirming(false)} disabled={busy}>
              Keep editing
            </Button>
          </div>
        </Alert>
      ) : (
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="outline" onClick={() => void onSave()} disabled={busy} aria-busy={busy}>
            {busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Save className="size-4" aria-hidden />}
            Save draft
          </Button>
          <Button onClick={() => setConfirming(true)} disabled={busy}>
            <CheckCircle2 className="size-4" aria-hidden /> Finalize note
          </Button>
        </div>
      )}
    </section>
  )
}
