import { useAuthStore } from '@/store/auth-store'
import { navForRole, type Role } from '@/lib/rbac'

/**
 * Role/permission helpers for the current user. Use to filter nav, guard
 * routes, and hide unauthorized actions (spec: "hide unauthorized cards and
 * actions completely").
 */
export function usePermissions() {
  const role = useAuthStore((s) => s.user?.role)

  return {
    role,
    /** True if the current user has one of the given roles. */
    hasRole: (...roles: Role[]) => !!role && roles.includes(role),
    /** Nav items the current role may see. */
    nav: navForRole(role),
  }
}
