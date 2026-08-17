import { describe, it, expect } from 'vitest'
import {
  hasPermission,
  navForPermissions,
  MOCK_PERMISSIONS_BY_ROLE,
  type Permission,
} from './rbac'

describe('rbac', () => {
  it('hasPermission checks membership in the permission set', () => {
    const perms: Permission[] = ['dashboard.view', 'patient.read']
    expect(hasPermission(perms, 'patient.read')).toBe(true)
    expect(hasPermission(perms, 'billing.read')).toBe(false)
    expect(hasPermission(undefined, 'dashboard.view')).toBe(false)
  })

  it('navForPermissions only returns items the user is permitted to see', () => {
    // Receptionist has no report/settings permission.
    const nav = navForPermissions(MOCK_PERMISSIONS_BY_ROLE.receptionist)
    const paths = nav.map((n) => n.to)
    expect(paths).toContain('/patients')
    expect(paths).toContain('/appointments')
    expect(paths).not.toContain('/reports')
    expect(paths).not.toContain('/settings')
  })

  it('billing staff sees billing and reports but not patients or settings', () => {
    const paths = navForPermissions(MOCK_PERMISSIONS_BY_ROLE.billing_staff).map((n) => n.to)
    expect(paths).toEqual(expect.arrayContaining(['/dashboard', '/billing', '/reports']))
    expect(paths).not.toContain('/patients')
    expect(paths).not.toContain('/settings')
  })

  it('an empty permission set sees no nav', () => {
    expect(navForPermissions([])).toHaveLength(0)
    expect(navForPermissions(undefined)).toHaveLength(0)
  })
})
