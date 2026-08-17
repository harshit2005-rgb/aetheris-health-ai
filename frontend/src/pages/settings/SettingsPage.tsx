import { Settings } from 'lucide-react'
import ScaffoldPage from '@/components/layout/ScaffoldPage'

export default function SettingsPage() {
  return (
    <ScaffoldPage
      title="Settings"
      subtitle="Hospital configuration, users, roles and security."
      icon={Settings}
      specRef="Spec Part 10"
      planned={[
        'Hospital profile',
        'User management',
        'Roles & permissions',
        'Departments',
        'Notification settings',
        'AI configuration',
        'Branding',
        'Security & audit logs',
      ]}
    />
  )
}
