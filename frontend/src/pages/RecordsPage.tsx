import { Icon } from '@/components/ui/icon'
import { cn } from '@/lib/utils'

type Status = 'Stable' | 'Monitoring' | 'Review Needed' | 'Discharged'

interface PatientRecord {
  id: string
  diagnosis: string
  agent: string
  status: Status
}

const RECORDS: PatientRecord[] = [
  { id: 'PT-8291-A', diagnosis: 'Hypertension, Stage 2', agent: 'CardioBot-X1', status: 'Stable' },
  { id: 'PT-4022-C', diagnosis: 'Acute Bronchitis', agent: 'Pulmo-Assist', status: 'Monitoring' },
  { id: 'PT-9188-B', diagnosis: 'Type 2 Diabetes', agent: 'Endo-AI', status: 'Review Needed' },
  { id: 'PT-1104-D', diagnosis: 'Post-Op Recovery', agent: 'SurgiCare-V2', status: 'Discharged' },
  { id: 'PT-6357-F', diagnosis: 'Atrial Fibrillation', agent: 'CardioBot-X1', status: 'Monitoring' },
  { id: 'PT-2048-E', diagnosis: 'Migraine, Chronic', agent: 'NeuroScope', status: 'Stable' },
  { id: 'PT-7791-G', diagnosis: 'Pneumonia', agent: 'Pulmo-Assist', status: 'Review Needed' },
]

const STATUS_STYLES: Record<string, string> = {
  Stable: 'bg-secondary-container/20 text-on-secondary-container',
  Monitoring: 'bg-tertiary-container/25 text-tertiary',
  'Review Needed': 'bg-error-container/50 text-on-error-container',
  Discharged: 'bg-surface-container-highest text-on-surface-variant',
}

export default function RecordsPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-8">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <h1 className="font-display text-primary text-3xl font-extrabold tracking-tight md:text-headline-xl">
            Clinical Records
          </h1>
          <p className="font-body text-body-md text-on-surface-variant mt-2">
            Patient administration and AI agent assignments.
          </p>
        </div>
        <div className="flex w-full gap-3 md:w-auto">
          <div className="relative w-full md:w-64">
            <Icon
              name="search"
              className="text-outline absolute top-1/2 left-3 -translate-y-1/2 text-lg"
            />
            <input
              type="text"
              placeholder="Search Patient ID..."
              className="neo-pressed bg-surface/50 font-body text-body-sm placeholder:text-outline-variant focus:ring-secondary w-full rounded-full py-2.5 pr-4 pl-10 outline-none focus:ring-2"
            />
          </div>
          <button className="neo-extruded bg-surface text-primary font-body text-body-sm hover:text-secondary flex items-center gap-2 rounded-full px-6 py-2.5 whitespace-nowrap transition-colors active:scale-95">
            <Icon name="download" className="text-lg" />
            Export
          </button>
        </div>
      </div>

      {/* Mobile: card list */}
      <div className="space-y-4 md:hidden">
        {RECORDS.map((r) => (
          <div key={r.id} className="neo-extruded bg-surface rounded-2xl p-5">
            <div className="mb-3 flex items-start justify-between gap-3">
              <span className="font-mono text-primary text-sm">{r.id}</span>
              <span
                className={cn(
                  'font-label inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-bold',
                  STATUS_STYLES[r.status],
                )}
              >
                {r.status}
              </span>
            </div>
            <p className="font-body text-body-md text-on-surface font-bold">{r.diagnosis}</p>
            <div className="text-on-surface-variant mt-2 flex items-center gap-2">
              <Icon name="smart_toy" className="text-secondary text-base" />
              <span className="font-body text-body-sm">{r.agent}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Desktop: table */}
      <div className="neo-extruded bg-surface hidden overflow-hidden rounded-2xl p-1 md:block">
        <div className="w-full overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="bg-surface-container-low text-on-surface-variant font-label text-label-caps">
                <th className="rounded-tl-xl p-4 font-semibold">Patient ID</th>
                <th className="p-4 font-semibold">Last Diagnosis</th>
                <th className="p-4 font-semibold">Assigned AI Agent</th>
                <th className="rounded-tr-xl p-4 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className="font-body text-body-sm">
              {RECORDS.map((r, i) => (
                <tr
                  key={r.id}
                  className={cn(
                    'hover:bg-surface-container-lowest transition-colors',
                    i < RECORDS.length - 1 && 'border-surface-variant/50 border-b',
                  )}
                >
                  <td className="font-mono text-primary p-4">{r.id}</td>
                  <td className="text-on-surface p-4">{r.diagnosis}</td>
                  <td className="p-4">
                    <span className="flex items-center gap-2">
                      <Icon name="smart_toy" className="text-secondary text-base" />
                      {r.agent}
                    </span>
                  </td>
                  <td className="p-4">
                    <span
                      className={cn(
                        'font-label inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-bold',
                        STATUS_STYLES[r.status],
                      )}
                    >
                      {r.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
