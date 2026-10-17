import { useState } from "react";
import { toast } from "sonner";
import { Activity, Loader2, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  useRecordVitals,
  type Consultation,
  type Vitals,
} from "@/api/consultations";
import { VITALS, toBody, vitalsProblem, type VitalKey } from "./vitals";
import { apiErrorMessage } from "@/lib/apiErrors";
import { formatDateTime } from "@/lib/format";

function display(vitals: Vitals | null, bmi: string | null) {
  const v = vitals ?? {};
  const rows: { label: string; value: string }[] = [];
  if (v.bp_systolic !== undefined && v.bp_diastolic !== undefined)
    rows.push({
      label: "Blood pressure",
      value: `${v.bp_systolic}/${v.bp_diastolic} mmHg`,
    });
  for (const { key, label, unit } of VITALS) {
    if (key === "bp_systolic" || key === "bp_diastolic") continue;
    const value = v[key];
    if (value !== undefined && value !== null)
      rows.push({ label, value: `${value} ${unit}` });
  }
  if (bmi) rows.push({ label: "BMI", value: bmi });
  return rows;
}

/**
 * The visit's vitals: shown to everyone who can read the note, editable on a
 * draft by anyone holding `consultation.vitals.record` (a nurse, the doctor).
 */
export function VitalsCard({
  appointmentId,
  note,
  canRecord,
}: {
  appointmentId: string;
  note: Consultation | null;
  canRecord: boolean;
}) {
  const record = useRecordVitals(appointmentId);
  const editable = canRecord && (!note || note.status === "draft");
  const empty = (): Record<VitalKey, string> =>
    Object.fromEntries(
      VITALS.map(({ key }) => [
        key,
        note?.vitals?.[key] != null ? String(note.vitals[key]) : "",
      ]),
    ) as Record<VitalKey, string>;
  const [editing, setEditing] = useState(false);
  const [values, setValues] = useState(empty);
  const [problem, setProblem] = useState<string | null>(null);
  const rows = display(note?.vitals ?? null, note?.bmi ?? null);

  async function save() {
    const issue = vitalsProblem(values);
    setProblem(issue);
    if (issue) return;
    try {
      await record.mutateAsync(toBody(values));
      toast.success("Vitals recorded");
      setEditing(false);
    } catch (err) {
      setProblem(apiErrorMessage(err, "Couldn't save the vitals. Try again."));
    }
  }

  return (
    <section
      aria-labelledby="vitals-title"
      className="neo-extruded bg-surface rounded-2xl p-6"
    >
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2
          id="vitals-title"
          className="font-display text-title-lg text-primary flex items-center gap-2 font-bold"
        >
          <Activity className="size-5" aria-hidden /> Vitals
        </h2>
        {editable && !editing && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setValues(empty());
              setProblem(null);
              setEditing(true);
            }}
          >
            <Pencil className="size-4" aria-hidden />{" "}
            {rows.length ? "Update vitals" : "Record vitals"}
          </Button>
        )}
      </div>

      {editing ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
          className="space-y-4"
          aria-label="Record vitals"
        >
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {VITALS.map(({ key, label, unit, min, max, step }) => (
              <Field key={key} label={`${label} (${unit})`}>
                {(ids) => (
                  <Input
                    {...ids}
                    type="number"
                    inputMode="decimal"
                    min={min}
                    max={max}
                    step={step}
                    value={values[key]}
                    onChange={(e) =>
                      setValues((v) => ({ ...v, [key]: e.target.value }))
                    }
                  />
                )}
              </Field>
            ))}
          </div>
          {problem && (
            <p role="alert" className="font-body text-error text-sm">
              {problem}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setEditing(false)}
              disabled={record.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={record.isPending}
              aria-busy={record.isPending}
            >
              {record.isPending && (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              )}
              Save vitals
            </Button>
          </div>
        </form>
      ) : rows.length ? (
        <>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
            {rows.map((r) => (
              <div key={r.label}>
                <dt className="font-body text-on-surface-variant text-xs">
                  {r.label}
                </dt>
                <dd className="font-body text-on-surface text-body-md font-semibold">
                  {r.value}
                </dd>
              </div>
            ))}
          </dl>
          {note?.vitals_recorded_at && (
            <p className="font-body text-outline mt-3 text-xs">
              Recorded {formatDateTime(note.vitals_recorded_at)}
            </p>
          )}
        </>
      ) : (
        <p className="font-body text-on-surface-variant text-sm">
          No vitals recorded yet.
        </p>
      )}
    </section>
  );
}
