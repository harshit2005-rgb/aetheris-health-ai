import { ThemeProvider } from 'next-themes'
import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import { Toaster } from '@/components/ui/sonner'
import { SessionRestorer } from '@/components/auth/SessionRestorer'
import { queryClient } from '@/lib/query-client'
import { router } from '@/router'

export default function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <QueryClientProvider client={queryClient}>
        <SessionRestorer>
          <RouterProvider router={router} />
        </SessionRestorer>
        <Toaster richColors position="top-right" />
      </QueryClientProvider>
    </ThemeProvider>
  )
}
