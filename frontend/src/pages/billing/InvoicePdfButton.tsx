import { useRef } from 'react'
import { toast } from 'sonner'
import { Download, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useDownloadInvoicePdf, type Invoice } from '@/api/billing'
import { ApiError } from '@/api/types'
import { saveBlob } from '@/lib/download'

const DOWNLOAD_FAILED = "Couldn't download the PDF. Try again."

function downloadErrorMessage(err: unknown): string {
  if (!(err instanceof ApiError)) return DOWNLOAD_FAILED
  if (err.status === 403) return "You don't have permission to download invoice PDFs."
  // A draft, in the server's own words.
  if (err.status === 400) return err.message
  return DOWNLOAD_FAILED
}

/**
 * Download the invoice on screen as a PDF, line for line as shown, with its
 * payments and refunds (module spec §9, AC-5). Offered once the invoice is
 * issued — a draft has no PDF — and only to someone holding
 * `invoice.pdf.download`, which the server also requires.
 */
export function InvoicePdfButton({ invoice }: { invoice: Invoice }) {
  const download = useDownloadInvoicePdf()
  // `isPending` disables the button only after a re-render; this also stops a
  // second request fired before then.
  const busy = useRef(false)

  async function run() {
    if (busy.current) return
    busy.current = true
    try {
      const file = await download.mutateAsync({ id: invoice.id, invoiceNumber: invoice.invoice_number })
      saveBlob(file.blob, file.filename)
      toast.success(`Downloaded ${file.filename}`)
    } catch (err) {
      toast.error(downloadErrorMessage(err))
    } finally {
      busy.current = false
    }
  }

  return (
    <Button variant="outline" onClick={run} disabled={download.isPending} aria-busy={download.isPending}>
      {download.isPending ? (
        <Loader2 className="size-4 animate-spin" aria-hidden />
      ) : (
        <Download className="size-4" aria-hidden />
      )}
      {download.isPending ? 'Preparing PDF…' : 'Download PDF'}
    </Button>
  )
}
