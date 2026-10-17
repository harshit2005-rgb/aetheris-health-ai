import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, FlaskConical, Pill, Stethoscope } from 'lucide-react'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useAppointment, type Appointment } from '@/api/appointments'
import { useVisitConsultation, type Consultation } from '@/api/consultations'
import { useLabOrders } from '@/api/lab'
import { usePrescriptions } from '@/api/pharmacy'
import { LabOrderStatusBadge } from '@/components/laboratory/LabBadges'
import { OrderLabTestsDialog } from '@/components/laboratory/OrderLabTestsDialog'
import { canOrderLabTestsFor } from '@/components/laboratory/labPresentation'
import { PrescriptionStatusBadge } from '@/components/pharmacy/PharmacyBadges'
import { PrescribeDialog } from '@/components/pharmacy/PrescribeDialog'
import { canPrescribeFor } from '@/components/pharmacy/pharmacyPresentation'
import { usePermissions } from '@/hooks/usePermissions'
import { formatDateTime } from '@/lib/format'
import { NoteEditor } from './NoteEditor'
import { NoteView } from './NoteView'
import { VitalsCard } from './VitalsCard'

/** Visits a note can be written for (docs/modules/16-consultation.md §4 rule 2). */
const DOCUMENTABLE = new Set(['checked_in', 'in_progress', 'completed'])

function VisitOrders({ appointment }: { appointment: Appointment }) {
  const { can } = usePermissions()
  const canReadRx = can('pharmacy.prescription.read')
  const canReadLab = can('lab.order.read')
  const prescriptions = usePrescriptions({ appointment_id: appointment.id, page_size: 50 }, { enabled: canReadRx })
  const labOrders = useLabOrders({ appointment_id: appointment.id, page_size: 50 }, { enabled: canReadLab })
  const canPrescribe =
    canPrescribeFor(appointment.status) && can('pharmacy.prescription.create') && can('pharmacy.medicine.read')
  const canOrder = canOrderLabTestsFor(appointment.status) && can('lab.order.create') && can('lab.test.read')

  return (
    <aside className="space-y-6" aria-label="This visit's orders">
      {canReadRx && (
        <section className="neo-extruded bg-surface rounded-2xl p-6" aria-labelledby="rx-title">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 id="rx-title" className="font-display text-title-md text-primary flex items-center gap-2 font-bold">
              <Pill className="size-5" aria-hidden /> Prescriptions
            </h2>
            {canPrescribe && (
              <PrescribeDialog
                visit={appointment}
                trigger={
                  <Button variant="outline" size="sm">
                    Write prescription
                  </Button>
                }
              />
            )}
          </div>
          {prescriptions.isLoading ? (
            <Skeleton className="h-16 w-full" />
          ) : prescriptions.data?.items.length ? (
            <ul className="space-y-2">
              {prescriptions.data.items.map((rx) => (
                <li key={rx.id} className="bg-surface-container-low rounded-xl p-3">
                  <div className="flex items-center justify-between gap-2">
                    <Link to={`/pharmacy/prescriptions/${rx.id}`} className="text-secondary text-sm hover:underline">
                      {formatDateTime(rx.prescribed_at)}
                    </Link>
                    <PrescriptionStatusBadge status={rx.status} />
                  </div>
                  <p className="font-body text-on-surface-variant mt-1 text-sm">
                    {rx.items.map((i) => i.medicine_name).join(', ')}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="font-body text-on-surface-variant text-sm">No prescription yet.</p>
          )}
        </section>
      )}

      {canReadLab && (
        <section className="neo-extruded bg-surface rounded-2xl p-6" aria-labelledby="lab-title">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 id="lab-title" className="font-display text-title-md text-primary flex items-center gap-2 font-bold">
              <FlaskConical className="size-5" aria-hidden /> Lab tests
            </h2>
            {canOrder && (
              <OrderLabTestsDialog
                visit={appointment}
                trigger={
                  <Button variant="outline" size="sm">
                    Order lab tests
                  </Button>
                }
              />
            )}
          </div>
          {labOrders.isLoading ? (
            <Skeleton className="h-16 w-full" />
          ) : labOrders.data?.items.length ? (
            <ul className="space-y-2">
              {labOrders.data.items.map((order) => (
                <li key={order.id} className="bg-surface-container-low rounded-xl p-3">
                  <div className="flex items-center justify-between gap-2">
                    <Link to={`/laboratory/orders/${order.id}`} className="text-secondary text-sm hover:underline">
                      {formatDateTime(order.ordered_at)}
                    </Link>
                    <LabOrderStatusBadge status={order.status} />
                  </div>
                  <p className="font-body text-on-surface-variant mt-1 text-sm">
                    {order.items.map((i) => i.test_name).join(', ')}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="font-body text-on-surface-variant text-sm">No tests ordered yet.</p>
          )}
        </section>
      )}
    </aside>
  )
}

function NoteArea({ appointment, note }: { appointment: Appointment; note: Consultation | null }) {
  const { can } = usePermissions()
  if (note && (note.status === 'finalized' || !note.is_own)) {
    return <NoteView appointmentId={appointment.id} note={note} />
  }
  if (can('consultation.write') && DOCUMENTABLE.has(appointment.status)) {
    // Before the note exists the screen cannot tell whose visit this is; the
    // server refuses anyone but the visit's doctor, and the editor says so.
    return <NoteEditor key={note?.id ?? 'new'} appointmentId={appointment.id} note={note} />
  }
  return (
    <section className="neo-extruded bg-surface rounded-2xl p-6">
      <p className="font-body text-on-surface-variant text-sm">
        {DOCUMENTABLE.has(appointment.status)
          ? 'The doctor has not started the consultation note yet.'
          : 'A consultation note is written once the patient is checked in.'}
      </p>
    </section>
  )
}

/**
 * The doctor's screen for one visit (docs/modules/16-consultation.md §12):
 * vitals, the clinical note, and the visit's prescriptions and lab tests.
 */
export default function ConsultationPage() {
  const { appointmentId = '' } = useParams()
  const { can } = usePermissions()
  const appointment = useAppointment(appointmentId)
  const note = useVisitConsultation(appointmentId)

  const backLink = (
    <Link to="/appointments" className="text-secondary inline-flex items-center gap-1 text-sm hover:underline">
      <ArrowLeft className="size-4" aria-hidden /> Appointments
    </Link>
  )

  if (appointment.isLoading || note.isLoading) {
    return (
      <div className="w-full space-y-6" aria-busy>
        {backLink}
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }
  if (appointment.isError || !appointment.data || note.isError) {
    return (
      <div className="w-full space-y-6">
        {backLink}
        <Alert variant="error" title="This consultation couldn't be loaded">
          Check the link, or go back to the appointments list and open the visit again.
        </Alert>
      </div>
    )
  }

  const visit = appointment.data
  const consultation = note.data ?? null
  return (
    <div className="w-full space-y-6">
      {backLink}
      <header className="glassmorphism shadow-glass-panel flex flex-wrap items-center justify-between gap-4 rounded-2xl p-6">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-display text-headline-md text-primary flex items-center gap-2 font-bold">
              <Stethoscope className="size-6" aria-hidden /> Consultation
            </h1>
            {consultation && (
              <Badge variant={consultation.status === 'finalized' ? 'success' : 'warning'}>
                {consultation.status === 'finalized' ? 'Finalized' : 'Draft'}
              </Badge>
            )}
          </div>
          <p className="font-body text-body-md text-on-surface-variant mt-1">
            {can('patient.read') ? (
              <Link to={`/patients/${visit.patient_id}`} className="text-secondary hover:underline">
                {visit.patient_name}
              </Link>
            ) : (
              visit.patient_name
            )}
            {consultation && <span className="text-outline font-mono text-sm"> · {consultation.patient_mrn}</span>}
            <span> · {visit.doctor_name}</span>
            <span> · {formatDateTime(visit.scheduled_start)}</span>
          </p>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          <VitalsCard
            appointmentId={visit.id}
            note={consultation}
            canRecord={can('consultation.vitals.record') && DOCUMENTABLE.has(visit.status)}
          />
          <NoteArea appointment={visit} note={consultation} />
        </div>
        <VisitOrders appointment={visit} />
      </div>
    </div>
  )
}
