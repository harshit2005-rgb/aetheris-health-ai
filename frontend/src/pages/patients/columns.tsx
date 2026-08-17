import type { ColumnDef } from '@tanstack/react-table'
import { Badge } from '@/components/ui/badge'
import type { Patient, PatientStatus } from '@/api/patients'

const STATUS_VARIANT: Record<PatientStatus, 'accent' | 'primary' | 'critical' | 'neutral'> = {
  Outpatient: 'accent',
  Admitted: 'primary',
  Critical: 'critical',
  Discharged: 'neutral',
}

export const patientColumns: ColumnDef<Patient>[] = [
  {
    accessorKey: 'mrn',
    header: 'MRN',
    cell: ({ row }) => <span className="font-mono text-primary">{row.original.mrn}</span>,
  },
  {
    accessorKey: 'name',
    header: 'Name',
    cell: ({ row }) => <span className="font-semibold">{row.original.name}</span>,
  },
  {
    id: 'ageSex',
    header: 'Age / Sex',
    accessorFn: (p) => `${p.age} · ${p.gender}`,
    enableSorting: false,
  },
  { accessorKey: 'phone', header: 'Phone' },
  { accessorKey: 'doctor', header: 'Doctor' },
  { accessorKey: 'department', header: 'Department' },
  {
    accessorKey: 'status',
    header: 'Status',
    cell: ({ row }) => (
      <Badge variant={STATUS_VARIANT[row.original.status]}>{row.original.status}</Badge>
    ),
  },
]
