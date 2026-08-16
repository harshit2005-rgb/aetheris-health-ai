import { BarChart3 } from 'lucide-react'
import ScaffoldPage from '@/components/layout/ScaffoldPage'

export default function ReportsPage() {
  return (
    <ScaffoldPage
      title="Reports"
      subtitle="Operational, financial and clinical analytics."
      icon={BarChart3}
      specRef="Spec Part 8"
      planned={[
        'Executive dashboard',
        'Patient & doctor reports',
        'Appointment & revenue reports',
        'Interactive charts',
        'Filters by date, department, doctor',
        'Export center (PDF, Excel, CSV)',
        'AI-generated insights',
      ]}
    />
  )
}
