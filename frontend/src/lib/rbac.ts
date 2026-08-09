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

/** The 7 hospital roles from the spec (Part 1, 2B). */
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

export const ALL_ROLES: Role[] = [
  'super_admin',
  'hospital_admin',
  'receptionist',
  'doctor',
  'nurse',
  'billing_staff',
  'lab_technician',
]

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** Roles allowed to see this item; 'all' means every role. */
  roles: Role[] | 'all'
}

/**
 * Primary sidebar navigation, with per-item role visibility derived from the
 * module specs (Parts 3–10). Unauthorized items are hidden entirely.
 */
export const NAV: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, roles: 'all' },
  {
    to: '/patients',
    label: 'Patients',
    icon: Users,
    roles: ['super_admin', 'hospital_admin', 'receptionist', 'doctor', 'nurse', 'lab_technician'],
  },
  {
    to: '/doctors',
    label: 'Doctors',
    icon: Stethoscope,
    roles: ['super_admin', 'hospital_admin', 'receptionist', 'doctor', 'nurse'],
  },
  {
    to: '/appointments',
    label: 'Appointments',
    icon: CalendarDays,
    roles: ['super_admin', 'hospital_admin', 'receptionist', 'doctor', 'nurse'],
  },
  {
    to: '/billing',
    label: 'Billing',
    icon: Receipt,
    roles: ['super_admin', 'hospital_admin', 'billing_staff', 'receptionist', 'doctor'],
  },
  {
    to: '/reports',
    label: 'Reports',
    icon: BarChart3,
    roles: ['super_admin', 'hospital_admin', 'billing_staff', 'doctor'],
  },
  {
    to: '/settings',
    label: 'Settings',
    icon: Settings,
    roles: ['super_admin', 'hospital_admin'],
  },
]

export function canAccess(role: Role | undefined, item: NavItem): boolean {
  if (!role) return false
  return item.roles === 'all' || item.roles.includes(role)
}

/** Nav items visible to a given role. */
export function navForRole(role: Role | undefined): NavItem[] {
  return NAV.filter((item) => canAccess(role, item))
}
