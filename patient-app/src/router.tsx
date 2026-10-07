import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom'
import { FullScreenLoader } from '@/components/FullScreenLoader'
import { RouteError } from '@/components/RouteError'
import { AuthLayout } from '@/layouts/AuthLayout'
import { PatientLayout } from '@/layouts/PatientLayout'
import { RedirectIfSignedIn } from '@/routes/RedirectIfSignedIn'
import { RequirePatientSession } from '@/routes/RequirePatientSession'

/**
 * The ONLY route table of the Patient App (docs/modules/15-patient-app.md
 * §25.5). It shares nothing with the Hospital app's router: no staff route is
 * reachable from here. Pages are lazy-loaded.
 */
export const routes: RouteObject[] = [
  {
    hydrateFallbackElement: <FullScreenLoader label="Loading…" />,
    errorElement: <RouteError />,
    children: [
      {
        element: <RedirectIfSignedIn />,
        children: [
          {
            element: <AuthLayout />,
            children: [
              {
                path: '/login',
                lazy: async () => ({ Component: (await import('@/pages/auth/LoginPage')).LoginPage }),
              },
              {
                path: '/verify-otp',
                lazy: async () => ({
                  Component: (await import('@/pages/auth/VerifyOtpPage')).VerifyOtpPage,
                }),
              },
            ],
          },
        ],
      },
      {
        element: <RequirePatientSession />,
        children: [
          {
            element: <PatientLayout />,
            children: [
              {
                path: '/',
                lazy: async () => ({ Component: (await import('@/pages/home/HomePage')).HomePage }),
              },
              {
                path: '/hospitals',
                lazy: async () => ({
                  Component: (await import('@/pages/hospitals/HospitalsPage')).HospitalsPage,
                }),
              },
              {
                path: '/hospitals/:hospitalRef',
                lazy: async () => ({
                  Component: (await import('@/pages/hospitals/HospitalDetailPage')).HospitalDetailPage,
                }),
              },
              {
                // The entry point of doctor discovery; it lists no doctors yet.
                path: '/hospitals/:hospitalRef/doctors',
                lazy: async () => ({
                  Component: (await import('@/pages/doctors/HospitalDoctorsPage')).HospitalDoctorsPage,
                }),
              },
              {
                path: '/link-patient',
                lazy: async () => ({
                  Component: (await import('@/pages/hospitals/LinkPatientPage')).LinkPatientPage,
                }),
              },
            ],
          },
        ],
      },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]

export const createAppRouter = () => createBrowserRouter(routes)

export type AppRouter = ReturnType<typeof createBrowserRouter>
