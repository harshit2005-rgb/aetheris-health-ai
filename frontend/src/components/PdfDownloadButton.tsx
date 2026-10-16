import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { Download, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ApiError } from '@/api/types'
import { saveBlob } from '@/lib/download'

export interface PdfFile {
  blob: Blob
  filename: string
}

const DOWNLOAD_FAILED = "Couldn't download the PDF. Try again."

function downloadErrorMessage(err: unknown, forbidden: string): string {
  if (!(err instanceof ApiError)) return DOWNLOAD_FAILED
  if (err.status === 403) return forbidden
  // A business rule, in the server's own words (e.g. "not released yet").
  if (err.status === 400) return err.message
  return DOWNLOAD_FAILED
}

interface PdfDownloadButtonProps {
  /** Fetches the PDF; rejects with an `ApiError` on refusal. */
  fetchFile: () => Promise<PdfFile>
  /** The button's label, e.g. "Download report". */
  label: string
  /** The toast shown on a 403. */
  forbiddenMessage: string
}

/**
 * Download a server-rendered PDF (a lab report, a prescription) and hand it to
 * the browser's download manager. One request at a time; the server's reason
 * is shown when it refuses.
 */
export function PdfDownloadButton({ fetchFile, label, forbiddenMessage }: PdfDownloadButtonProps) {
  const [pending, setPending] = useState(false)
  // `pending` disables the button only after a re-render; this also stops a
  // second request fired before then.
  const busy = useRef(false)

  async function run() {
    if (busy.current) return
    busy.current = true
    setPending(true)
    try {
      const file = await fetchFile()
      saveBlob(file.blob, file.filename)
      toast.success(`Downloaded ${file.filename}`)
    } catch (err) {
      toast.error(downloadErrorMessage(err, forbiddenMessage))
    } finally {
      busy.current = false
      setPending(false)
    }
  }

  return (
    <Button variant="outline" onClick={run} disabled={pending} aria-busy={pending}>
      {pending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Download className="size-4" aria-hidden />}
      {pending ? 'Preparing PDF…' : label}
    </Button>
  )
}
