import { Download, UserPlus, Users } from 'lucide-react'
import PageHeader from '@/components/layout/PageHeader'
import { DataTable } from '@/components/ui/data-table'
import { EmptyState } from '@/components/ui/empty-state'
import { Button } from '@/components/ui/button'
import { Alert } from '@/components/ui/alert'
import { usePatients } from '@/api/patients'
import { patientColumns } from './columns'
import { RegisterPatientDialog } from './RegisterPatientDialog'

export default function PatientsPage() {
  const { data, isLoading, isError } = usePatients()
  const patients = data?.items ?? []

  const registerButton = (
    <Button className="rounded-full">
      <UserPlus className="size-4" /> Register Patient
    </Button>
  )

  return (
    <div className="w-full">
      <PageHeader
        title="Patients"
        subtitle="Patient registry, admissions and AI-assisted summaries."
        actions={
          <>
            <Button variant="outline" className="rounded-full">
              <Download className="size-4" /> Export
            </Button>
            <RegisterPatientDialog trigger={registerButton} />
          </>
        }
      />

      {isError ? (
        <Alert variant="error" title="Couldn't load patients">
          Something went wrong fetching the patient registry. Please retry.
        </Alert>
      ) : (
        <DataTable
          columns={patientColumns}
          data={patients}
          isLoading={isLoading}
          searchable
          searchPlaceholder="Search MRN, name, phone…"
          emptyState={
            <EmptyState
              icon={Users}
              title="No patients yet"
              description="Register your first patient to start building the registry."
              action={<RegisterPatientDialog trigger={registerButton} />}
            />
          }
        />
      )}
    </div>
  )
}
