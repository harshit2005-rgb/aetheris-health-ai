import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { InternalAxiosRequestConfig } from 'axios'
import type { ImportReport } from '@/api/dataImport'
import { signIn, signOut } from '@/test/auth'
import { fail, installFakeApi, ok, type FakeApi, type Outcome } from '@/test/fakeApi'
import SettingsPage from './SettingsPage'

const { toastSuccess, toastError, saveBlob } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  saveBlob: vi.fn(),
}))
vi.mock('sonner', () => ({
  toast: { success: toastSuccess, error: toastError },
}))
vi.mock('@/lib/download', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/download')>()),
  saveBlob,
}))

const ADMIN = ['settings.read', 'data.import', 'data.export']
const XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

function report(extra: Partial<ImportReport> = {}): ImportReport {
  return {
    kind: 'patients',
    dry_run: true,
    total_rows: 4,
    ready: 2,
    created: 0,
    skipped: [{ row: 3, reason: 'Already registered as MRN-2026-00007.' }],
    problems: [
      {
        row: 5,
        column: 'Date of birth',
        message: 'Use a date like 1990-01-31 or 31/01/1990.',
      },
    ],
    ignored_columns: ['favourite_colour'],
    ...extra,
  }
}

let fake: FakeApi
let answer: (config: InternalAxiosRequestConfig) => Outcome

function server(config: InternalAxiosRequestConfig): Outcome {
  const url = config.url ?? ''
  if (url === '/hospitals/me' || url.startsWith('/hospitals/')) return fail(404, 'n/a')
  return answer(config)
}

function renderSettings(permissions: string[]) {
  signIn(permissions)
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <SettingsPage />
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

async function openDataTab(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('tab', { name: /Data/ }))
}

const imports = () => fake.sent.filter((c) => c.method === 'post' && c.url?.startsWith('/imports/'))

beforeEach(() => {
  toastSuccess.mockReset()
  toastError.mockReset()
  saveBlob.mockReset()
  answer = (config) => {
    const dryRun = (config.params as { dry_run: boolean }).dry_run
    return ok(dryRun ? report() : report({ dry_run: false, created: 2 }))
  }
  fake = installFakeApi(server)
})

afterEach(() => {
  fake.restore()
  signOut()
})

describe('importing a spreadsheet', () => {
  it('checks the file first, then imports on request', async () => {
    const user = userEvent.setup()
    renderSettings(ADMIN)
    await openDataTab(user)

    const file = new File(['xlsx bytes'], 'old-system.xlsx', { type: XLSX })
    await user.upload(screen.getByLabelText(/Patients file/), file)

    // The check: nothing saved yet, and the report says why rows are out.
    expect(await screen.findByText('Ready to import')).toBeInTheDocument()
    const [check] = imports()
    expect(check.url).toBe('/imports/patients')
    expect(check.params).toEqual({ dry_run: true })
    expect(check.headers['X-Filename']).toBe('old-system.xlsx')
    expect(check.headers['Content-Type']).toBe(XLSX)
    const problems = screen.getByRole('table')
    expect(within(problems).getByText('Date of birth')).toBeInTheDocument()
    expect(screen.getByText(/favourite_colour/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Import 2 rows' }))

    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Imported 2 records'))
    expect(imports()[1].params).toEqual({ dry_run: false })
    expect(screen.getByText('Import finished')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Import \d/ })).not.toBeInTheDocument()
  })

  it('imports into the kind that was picked', async () => {
    const user = userEvent.setup()
    renderSettings(ADMIN)
    await openDataTab(user)

    await user.click(screen.getByRole('radio', { name: /Medicines/ }))
    await user.upload(screen.getByLabelText(/Medicines file/), new File(['SKU,Name\n'], 'meds.csv', { type: '' }))

    await waitFor(() => expect(imports()).toHaveLength(1))
    expect(imports()[0].url).toBe('/imports/medicines')
    // A file the browser gives no type is declared from its name.
    expect(imports()[0].headers['Content-Type']).toBe('text/csv')
  })

  it('offers no Import button when nothing is ready', async () => {
    answer = () => ok(report({ ready: 0 }))
    const user = userEvent.setup()
    renderSettings(ADMIN)
    await openDataTab(user)

    await user.upload(screen.getByLabelText(/Patients file/), new File(['x'], 'p.xlsx', { type: XLSX }))

    expect(await screen.findByText('Ready to import')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Import \d/ })).not.toBeInTheDocument()
  })

  it('refuses a file that is not a spreadsheet without sending it', async () => {
    const user = userEvent.setup({ applyAccept: false })
    renderSettings(ADMIN)
    await openDataTab(user)

    await user.upload(
      screen.getByLabelText(/Patients file/),
      new File(['%PDF'], 'scan.pdf', { type: 'application/pdf' }),
    )

    expect(await screen.findByText('Choose an Excel (.xlsx) or CSV (.csv) file.')).toBeInTheDocument()
    expect(imports()).toHaveLength(0)
  })

  it("shows the server's reason when it can't read the file", async () => {
    answer = () => fail(422, "This doesn't look like an Excel (.xlsx) file.")
    const user = userEvent.setup()
    renderSettings(ADMIN)
    await openDataTab(user)

    await user.upload(screen.getByLabelText(/Patients file/), new File(['x'], 'p.xlsx', { type: XLSX }))

    expect(await screen.findByText("This doesn't look like an Excel (.xlsx) file.")).toBeInTheDocument()
  })

  it('downloads the template for the picked kind', async () => {
    answer = () => ({
      status: 200,
      data: new Blob(['xlsx']),
      headers: {
        'content-disposition': 'attachment; filename="atheris-lab-tests-template.xlsx"',
      },
    })
    const user = userEvent.setup()
    renderSettings(ADMIN)
    await openDataTab(user)

    await user.click(screen.getByRole('radio', { name: /Lab tests/ }))
    await user.click(screen.getByRole('button', { name: /Download lab tests template/ }))

    await waitFor(() => expect(saveBlob).toHaveBeenCalledWith(expect.any(Blob), 'atheris-lab-tests-template.xlsx'))
    expect(fake.sent.at(-1)?.url).toBe('/imports/lab-tests/template')
  })
})

describe('who sees the Data tab', () => {
  it('is hidden without data.import', async () => {
    renderSettings(['settings.read'])

    expect(await screen.findByRole('tab', { name: /Hospital/ })).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: /Data/ })).not.toBeInTheDocument()
  })
})
