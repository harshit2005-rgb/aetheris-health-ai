import { lazy, Suspense } from 'react'
import { Navigate, createBrowserRouter, Outlet } from 'react-router-dom'
import { RequireAuth } from '@/components/auth/RequireAuth'
import { RequirePermission } from '@/components/auth/RequirePermission'
import { RouteFallback } from '@/components/layout/RouteFallback'
import { privacyDoc, termsDoc, securityDoc } from '@/content/legal'

// Route-level code splitting: each page (and its heavy deps like Recharts)
// lands in its own chunk, loaded on demand behind the Suspense boundary below.
const DashboardLayout = lazy(() => import('@/layouts/DashboardLayout'))
const LandingPage = lazy(() => import('@/pages/LandingPage'))
const LoginPage = lazy(() => import('@/pages/LoginPage'))
const ForgotPasswordPage = lazy(() => import('@/pages/auth/ForgotPasswordPage'))
const ResetPasswordPage = lazy(() => import('@/pages/auth/ResetPasswordPage'))
const ContactPage = lazy(() => import('@/pages/ContactPage'))
const LegalPage = lazy(() => import('@/pages/LegalPage'))
const PricingPage = lazy(() => import('@/pages/PricingPage'))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const PatientsPage = lazy(() => import('@/pages/patients/PatientsPage'))
const PatientDetailPage = lazy(() => import('@/pages/patients/PatientDetailPage'))
const DoctorsPage = lazy(() => import('@/pages/doctors/DoctorsPage'))
const DoctorDetailPage = lazy(() => import('@/pages/doctors/DoctorDetailPage'))
const AppointmentsPage = lazy(() => import('@/pages/appointments/AppointmentsPage'))
const BillingPage = lazy(() => import('@/pages/billing/BillingPage'))
const InvoiceDetailPage = lazy(() => import('@/pages/billing/InvoiceDetailPage'))
const ReportsPage = lazy(() => import('@/pages/reports/ReportsPage'))
const LabOrdersPage = lazy(() => import('@/pages/laboratory/LabOrdersPage'))
const LabOrderDetailPage = lazy(() => import('@/pages/laboratory/LabOrderDetailPage'))
const LabCatalogPage = lazy(() => import('@/pages/laboratory/LabCatalogPage'))
const PharmacyIndexPage = lazy(() => import('@/pages/pharmacy/PharmacyIndexPage'))
const PrescriptionsPage = lazy(() => import('@/pages/pharmacy/PrescriptionsPage'))
const PrescriptionDetailPage = lazy(() => import('@/pages/pharmacy/PrescriptionDetailPage'))
const MedicinesPage = lazy(() => import('@/pages/pharmacy/MedicinesPage'))
const MedicineStockPage = lazy(() => import('@/pages/pharmacy/MedicineStockPage'))
const PurchaseOrdersPage = lazy(() => import('@/pages/pharmacy/PurchaseOrdersPage'))
const PurchaseOrderDetailPage = lazy(() => import('@/pages/pharmacy/PurchaseOrderDetailPage'))
const VendorsPage = lazy(() => import('@/pages/pharmacy/VendorsPage'))
const UsersPage = lazy(() => import('@/pages/users/UsersPage'))
const SettingsPage = lazy(() => import('@/pages/settings/SettingsPage'))
const ProfilePage = lazy(() => import('@/pages/settings/ProfilePage'))

export const router = createBrowserRouter([
  {
    // Single Suspense boundary for every lazily-loaded route.
    element: (
      <Suspense fallback={<RouteFallback />}>
        <Outlet />
      </Suspense>
    ),
    children: [
      // Public marketing pages
      { path: '/', element: <LandingPage /> },
      { path: '/pricing', element: <PricingPage /> },
      { path: '/contact', element: <ContactPage /> },
      { path: '/privacy', element: <LegalPage doc={privacyDoc} /> },
      { path: '/terms', element: <LegalPage doc={termsDoc} /> },
      { path: '/security', element: <LegalPage doc={securityDoc} /> },
      // The page's old address, kept so existing links still land somewhere true.
      { path: '/hipaa', element: <Navigate to="/security" replace /> },

      // Auth pages (public)
      { path: '/login', element: <LoginPage /> },
      { path: '/forgot-password', element: <ForgotPasswordPage /> },
      { path: '/reset-password', element: <ResetPasswordPage /> },

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
            path: '/patients/:patientId',
            element: (
              <RequirePermission permission="patient.read">
                <PatientDetailPage />
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
            path: '/doctors/:doctorId',
            element: (
              <RequirePermission permission="doctor.read">
                <DoctorDetailPage />
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
            // Either invoice read code opens Billing; the server narrows a
            // doctor's list to their own visits (docs/18-API_CONTRACTS.md §6.11).
            path: '/billing',
            element: (
              <RequirePermission group="invoice.read">
                <BillingPage />
              </RequirePermission>
            ),
          },
          {
            path: '/billing/:invoiceId',
            element: (
              <RequirePermission group="invoice.read">
                <InvoiceDetailPage />
              </RequirePermission>
            ),
          },
          {
            path: '/laboratory',
            element: (
              <RequirePermission permission="lab.order.read">
                <LabOrdersPage />
              </RequirePermission>
            ),
          },
          {
            path: '/laboratory/orders/:orderId',
            element: (
              <RequirePermission permission="lab.order.read">
                <LabOrderDetailPage />
              </RequirePermission>
            ),
          },
          {
            // Reading the catalog is its own code: a nurse can read orders
            // but not the catalog (docs/18-API_CONTRACTS.md §8.2).
            path: '/laboratory/catalog',
            element: (
              <RequirePermission permission="lab.test.read">
                <LabCatalogPage />
              </RequirePermission>
            ),
          },
          {
            // Any pharmacy read code opens the module; the index sends each user to
            // the first screen their permissions cover (docs/18-API_CONTRACTS.md §9.1).
            path: '/pharmacy',
            element: (
              <RequirePermission group="pharmacy.medicine.read">
                <PharmacyIndexPage />
              </RequirePermission>
            ),
          },
          {
            path: '/pharmacy/prescriptions',
            element: (
              <RequirePermission permission="pharmacy.prescription.read">
                <PrescriptionsPage />
              </RequirePermission>
            ),
          },
          {
            path: '/pharmacy/prescriptions/:prescriptionId',
            element: (
              <RequirePermission permission="pharmacy.prescription.read">
                <PrescriptionDetailPage />
              </RequirePermission>
            ),
          },
          {
            path: '/pharmacy/medicines',
            element: (
              <RequirePermission permission="pharmacy.medicine.read">
                <MedicinesPage />
              </RequirePermission>
            ),
          },
          {
            // Stock is its own code: a doctor reads the catalog but not the batches.
            path: '/pharmacy/medicines/:medicineId',
            element: (
              <RequirePermission permission="pharmacy.batch.read">
                <MedicineStockPage />
              </RequirePermission>
            ),
          },
          {
            path: '/pharmacy/purchase-orders',
            element: (
              <RequirePermission permission="pharmacy.po.read">
                <PurchaseOrdersPage />
              </RequirePermission>
            ),
          },
          {
            path: '/pharmacy/purchase-orders/:orderId',
            element: (
              <RequirePermission permission="pharmacy.po.read">
                <PurchaseOrderDetailPage />
              </RequirePermission>
            ),
          },
          {
            path: '/pharmacy/vendors',
            element: (
              <RequirePermission permission="pharmacy.vendor.read">
                <VendorsPage />
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
            path: '/users',
            element: (
              <RequirePermission permission="user.read">
                <UsersPage />
              </RequirePermission>
            ),
          },
          {
            path: '/settings',
            element: (
              <RequirePermission permission="settings.read">
                <SettingsPage />
              </RequirePermission>
            ),
          },
          {
            // Own profile (module spec 02 §12). Deliberately NOT behind
            // RequirePermission: it acts only on the caller's own account, so
            // every authenticated user reaches it — including one with no
            // roles at all.
            path: '/settings/profile',
            element: <ProfilePage />,
          },
        ],
      },

      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
