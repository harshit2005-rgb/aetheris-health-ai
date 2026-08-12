import { createBrowserRouter } from 'react-router-dom'
import DashboardLayout from '@/layouts/DashboardLayout'
import { RequireAuth } from '@/components/auth/RequireAuth'
import { RequirePermission } from '@/components/auth/RequirePermission'
import LandingPage from '@/pages/LandingPage'
import LoginPage from '@/pages/LoginPage'
import ContactPage from '@/pages/ContactPage'
import LegalPage from '@/pages/LegalPage'
import { privacyDoc, termsDoc, hipaaDoc } from '@/content/legal'
import PricingPage from '@/pages/PricingPage'
import NotFoundPage from '@/pages/NotFoundPage'
import DashboardPage from '@/pages/DashboardPage'
import PatientsPage from '@/pages/patients/PatientsPage'
import DoctorsPage from '@/pages/doctors/DoctorsPage'
import AppointmentsPage from '@/pages/appointments/AppointmentsPage'
import BillingPage from '@/pages/billing/BillingPage'
import ReportsPage from '@/pages/reports/ReportsPage'
import SettingsPage from '@/pages/settings/SettingsPage'

export const router = createBrowserRouter([
  // Public marketing pages
  { path: '/', element: <LandingPage /> },
  { path: '/pricing', element: <PricingPage /> },
  { path: '/contact', element: <ContactPage /> },
  { path: '/privacy', element: <LegalPage doc={privacyDoc} /> },
  { path: '/terms', element: <LegalPage doc={termsDoc} /> },
  { path: '/hipaa', element: <LegalPage doc={hipaaDoc} /> },
  { path: '/login', element: <LoginPage /> },

  // Authenticated app — shared enterprise shell
  {
    element: (
      <RequireAuth>
        <DashboardLayout />
      </RequireAuth>
    ),
    children: [
      { path: '/dashboard', element: <DashboardPage /> },
      {
        path: '/patients',
        element: (
          <RequirePermission permission="patient.read">
            <PatientsPage />
          </RequirePermission>
        ),
      },
      {
        path: '/doctors',
        element: (
          <RequirePermission permission="doctor.read">
            <DoctorsPage />
          </RequirePermission>
        ),
      },
      {
        path: '/appointments',
        element: (
          <RequirePermission permission="appointment.read">
            <AppointmentsPage />
          </RequirePermission>
        ),
      },
      {
        path: '/billing',
        element: (
          <RequirePermission permission="billing.read">
            <BillingPage />
          </RequirePermission>
        ),
      },
      {
        path: '/reports',
        element: (
          <RequirePermission permission="report.read">
            <ReportsPage />
          </RequirePermission>
        ),
      },
      {
        path: '/settings',
        element: (
          <RequirePermission permission="settings.manage">
            <SettingsPage />
          </RequirePermission>
        ),
      },
    ],
  },

  { path: '*', element: <NotFoundPage /> },
])
