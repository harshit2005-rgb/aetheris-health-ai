import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { Download, FileSpreadsheet, Loader2, Upload } from 'lucide-react'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  IMPORT_KINDS,
  fetchImportTemplate,
  importFileProblem,
  useImportSpreadsheet,
  type ImportKind,
  type ImportReport,
} from '@/api/dataImport'
import { apiErrorMessage } from '@/lib/apiErrors'
import { saveBlob } from '@/lib/download'
import { cn } from '@/lib/utils'

/** How many problem rows to list; the rest are counted. */
const SHOWN = 50

function plural(n: number, one: string, many = `${one}s`) {
  return `${n.toLocaleString('en-IN')} ${n === 1 ? one : many}`
}

function ReportView({ report }: { report: ImportReport }) {
  const done = !report.dry_run
  return (
    <div className="space-y-4" aria-live="polite">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: 'Rows in file', value: report.total_rows },
          {
            label: done ? 'Imported' : 'Ready to import',
            value: done ? report.created : report.ready,
          },
          { label: 'Already here', value: report.skipped.length },
          { label: 'With problems', value: report.problems.length },
        ].map((s) => (
          <div key={s.label} className="bg-surface-container-low rounded-xl p-3">
            <dt className="font-body text-on-surface-variant text-xs">{s.label}</dt>
            <dd className="font-display text-title-lg text-on-surface font-bold">{s.value.toLocaleString('en-IN')}</dd>
          </div>
        ))}
      </dl>

      {report.ignored_columns.length > 0 && (
        <p className="font-body text-on-surface-variant text-sm">
          Columns not in the template were ignored: {report.ignored_columns.join(', ')}.
        </p>
      )}

      {report.problems.length > 0 && (
        <div>
          <h3 className="font-body text-on-surface mb-2 text-sm font-semibold">Rows with problems — not imported</h3>
          <div className="border-outline-variant max-h-72 overflow-auto rounded-xl border">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-container-low sticky top-0">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Row
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Column
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Problem
                  </th>
                </tr>
              </thead>
              <tbody>
                {report.problems.slice(0, SHOWN).map((p, i) => (
                  <tr key={i} className="border-outline-variant border-t">
                    <td className="px-3 py-2 font-mono">{p.row}</td>
                    <td className="px-3 py-2">{p.column}</td>
                    <td className="px-3 py-2">{p.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {report.problems.length > SHOWN && (
            <p className="font-body text-on-surface-variant mt-2 text-xs">
              And {plural(report.problems.length - SHOWN, 'more problem')}. Fix these first, then check again.
            </p>
          )}
        </div>
      )}

      {report.skipped.length > 0 && (
        <details className="font-body text-sm">
          <summary className="text-on-surface cursor-pointer font-semibold">
            {plural(report.skipped.length, 'row')} already in Atheris — left out, not overwritten
          </summary>
          <ul className="text-on-surface-variant mt-2 space-y-1">
            {report.skipped.slice(0, SHOWN).map((s) => (
              <li key={s.row}>
                Row {s.row}: {s.reason}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

/**
 * Import patients and catalogs from a spreadsheet (docs/modules/17-data-import-export.md §12).
 * Every file is checked first (a dry run that saves nothing); importing is a second, explicit step.
 */
export function DataImportCard() {
  const [kind, setKind] = useState<ImportKind>('patients')
  const [file, setFile] = useState<File | null>(null)
  const [report, setReport] = useState<ImportReport | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const run = useImportSpreadsheet()

  function reset(nextKind: ImportKind = kind) {
    setKind(nextKind)
    setFile(null)
    setReport(null)
    setProblem(null)
    if (input.current) input.current.value = ''
  }

  async function check(chosen: File) {
    setReport(null)
    const issue = importFileProblem(chosen)
    setProblem(issue)
    if (issue) return
    try {
      setReport(await run.mutateAsync({ kind, file: chosen, dryRun: true }))
    } catch (err) {
      setProblem(apiErrorMessage(err, "Couldn't check the file. Try again."))
    }
  }

  async function importNow() {
    if (!file) return
    try {
      const done = await run.mutateAsync({ kind, file, dryRun: false })
      setReport(done)
      toast.success(`Imported ${plural(done.created, 'record')}`)
    } catch (err) {
      setProblem(apiErrorMessage(err, "Couldn't import the file. Try again."))
    }
  }

  async function downloadTemplate() {
    setDownloading(true)
    try {
      const { blob, filename } = await fetchImportTemplate(kind)
      saveBlob(blob, filename)
    } catch (err) {
      toast.error(apiErrorMessage(err, "Couldn't download the template. Try again."))
    } finally {
      setDownloading(false)
    }
  }

  const label = IMPORT_KINDS.find((k) => k.value === kind)?.label ?? ''
  const canImport = report?.dry_run === true && report.ready > 0

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileSpreadsheet className="size-5" aria-hidden /> Import from a spreadsheet
        </CardTitle>
        <CardDescription>
          Bring in patients and price lists from Excel or CSV. Each file is checked first and nothing is saved until you
          press Import. Records already in Atheris are left alone. Doctors are added through Users → Invite, because
          each needs their own login.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div role="radiogroup" aria-label="What to import" className="grid gap-2 sm:grid-cols-4">
          {IMPORT_KINDS.map((k) => (
            <button
              key={k.value}
              type="button"
              role="radio"
              aria-checked={kind === k.value}
              onClick={() => reset(k.value)}
              className={cn(
                'rounded-xl border p-3 text-left transition-colors',
                kind === k.value
                  ? 'border-primary bg-primary-container/10'
                  : 'border-outline-variant hover:bg-surface-container-low',
              )}
            >
              <span className="font-body text-on-surface block text-sm font-semibold">{k.label}</span>
              <span className="font-body text-on-surface-variant block text-xs">{k.hint}</span>
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <Button
            variant="outline"
            onClick={() => void downloadTemplate()}
            disabled={downloading}
            aria-busy={downloading}
          >
            {downloading ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Download className="size-4" aria-hidden />
            )}
            Download {label.toLowerCase()} template
          </Button>
          <Field label={`${label} file (.xlsx or .csv, up to 5 MB)`} className="min-w-64 flex-1">
            {(ids) => (
              <Input
                {...ids}
                ref={input}
                type="file"
                accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
                disabled={run.isPending}
                onChange={(e) => {
                  const chosen = e.target.files?.[0] ?? null
                  setFile(chosen)
                  if (chosen) void check(chosen)
                }}
              />
            )}
          </Field>
        </div>

        {run.isPending && (
          <p className="font-body text-on-surface-variant flex items-center gap-2 text-sm" role="status">
            <Loader2 className="size-4 animate-spin" aria-hidden /> {report ? 'Importing…' : 'Checking the file…'}
          </p>
        )}

        {problem && (
          <Alert variant="error" title="The file can't be used">
            {problem}
          </Alert>
        )}

        {report && <ReportView report={report} />}

        {report && !report.dry_run && (
          <Alert variant="success" title="Import finished">
            {plural(report.created, 'record')} added.{' '}
            <button type="button" className="text-secondary underline" onClick={() => reset()}>
              Import another file
            </button>
          </Alert>
        )}

        {canImport && (
          <div className="flex justify-end">
            <Button onClick={() => void importNow()} disabled={run.isPending} aria-busy={run.isPending}>
              {run.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Upload className="size-4" aria-hidden />
              )}
              Import {plural(report.ready, 'row')}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
