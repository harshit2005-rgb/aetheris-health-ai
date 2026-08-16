import { useAuthStore } from '@/store/auth-store'
import { navForPermissions, hasPermission, type Permission } from '@/lib/rbac'

/**
 * Authorization for the current user, modelled on PERMISSION CODES (defect F5).
 * Components ask `can('patient.read')` — never `hasRole(...)`. Roles are display
 * only. This is a UX affordance, not a security boundary: the backend enforces.
 */
export function usePermissions() {
  const user = useAuthStore((s) => s.user)
  const permissions = user?.permissions

  return {
    role: user?.role,
    can: (permission: Permission) => hasPermission(permissions, permission),
    /** Nav items the current permission set may see. */
    nav: navForPermissions(permissions),
  }
}
