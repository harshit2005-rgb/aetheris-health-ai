import type { ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ManagedUser, RoleSummary } from '@/api/users'
import { MOCK_PERMISSIONS_BY_ROLE } from '@/lib/rbac'
import { signIn, signOut } from '@/test/auth'
import { bodyOf, fail, installFakeApi, ok, paged, type FakeApi, type Outcome } from '@/test/fakeApi'
import { InviteUserDialog } from './InviteUserDialog'
import { ManageRolesDialog } from './ManageRolesDialog'

/**
 * Role assignment and invites against `POST /users`, `POST /users/{id}/roles`
 * and `DELETE /users/{id}/roles/{role_id}` (`backend/app/api/v1/users.py`).
 * The real hooks, permission store and Axios instance run; only the network
 * adapter is replaced.
 *
 * The rule under test is `_assert_grantable`
 * (`backend/app/services/user_service.py`): a role that includes a permission
 * the actor does not hold is refused with a 403.
 */

const { toastSuccess, toastError } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock('sonner', () => ({ toast: { success: toastSuccess, error: toastError } }))

const SUPER: RoleSummary = { id: 'r-super', name: 'Super Admin', description: null, is_system: true }
const HOSPITAL: RoleSummary = { id: 'r-hadmin', name: 'Hospital Admin', description: null, is_system: true }
const NURSE: RoleSummary = { id: 'r-nurse', name: 'Nurse', description: null, is_system: true }
/** A hospital's own role: the frontend cannot know what it grants. */
const CUSTOM: RoleSummary = { id: 'r-custom', name: 'Ward Clerk', description: null, is_system: false }

const target: ManagedUser = {
  id: 'u2',
  email: 'priya@hospital.test',
  first_name: 'Priya',
  last_name: 'Nair',
  phone: null,
  status: 'active',
  hospital_id: 'h1',
  roles: [HOSPITAL],
  mfa_enabled: false,
  last_login_at: null,
  password_changed_at: null,
  created_at: null,
  updated_at: null,
}

const ESCALATION = 'You cannot grant a role that includes permissions you do not hold.'

let fake: FakeApi
let onAssign: () => Outcome | Promise<Outcome>
let onRemove: () => Outcome | Promise<Outcome>
let onInvite: () => Outcome | Promise<Outcome>

beforeEach(() => {
  toastSuccess.mockReset()
  toastError.mockReset()
  onAssign = () => ok(null)
  onRemove = () => ok(null)
  onInvite = () => ok({ ...target, id: 'u9', status: 'invited', invite_token: 'tok-abc123' }, 201)
  fake = installFakeApi((config) => {
    if (config.method === 'get' && config.url === '/roles') return paged([SUPER, HOSPITAL, NURSE, CUSTOM])
    if (config.method === 'get' && config.url === '/users/u2') return ok(target)
    if (config.method === 'post' && config.url === '/users/u2/roles') return onAssign()
    if (config.method === 'delete') return onRemove()
    if (config.method === 'post' && config.url === '/users') return onInvite()
    return paged([])
  })
})

afterEach(() => {
  fake.restore()
  signOut()
})

function withClient(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

const assigns = () => fake.requests('post', '/users/u2/roles')
const invites = () => fake.sent.filter((c) => c.method === 'post' && c.url === '/users')

async function offeredRoles(user: ReturnType<typeof userEvent.setup>, trigger: HTMLElement) {
  await user.click(trigger)
  const names = (await screen.findAllByRole('option')).map((o) => o.textContent)
  await user.keyboard('{Escape}')
  return names
}

describe('ManageRolesDialog', () => {
  function renderDialog() {
    withClient(<ManageRolesDialog user={target} onClose={() => {}} />)
  }

  const roleSelect = () => screen.findByRole('combobox', { name: 'Assign a role' })

  async function pick(user: ReturnType<typeof userEvent.setup>, name: RegExp) {
    await user.click(await roleSelect())
    await user.click(await screen.findByRole('option', { name }))
  }

  it('does not offer a Hospital Admin the Super Admin role, which the API would refuse', async () => {
    signIn(MOCK_PERMISSIONS_BY_ROLE.hospital_admin)
    const user = userEvent.setup()
    renderDialog()
    await waitFor(() => expect(fake.requests('get', '/roles')).toHaveLength(1))

    const names = await offeredRoles(user, await roleSelect())
    expect(names).toEqual(['Nurse (system)', 'Ward Clerk'])
  })

  it('offers Super Admin to someone who holds everything it grants', async () => {
    signIn(MOCK_PERMISSIONS_BY_ROLE.super_admin)
    const user = userEvent.setup()
    renderDialog()
    await waitFor(() => expect(fake.requests('get', '/roles')).toHaveLength(1))

    expect(await offeredRoles(user, await roleSelect())).toContain('Super Admin (system)')
  })

  it("reports the API's reason when an assignment is refused", async () => {
    signIn(MOCK_PERMISSIONS_BY_ROLE.hospital_admin)
    onAssign = () => fail(403, ESCALATION, { error_code: 'PERMISSION_DENIED' })
    const user = userEvent.setup()
    renderDialog()
    await pick(user, /Ward Clerk/)
    await user.click(screen.getByRole('button', { name: /Assign/ }))

    await waitFor(() => expect(toastError).toHaveBeenCalledWith(ESCALATION))
  })

  it('does not blame a permission, or show server text, when the server fails', async () => {
    signIn(MOCK_PERMISSIONS_BY_ROLE.hospital_admin)
    onAssign = () => ({ status: 500, data: 'Internal Server Error' })
    const user = userEvent.setup()
    renderDialog()
    await pick(user, /Ward Clerk/)
    await user.click(screen.getByRole('button', { name: /Assign/ }))

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Couldn't assign the role. Please try again."),
    )
  })

  it('sends one assignment when Assign is clicked twice before the button disables', async () => {
    signIn(MOCK_PERMISSIONS_BY_ROLE.hospital_admin)
    let finish: (outcome: Outcome) => void = () => {}
    onAssign = () => new Promise<Outcome>((resolve) => (finish = resolve))
    const user = userEvent.setup()
    renderDialog()
    await pick(user, /Nurse/)

    const assign = screen.getByRole('button', { name: /Assign/ })
    // Two clicks dispatched back to back, with no re-render in between.
    assign.click()
    assign.click()

    await waitFor(() => expect(assigns()).toHaveLength(1))
    finish(ok(null))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledTimes(1))
    expect(assigns()).toHaveLength(1)
    expect(bodyOf(assigns()[0])).toEqual({ role_id: 'r-nurse' })
  })

  it('sends one removal when the remove button is clicked twice', async () => {
    signIn(MOCK_PERMISSIONS_BY_ROLE.hospital_admin)
    let finish: (outcome: Outcome) => void = () => {}
    onRemove = () => new Promise<Outcome>((resolve) => (finish = resolve))
    renderDialog()

    const removeButton = await screen.findByRole('button', { name: 'Remove Hospital Admin' })
    removeButton.click()
    removeButton.click()

    await waitFor(() => expect(fake.requests('delete')).toHaveLength(1))
    finish(ok(null))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledTimes(1))
    expect(fake.requests('delete')).toHaveLength(1)
  })

  it("says why the API refused to remove the last administrator's role", async () => {
    signIn(MOCK_PERMISSIONS_BY_ROLE.hospital_admin)
    const reason =
      "This is the hospital's last administrator — assign the role to someone else before removing it."
    onRemove = () => fail(400, reason, { error_code: 'BUSINESS_RULE_VIOLATION' })
    const user = userEvent.setup()
    renderDialog()

    await user.click(await screen.findByRole('button', { name: 'Remove Hospital Admin' }))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith(reason))
  })
})

describe('InviteUserDialog', () => {
  async function openDialog(user: ReturnType<typeof userEvent.setup>) {
    withClient(<InviteUserDialog trigger={<button type="button">Invite user</button>} />)
    await user.click(screen.getByRole('button', { name: 'Invite user' }))
    return screen.findByRole('dialog')
  }

  async function fill(user: ReturnType<typeof userEvent.setup>) {
    await user.type(screen.getByLabelText(/Email/), 'new.nurse@hospital.test')
    await user.type(screen.getByLabelText(/First name/), 'Meera')
    await user.type(screen.getByLabelText(/Last name/), 'Iyer')
  }

  const submit = (user: ReturnType<typeof userEvent.setup>) =>
    user.click(screen.getByRole('button', { name: 'Create invite' }))

  it('says how the invited user gets in, without promising an email', async () => {
    signIn(MOCK_PERMISSIONS_BY_ROLE.hospital_admin)
    const dialog = await openDialog(userEvent.setup())

    expect(within(dialog).getByText(/one-time\s+invite link/)).toBeInTheDocument()
    expect(within(dialog).getByText(/if email delivery is configured/)).toBeInTheDocument()
    expect(within(dialog).queryByText(/first login/)).not.toBeInTheDocument()
  })

  it('shows the one-time link the API returned, to copy and pass on', async () => {
    signIn(MOCK_PERMISSIONS_BY_ROLE.hospital_admin)
    const user = userEvent.setup()
    await openDialog(user)
    await fill(user)
    await submit(user)

    const link = await screen.findByLabelText('One-time invite link')
    const expected = `${window.location.origin}/reset-password?token=tok-abc123`
    expect(link).toHaveValue(expected)
    expect(link).toHaveAttribute('readonly')
    expect(screen.getByText('This link is shown only once')).toBeInTheDocument()
    expect(screen.getByText(/only if email delivery is\s+configured/)).toBeInTheDocument()
    // The toast names no token the admin cannot see.
    expect(toastSuccess).toHaveBeenCalledWith('Invite created for new.nurse@hospital.test')

    await user.click(screen.getByRole('button', { name: /Copy link/ }))
    expect(await navigator.clipboard.readText()).toBe(expected)

    await user.click(screen.getByRole('button', { name: 'Done' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('keeps the one-time link on screen when Escape is pressed', async () => {
    signIn(MOCK_PERMISSIONS_BY_ROLE.hospital_admin)
    const user = userEvent.setup()
    await openDialog(user)
    await fill(user)
    await submit(user)

    const link = await screen.findByLabelText('One-time invite link')
    link.focus()
    await user.keyboard('{Escape}')

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByLabelText('One-time invite link')).toHaveValue(
      `${window.location.origin}/reset-password?token=tok-abc123`,
    )

    await user.click(screen.getByRole('button', { name: 'Done' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('still closes the empty form on Escape', async () => {
    signIn(MOCK_PERMISSIONS_BY_ROLE.hospital_admin)
    const user = userEvent.setup()
    await openDialog(user)

    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('sends one invite when the form is submitted twice in the same tick', async () => {
    signIn(MOCK_PERMISSIONS_BY_ROLE.hospital_admin)
    let finish: (outcome: Outcome) => void = () => {}
    onInvite = () => new Promise<Outcome>((resolve) => (finish = resolve))
    const user = userEvent.setup()
    const dialog = await openDialog(user)
    await fill(user)

    const form = dialog.querySelector('form') as HTMLFormElement
    fireEvent.submit(form)
    fireEvent.submit(form)

    await waitFor(() => expect(invites()).toHaveLength(1))
    finish(ok({ ...target, id: 'u9', invite_token: 'tok-abc123' }, 201))
    await screen.findByLabelText('One-time invite link')
    expect(invites()).toHaveLength(1)
  })

  it('names each role row and its remove button, and offers only grantable roles', async () => {
    signIn(MOCK_PERMISSIONS_BY_ROLE.hospital_admin)
    const user = userEvent.setup()
    await openDialog(user)
    await waitFor(() => expect(screen.getByRole('button', { name: /Add role/ })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: /Add role/ }))
    await user.click(screen.getByRole('button', { name: /Add role/ }))

    expect(screen.getByRole('combobox', { name: /Assign role/ })).toBeInTheDocument()
    const second = screen.getByRole('combobox', { name: 'Role 2' })
    expect(screen.getByRole('button', { name: 'Remove role 1' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove role 2' })).toBeInTheDocument()

    expect(await offeredRoles(user, second)).toEqual(['Hospital Admin', 'Nurse', 'Ward Clerk'])
  })

  it('puts a 422 under the field it names and the rest above the form', async () => {
    signIn(MOCK_PERMISSIONS_BY_ROLE.hospital_admin)
    onInvite = () =>
      fail(422, 'Validation failed.', {
        error_code: 'VALIDATION_ERROR',
        errors: [
          { field: 'email', message: 'value is not a valid email address' },
          { field: 'role_ids.0', message: 'Input should be a valid UUID' },
          { field: 'department_id', message: 'Extra inputs are not permitted' },
        ],
      })
    const user = userEvent.setup()
    const dialog = await openDialog(user)
    await fill(user)
    await waitFor(() => expect(screen.getByRole('button', { name: /Add role/ })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: /Add role/ }))
    await user.click(screen.getByRole('combobox', { name: /Assign role/ }))
    await user.click(await screen.findByRole('option', { name: 'Nurse' }))
    await submit(user)

    expect(await within(dialog).findByText('value is not a valid email address')).toBeInTheDocument()
    expect(within(dialog).getByText('Input should be a valid UUID')).toBeInTheDocument()
    expect(within(dialog).getByText('Extra inputs are not permitted')).toBeInTheDocument()
    expect(screen.getByLabelText(/Email/)).toHaveAttribute('aria-invalid', 'true')
    expect(toastError).toHaveBeenCalledWith('Extra inputs are not permitted')
  })

  it("reports the API's reason for a refusal instead of asking for a retry", async () => {
    signIn(MOCK_PERMISSIONS_BY_ROLE.hospital_admin)
    onInvite = () => fail(403, ESCALATION, { error_code: 'PERMISSION_DENIED' })
    const user = userEvent.setup()
    const dialog = await openDialog(user)
    await fill(user)
    await submit(user)

    expect(await within(dialog).findByText(ESCALATION)).toBeInTheDocument()
    expect(toastError).toHaveBeenCalledWith(ESCALATION)
  })

  it('shows a plain sentence, not server text, when the server fails', async () => {
    signIn(MOCK_PERMISSIONS_BY_ROLE.hospital_admin)
    onInvite = () => ({ status: 502, data: '<html>Bad Gateway</html>' })
    const user = userEvent.setup()
    await openDialog(user)
    await fill(user)
    await submit(user)

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Couldn't create the invite. Please try again."),
    )
  })
})
