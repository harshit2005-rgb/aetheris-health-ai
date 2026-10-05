import { describe, it, expect } from 'vitest'
import { filenameFromContentDisposition } from './download'

describe('filenameFromContentDisposition', () => {
  it('reads the quoted filename the API sends', () => {
    expect(filenameFromContentDisposition('attachment; filename="audit-logs-20261005-101500.csv"')).toBe(
      'audit-logs-20261005-101500.csv',
    )
  })

  it('reads an unquoted filename', () => {
    expect(filenameFromContentDisposition('attachment; filename=export.json')).toBe('export.json')
  })

  it('prefers the RFC 5987 form and decodes it', () => {
    expect(
      filenameFromContentDisposition("attachment; filename=\"fallback.csv\"; filename*=UTF-8''r%C3%A9sum%C3%A9.csv"),
    ).toBe('résumé.csv')
  })

  it('drops any directory part', () => {
    expect(filenameFromContentDisposition('attachment; filename="../../etc/passwd"')).toBe('passwd')
    expect(filenameFromContentDisposition('attachment; filename="C:\\\\temp\\\\a.csv"')).toBe('a.csv')
  })

  it('is undefined when no usable name is given', () => {
    expect(filenameFromContentDisposition('attachment')).toBeUndefined()
    expect(filenameFromContentDisposition('attachment; filename=""')).toBeUndefined()
    expect(filenameFromContentDisposition(undefined)).toBeUndefined()
    expect(filenameFromContentDisposition(42)).toBeUndefined()
  })
})
