import { Receipt } from 'lucide-react'
import ScaffoldPage from '@/components/layout/ScaffoldPage'

export default function BillingPage() {
  return (
    <ScaffoldPage
      title="Billing"
      subtitle="Invoices, payments, refunds and revenue."
      icon={Receipt}
      specRef="Spec Part 7"
      planned={[
        'Billing dashboard & KPIs',
        'Invoice list & details',
        'Create invoice',
        'Payment collection (cash, card, UPI, bank)',
        'Discounts & refunds',
        'Revenue reports',
        'AI billing insights',
      ]}
    />
  )
}
