import { Database, FileClock, Hospital, Settings as SettingsIcon } from 'lucide-react'
import PageHeader from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/empty-state'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { usePermissions } from '@/hooks/usePermissions'
import { HospitalSettingsTab } from './HospitalSettingsTab'
import { WorkingHoursCard } from './WorkingHoursCard'
import { AuditLogTab } from './AuditLogTab'
import { DataImportCard } from './DataImportCard'

/**
 * Settings shell (module 14 §12, module 12 §12).
 *
 * Tabs are permission-driven: the Hospital tab needs `settings.read` and the
 * Audit tab `audit.read`, so a caller who somehow reaches `/settings` without
 * them sees an explanation rather than a dead screen. The route itself is
 * already gated on `settings.read` (router.tsx).
 */
export default function SettingsPage() {
  const { can } = usePermissions()
  const showHospital = can('settings.read')
  const showAudit = can('audit.read')
  // Data tab: import (docs/modules/17-data-import-export.md §12). Admins only.
  const showData = showHospital && can('data.import')

  return (
    <div className="w-full">
      <PageHeader
        title="Settings"
        subtitle="Hospital configuration and the audit log."
      />

      {!showHospital && !showAudit ? (
        <EmptyState
          icon={SettingsIcon}
          title="No access to settings"
          description="Your permission set does not include hospital settings or the audit trail."
        />
      ) : showAudit && !showHospital ? (
        // Reached only via a direct URL — show the one tab they may use.
        <AuditLogTab />
      ) : (
        <Tabs defaultValue="hospital">
          <TabsList>
            {showHospital && (
              <TabsTrigger value="hospital">
                <Hospital className="size-4" /> Hospital
              </TabsTrigger>
            )}
            {showData && (
              <TabsTrigger value="data">
                <Database className="size-4" /> Data
              </TabsTrigger>
            )}
            {showAudit && (
              <TabsTrigger value="audit">
                <FileClock className="size-4" /> Audit log
              </TabsTrigger>
            )}
          </TabsList>

          {showHospital && (
            <TabsContent value="hospital" className="space-y-6">
              <HospitalSettingsTab />
              <WorkingHoursCard />
            </TabsContent>
          )}
          {showData && (
            <TabsContent value="data" className="space-y-6">
              <DataImportCard />
            </TabsContent>
          )}
          {showAudit && (
            <TabsContent value="audit">
              <AuditLogTab />
            </TabsContent>
          )}
        </Tabs>
      )}
    </div>
  )
}
