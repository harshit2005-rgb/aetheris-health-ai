import { describe, expect, it } from 'vitest'
import { normalisePhone } from '@/lib/phone'

describe('normalisePhone', () => {
  it.each([
    ['98765 43210', '+919876543210'],
    ['9876543210', '+919876543210'],
    ['098765-43210', '+919876543210'],
    ['91 98765 43210', '+919876543210'],
    ['(+91) 98765 43210', '+919876543210'],
    ['+91 98765 43210', '+919876543210'],
    ['+44 20 7946 0958', '+442079460958'],
    ['6000000000', '+916000000000'],
  ])('reads "%s" as %s', (typed, expected) => {
    expect(normalisePhone(typed)).toBe(expected)
  })

  it.each(['', '12345 67890', '5876543210', '98765 4321', '98765 432100', '0091 98765 43210', '+0 9876543210', '+91 12', 'call me'])(
    'refuses "%s"',
    (typed) => {
      expect(normalisePhone(typed)).toBeNull()
    },
  )
})
