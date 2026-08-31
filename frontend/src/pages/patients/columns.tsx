import type { ColumnDef } from '@tanstack/react-table'
import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { Gender, PatientStatus, PatientSummary } from '@/api/patients'

const STATUS_VARIANT: Record<PatientStatus, 'success' | 'neutral'> = {
  active: 'success',
  inactive: 'neutral',
}

const GENDER_LABEL: Record<Gender, string> = {
  male: 'Male',
  female: 'Female',
  other: 'Other',
  unspecified: 'Unspecified',
}

export const patientColumns: ColumnDef<PatientSummary>[] = [
  {
    accessorKey: 'mrn',
    header: 'MRN',
    cell: ({ row }) => <span className="font-mono text-primary">{row.original.mrn}</span>,
  },
  {
    accessorKey: 'full_name',
    header: 'Name',
    cell: ({ row }) => <span className="font-semibold">{row.original.full_name}</span>,
  },
  {
    id: 'ageGender',
    header: 'Age / Sex',
    accessorFn: (p) => `${p.age} · ${GENDER_LABEL[p.gender]}`,
    enableSorting: false,
  },
  {
    accessorKey: 'phone',
    header: 'Phone',
    cell: ({ row }) => row.original.phone ?? <span className="text-outline-variant">—</span>,
  },
  {
    accessorKey: 'status',
    header: 'Status',
    cell: ({ row }) => (
      <Badge variant={STATUS_VARIANT[row.original.status]} className="capitalize">
        {row.original.status}
      </Badge>
    ),
  },
  {
    id: 'actions',
    header: '',
    enableSorting: false,
    cell: ({ row }) => (
      <Link
        to={`/patients/${row.original.id}`}
        aria-label={`View ${row.original.full_name}`}
        className="text-outline hover:text-secondary inline-flex items-center gap-1 transition-colors"
      >
        View <ChevronRight className="size-4" />
      </Link>
    ),
  },
]
