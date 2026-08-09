import { createBrowserRouter } from 'react-router-dom'
import AppLayout from '@/components/layout/AppLayout'
import { RequireAuth } from '@/components/auth/RequireAuth'
import LandingPage from '@/pages/LandingPage'
import LoginPage from '@/pages/LoginPage'
import SignupPage from '@/pages/SignupPage'
import HowItWorksPage from '@/pages/HowItWorksPage'
import TechnologyPage from '@/pages/TechnologyPage'
import ContactPage from '@/pages/ContactPage'
import LegalPage from '@/pages/LegalPage'
import { privacyDoc, termsDoc, hipaaDoc } from '@/content/legal'
import DashboardPage from '@/pages/DashboardPage'
import DiagnosticsPage from '@/pages/DiagnosticsPage'
import RecordsPage from '@/pages/RecordsPage'
import PricingPage from '@/pages/PricingPage'
import NotFoundPage from '@/pages/NotFoundPage'

export const router = createBrowserRouter([
  // Public pages
  { path: '/', element: <LandingPage /> },
  { path: '/how-it-works', element: <HowItWorksPage /> },
  { path: '/technology', element: <TechnologyPage /> },
  { path: '/pricing', element: <PricingPage /> },
  { path: '/contact', element: <ContactPage /> },
  { path: '/privacy', element: <LegalPage doc={privacyDoc} /> },
  { path: '/terms', element: <LegalPage doc={termsDoc} /> },
  { path: '/hipaa', element: <LegalPage doc={hipaaDoc} /> },
  { path: '/login', element: <LoginPage /> },
  { path: '/signup', element: <SignupPage /> },

  // App screens — require auth, share the sidebar/app chrome
  {
    element: (
      <RequireAuth>
        <AppLayout />
      </RequireAuth>
    ),
    children: [
      { path: '/dashboard', element: <DashboardPage /> },
      { path: '/diagnostics', element: <DiagnosticsPage /> },
      { path: '/records', element: <RecordsPage /> },
    ],
  },

  { path: '*', element: <NotFoundPage /> },
])
