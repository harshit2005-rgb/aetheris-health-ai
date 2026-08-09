import { Search, Download, UserPlus } from 'lucide-react'
import PageHeader from '@/components/layout/PageHeader'
import { cn } from '@/lib/utils'

type Status = 'Outpatient' | 'Admitted' | 'Discharged' | 'Critical'

interface Patient {
  mrn: string
  name: string
  age: number
  gender: 'M' | 'F'
  phone: string
  doctor: string
  department: string
  status: Status
}

const PATIENTS: Patient[] = [
  { mrn: 'PT-8291-A', name: 'Ravi Menon', age: 54, gender: 'M', phone: '+91 98847 21908', doctor: 'Dr. A. Chen', department: 'Cardiology', status: 'Admitted' },
  { mrn: 'PT-4022-C', name: 'Aisha Khan', age: 32, gender: 'F', phone: '+91 90031 55420', doctor: 'Dr. S. Rao', department: 'Pulmonology', status: 'Outpatient' },
  { mrn: 'PT-9188-B', name: 'Thomas George', age: 61, gender: 'M', phone: '+91 99456 12277', doctor: 'Dr. L. Iyer', department: 'Endocrinology', status: 'Critical' },
  { mrn: 'PT-1104-D', name: 'Meera Nair', age: 45, gender: 'F', phone: '+91 98120 66431', doctor: 'Dr. P. Verma', department: 'Surgery', status: 'Discharged' },
  { mrn: 'PT-6357-F', name: 'David Fernandes', age: 58, gender: 'M', phone: '+91 90876 33019', doctor: 'Dr. A. Chen', department: 'Cardiology', status: 'Outpatient' },
  { mrn: 'PT-2048-E', name: 'Sana Sheikh', age: 27, gender: 'F', phone: '+91 97411 20885', doctor: 'Dr. N. Bose', department: 'Neurology', status: 'Outpatient' },
  { mrn: 'PT-7791-G', name: 'Karan Malhotra', age: 39, gender: 'M', phone: '+91 98330 77164', doctor: 'Dr. S. Rao', department: 'Pulmonology', status: 'Admitted' },
]

const STATUS_STYLES: Record<Status, string> = {
  Outpatient: 'bg-secondary-container/20 text-on-secondary-container',
  Admitted: 'bg-tertiary-container/25 text-tertiary',
  Critical: 'bg-error-container/50 text-on-error-container',
  Discharged: 'bg-surface-container-highest text-on-surface-variant',
}

function StatusBadge({ status }: { status: Status }) {
  return (
    <span
      className={cn(
        'font-label inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-bold',
        STATUS_STYLES[status],
      )}
    >
      {status}
    </span>
  )
}

export default function PatientsPage() {
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Patients"
        subtitle="Patient registry, admissions and AI-assisted summaries."
        actions={
          <>
            <div className="relative">
              <Search className="text-outline pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search MRN, name, phone..."
                className="neo-pressed bg-surface/60 font-body text-body-sm placeholder:text-outline-variant focus:ring-secondary w-full rounded-full py-2.5 pr-4 pl-9 outline-none focus:ring-2 sm:w-64"
              />
            </div>
            <button className="neo-extruded bg-surface text-primary font-body text-body-sm hover:text-secondary flex items-center gap-2 rounded-full px-5 py-2.5 transition-colors active:scale-95">
              <Download className="size-4" /> Export
            </button>
            <button className="shadow-neo-base bg-primary text-on-primary font-label text-label-caps flex items-center gap-2 rounded-full px-5 py-2.5 font-bold transition-transform active:scale-95">
              <UserPlus className="size-4" /> Register Patient
            </button>
          </>
        }
      />

      {/* Mobile: cards */}
      <div className="space-y-4 md:hidden">
        {PATIENTS.map((p) => (
          <div key={p.mrn} className="neo-extruded bg-surface rounded-2xl p-5">
            <div className="mb-2 flex items-start justify-between gap-3">
              <div>
                <p className="font-body text-body-md text-primary font-bold">{p.name}</p>
                <p className="font-mono text-outline text-xs">{p.mrn}</p>
              </div>
              <StatusBadge status={p.status} />
            </div>
            <div className="font-body text-body-sm text-on-surface-variant grid grid-cols-2 gap-x-4 gap-y-1">
              <span>{p.age} · {p.gender === 'M' ? 'Male' : 'Female'}</span>
              <span>{p.department}</span>
              <span className="col-span-2">{p.doctor}</span>
              <span className="col-span-2">{p.phone}</span>
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
                <th className="rounded-tl-xl p-4 font-semibold">MRN</th>
                <th className="p-4 font-semibold">Name</th>
                <th className="p-4 font-semibold">Age / Sex</th>
                <th className="p-4 font-semibold">Phone</th>
                <th className="p-4 font-semibold">Doctor</th>
                <th className="p-4 font-semibold">Department</th>
                <th className="rounded-tr-xl p-4 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className="font-body text-body-sm">
              {PATIENTS.map((p, i) => (
                <tr
                  key={p.mrn}
                  className={cn(
                    'hover:bg-surface-container-lowest cursor-pointer transition-colors',
                    i < PATIENTS.length - 1 && 'border-surface-variant/50 border-b',
                  )}
                >
                  <td className="font-mono text-primary p-4">{p.mrn}</td>
                  <td className="text-on-surface p-4 font-semibold">{p.name}</td>
                  <td className="text-on-surface-variant p-4">
                    {p.age} · {p.gender}
                  </td>
                  <td className="text-on-surface-variant p-4">{p.phone}</td>
                  <td className="text-on-surface p-4">{p.doctor}</td>
                  <td className="text-on-surface-variant p-4">{p.department}</td>
                  <td className="p-4">
                    <StatusBadge status={p.status} />
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
