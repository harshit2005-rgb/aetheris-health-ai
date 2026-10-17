import { useMutation, useQueryClient } from '@tanstack/react-query'
import { http } from '@/api/http'
import { api } from '@/lib/api'
import { blobApiError, filenameFromContentDisposition } from '@/lib/download'

/**
 * Spreadsheet import — typed wrappers over `backend/app/api/v1/imports.py`
 * (docs/modules/17-data-import-export.md §9). The file is sent as the request
 * body itself, with its name in `X-Filename`.
 */

export type ImportKind = 'patients' | 'services' | 'medicines' | 'lab-tests'

export const IMPORT_KINDS: {
  value: ImportKind
  label: string
  hint: string
}[] = [
  {
    value: 'patients',
    label: 'Patients',
    hint: 'Name, date of birth, gender, phone, address',
  },
  {
    value: 'services',
    label: 'Billing services',
    hint: 'Code, name, category, price',
  },
  {
    value: 'medicines',
    label: 'Medicines',
    hint: 'SKU, name, strength, form, price',
  },
  {
    value: 'lab-tests',
    label: 'Lab tests',
    hint: 'Code, name, unit, reference range, price',
  },
]

export interface ImportProblem {
  row: number
  column: string
  message: string
}

export interface ImportReport {
  kind: ImportKind
  dry_run: boolean
  total_rows: number
  ready: number
  created: number
  skipped: { row: number; reason: string }[]
  problems: ImportProblem[]
  ignored_columns: string[]
}

/** The API's limits (§4 rule 2), checked before uploading to save a round trip. */
export const MAX_IMPORT_BYTES = 5 * 1024 * 1024

const XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

/** The media type to declare: the browser's, or one inferred from the name when it has none. */
export function importContentType(file: File): string {
  if (file.type) return file.type
  return file.name.toLowerCase().endsWith('.csv') ? 'text/csv' : XLSX
}

/** What is wrong with a file before it is sent, or null. */
export function importFileProblem(file: File): string | null {
  const name = file.name.toLowerCase()
  if (!name.endsWith('.xlsx') && !name.endsWith('.csv')) return 'Choose an Excel (.xlsx) or CSV (.csv) file.'
  if (file.size > MAX_IMPORT_BYTES) return 'The file is larger than 5 MB. Split it into smaller files.'
  if (file.size === 0) return 'The file is empty.'
  return null
}

/** Check (dry run) or import a file. A real import refreshes every list it may have added to. */
export function useImportSpreadsheet() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ kind, file, dryRun }: { kind: ImportKind; file: File; dryRun: boolean }) =>
      http.post<ImportReport>(`/imports/${kind}`, file, {
        params: { dry_run: dryRun },
        headers: {
          'Content-Type': importContentType(file),
          'X-Filename': file.name,
        },
      }),
    onSuccess: (report) => {
      if (report.dry_run || report.created === 0) return
      const keys: Record<ImportKind, string[]> = {
        patients: ['patients'],
        services: ['services'],
        medicines: ['pharmacy'],
        'lab-tests': ['lab'],
      }
      return qc.invalidateQueries({ queryKey: keys[report.kind] })
    },
  })
}

/** Download the blank template for one kind. */
export async function fetchImportTemplate(kind: ImportKind): Promise<{ blob: Blob; filename: string }> {
  try {
    const res = await api.get<Blob>(`/imports/${kind}/template`, {
      responseType: 'blob',
    })
    const headers = res.headers as Record<string, unknown> | undefined
    return {
      blob: res.data,
      filename: filenameFromContentDisposition(headers?.['content-disposition']) ?? `atheris-${kind}-template.xlsx`,
    }
  } catch (err) {
    throw await blobApiError(err)
  }
}
