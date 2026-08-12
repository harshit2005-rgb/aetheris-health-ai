import {
  LayoutDashboard,
  Users,
  Stethoscope,
  CalendarDays,
  Receipt,
  BarChart3,
  Settings,
  type LucideIcon,
} from 'lucide-react'

/** The 7 hospital roles (spec Part 1, 2B). Roles are for DISPLAY only. */
export type Role =
  | 'super_admin'
  | 'hospital_admin'
  | 'receptionist'
  | 'doctor'
  | 'nurse'
  | 'billing_staff'
  | 'lab_technician'

export const ROLE_LABELS: Record<Role, string> = {
  super_admin: 'Super Admin',
  hospital_admin: 'Hospital Admin',
  receptionist: 'Receptionist',
  doctor: 'Doctor',
  nurse: 'Nurse',
  billing_staff: 'Billing Staff',
  lab_technician: 'Lab Technician',
}

/**
 * Authorization is modelled on PERMISSION CODES, matching what the backend
 * issues in the token and checks via require_permission() (defect F5). Roles
 * never gate access on their own — the client only ever asks `can('patient.read')`.
 */
export type Permission =
  | 'dashboard.view'
  | 'patient.read'
  | 'patient.write'
  | 'doctor.read'
  | 'doctor.write'
  | 'appointment.read'
  | 'appointment.write'
  | 'billing.read'
  | 'billing.write'
  | 'report.read'
  | 'settings.manage'

/**
 * Mock role→permission mapping, used ONLY by the dev mock login. In production
 * the permission set arrives from the server in the auth response; the client
 * never derives it from the role.
 */
export const MOCK_PERMISSIONS_BY_ROLE: Record<Role, Permission[]> = {
  super_admin: [
    'dashboard.view', 'patient.read', 'patient.write', 'doctor.read', 'doctor.write',
    'appointment.read', 'appointment.write', 'billing.read', 'billing.write', 'report.read',
    'settings.manage',
  ],
  hospital_admin: [
    'dashboard.view', 'patient.read', 'patient.write', 'doctor.read', 'doctor.write',
    'appointment.read', 'appointment.write', 'billing.read', 'billing.write', 'report.read',
    'settings.manage',
  ],
  receptionist: [
    'dashboard.view', 'patient.read', 'patient.write', 'doctor.read', 'appointment.read',
    'appointment.write', 'billing.read',
  ],
  doctor: [
    'dashboard.view', 'patient.read', 'patient.write', 'doctor.read', 'appointment.read',
    'appointment.write', 'billing.read', 'report.read',
  ],
  nurse: ['dashboard.view', 'patient.read', 'patient.write', 'doctor.read', 'appointment.read'],
  billing_staff: ['dashboard.view', 'billing.read', 'billing.write', 'report.read'],
  lab_technician: ['dashboard.view', 'patient.read'],
}

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** The permission required to see this nav item and reach its route. */
  permission: Permission
}

/** Primary sidebar navigation, gated by permission (spec Parts 3–10). */
export const NAV: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, permission: 'dashboard.view' },
  { to: '/patients', label: 'Patients', icon: Users, permission: 'patient.read' },
  { to: '/doctors', label: 'Doctors', icon: Stethoscope, permission: 'doctor.read' },
  { to: '/appointments', label: 'Appointments', icon: CalendarDays, permission: 'appointment.read' },
  { to: '/billing', label: 'Billing', icon: Receipt, permission: 'billing.read' },
  { to: '/reports', label: 'Reports', icon: BarChart3, permission: 'report.read' },
  { to: '/settings', label: 'Settings', icon: Settings, permission: 'settings.manage' },
]

export function hasPermission(userPerms: Permission[] | undefined, perm: Permission): boolean {
  return !!userPerms && userPerms.includes(perm)
}

/** Nav items the given permission set may see. */
export function navForPermissions(userPerms: Permission[] | undefined): NavItem[] {
  return NAV.filter((item) => hasPermission(userPerms, item.permission))
}
