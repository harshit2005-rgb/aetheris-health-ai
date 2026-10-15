import { describe, expect, it } from 'vitest'
import { cn } from '@atheris/ui'

describe('cn', () => {
  it.each(['headline-xl', 'headline-lg', 'headline-md', 'title-lg', 'body-lg', 'body-md', 'body-sm', 'label-caps', 'label-mono'])(
    'keeps the type-scale size text-%s beside a text colour',
    (size) => {
      expect(cn(`text-${size}`, 'text-primary').split(' ')).toEqual([`text-${size}`, 'text-primary'])
    },
  )

  it('still lets a later size win over an earlier one, and a later colour over an earlier one', () => {
    expect(cn('text-body-sm text-secondary', 'text-headline-md text-primary')).toBe('text-headline-md text-primary')
  })
})
