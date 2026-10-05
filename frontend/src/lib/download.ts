/**
 * The filename a `Content-Disposition` header names, or undefined if it names
 * none. Reads the plain `filename="…"` form and the RFC 5987 `filename*=`
 * form, preferring the latter as the header's own rules do. Any directory part
 * is dropped: the name is only ever used as a suggestion for a local save.
 */
export function filenameFromContentDisposition(header: unknown): string | undefined {
  if (typeof header !== 'string') return undefined
  let name: string | undefined
  const extended = /filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)/.exec(header)
  if (extended) {
    try {
      name = decodeURIComponent(extended[1].trim())
    } catch {
      name = undefined
    }
  }
  if (!name) {
    const plain = /filename\s*=\s*(?:"([^"]*)"|([^;]+))/.exec(header)
    name = (plain?.[1] ?? plain?.[2])?.trim()
  }
  const base = name?.split(/[\\/]/).pop()
  return base || undefined
}

/** Hand a file the app already holds to the browser's download manager. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
