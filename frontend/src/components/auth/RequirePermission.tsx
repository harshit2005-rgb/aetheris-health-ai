import { Navigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import { usePermissions } from '@/hooks/usePermissions'
import type { Permission } from '@/lib/rbac'

/**
 * Route-level authorization (defect F6). Hiding a nav link is only a UX
 * affordance; the route itself must be guarded from the SAME permission the nav
 * filter uses, so typing /billing directly cannot reach a denied module.
 */
export function RequirePermission({
  permission,
  children,
}: {
  permission: Permission
  children: ReactNode
}) {
  const { can } = usePermissions()
  if (!can(permission)) return <Navigate to="/dashboard" replace />
  return <>{children}</>
}
