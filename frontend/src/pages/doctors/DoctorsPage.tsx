import { Stethoscope } from 'lucide-react'
import ScaffoldPage from '@/components/layout/ScaffoldPage'

export default function DoctorsPage() {
  return (
    <ScaffoldPage
      title="Doctors"
      subtitle="Manage doctors, departments, schedules and availability."
      icon={Stethoscope}
      specRef="Spec Part 5"
      planned={[
        'Doctor directory with search & filters',
        'Add / edit doctor profiles',
        'Department management',
        'Weekly availability calendar',
        'Leave management workflow',
        'Consultation history',
        'AI workload insights',
      ]}
    />
  )
}
