# Frontend Context (React / TypeScript)

You are in the frontend of Aetheris Health AI. The root `../CLAUDE.md` is in effect — read it first. This file adds frontend-specific rules.

---

## Stack

> Reconciled with the built frontend and team ruling (2026-08-09): React 19,
> npm, and the `pages/<module>/` layout from `docs/09-PROJECT_STRUCTURE.md`.

- **Framework:** React 19 + Vite
- **Language:** TypeScript (strict mode)
- **Styling:** Tailwind CSS v4 (utility-first)
- **Component library:** shadcn/ui (extend, don't fork)
- **Server state:** TanStack React Query
- **Client state:** Zustand (only when React Query isn't enough)
- **Forms:** React Hook Form + Zod validation
- **Routing:** React Router v7
- **HTTP:** Axios (wrapped in a typed client)
- **Testing:** Vitest + Testing Library + Playwright (E2E)
- **Package manager:** `npm`
- **Design language:** "Clinical Glass" (glassmorphism + soft neomorphism, navy
  `#0A2540` + cyan `#00D4FF`) — an approved override of Spec Part 11's flat
  mandate. See `docs/17-FRONTEND_BUILD_PLAN.md`.

---

## Directory Layout

> Team ruling: follow `docs/09-PROJECT_STRUCTURE.md` (`pages/<module>/`), not the
> earlier `features/` proposal.

```
frontend/src/
├── app/ (or root)     # App.tsx, router.tsx, providers
├── api/               # axios client + typed React Query hooks per module
├── components/
│   ├── ui/            # shadcn primitives (Button, Input, Dialog, ...)
│   ├── layout/        # shell: Sidebar, TopBar, Breadcrumbs, CopilotPanel
│   ├── charts/        # chart wrappers
│   └── <shared>/      # brand/, glass/ cross-module UI
├── layouts/           # DashboardLayout, AuthLayout, PublicLayout
├── pages/             # one folder per module: patients/ doctors/ billing/ ...
├── hooks/             # useAuth, usePermissions, usePagination, ...
├── lib/               # utils, rbac, constants
├── store/             # Zustand stores
└── main.tsx
```

**Cross-module isolation still applies:** `pages/patients/` should not import from
`pages/billing/`. Shared cross-module UI goes in `components/`.

---

## Coding Rules

- **No `any`.** Ever. If a type is truly dynamic, use `unknown` and narrow it.
- **No inline styles.** Tailwind only. If Tailwind can't express it, ask before writing custom CSS.
- **No `useState` for server data.** Use React Query.
- **No `useEffect` for data fetching.** React Query only. `useEffect` is for imperative side effects (subscriptions, timers).
- **Every list has a stable `key`.** Never use array index unless the list is immutable and static.
- **Every form uses React Hook Form + a Zod schema.**
- **Every API call has a typed hook** (`usePatient(id)`, `useCreateAppointment()`) — never call the axios client directly from a component.
- **Icons come from `lucide-react`.** No emoji as icons.
- **Dates displayed via a formatter that respects the hospital's timezone** (from user context).
- **Money displayed via a formatter that respects the hospital's currency.**

---

## API Response Envelope

Every API response follows this shape:

```ts
type ApiResponse<T> = {
  success: boolean;
  data: T;
  meta?: { pagination?: ... };
  error?: { code: string; message: string; details?: unknown };
};
```

The API client unwraps `data` on success and throws a typed `ApiError` on failure. Components never see the envelope.

---

## Auth Flow

- Access token in memory (Zustand `authStore`)
- Refresh token in HTTP-only cookie (backend sets it)
- On 401 → try silent refresh once → on failure, redirect to `/login`
- `AuthGate` component wraps protected routes and calls `useAuth()`
- Permissions checked via `usePermissions()` — never trust the frontend as the security boundary; the backend enforces

---

## React Query Patterns

- Query keys: `["module", "resource", { filters }]` — e.g., `["patients", "list", { search, page }]`
- Mutations invalidate specific queries, not the whole cache
- Optimistic updates for fast interactions (favorites, toggles)
- Use `keepPreviousData: true` for paginated tables
- `staleTime` default: 30s. Dashboard queries: 60s. Real-time-ish queries: 0.

---

## Component Patterns

- Prefer composition over prop drilling. Use `children` and slots.
- Container/presentation split for complex screens: `PatientListPage` (data) → `PatientList` (dumb UI).
- Every dialog/modal uses `Dialog` from Shadcn — no custom modal implementations.
- Every table uses `TanStack Table` (Shadcn wrapper) — no hand-rolled `<table>`.
- Every form field has: label, error slot, help text slot.
- Loading skeletons, not spinners, for above-the-fold content.

---

## Accessibility

- Every interactive element is keyboard-reachable and has a visible focus state
- Every form field has an associated `<label>`
- Every image has meaningful `alt` (or `alt=""` if decorative)
- Color contrast meets WCAG AA
- Live regions (`aria-live`) for toast notifications
- Never trap focus except inside modals

---

## Testing

- **Vitest + Testing Library** for components (test behavior, not implementation)
- **Mock the API client** at the module boundary, not `fetch`
- **Playwright** for E2E workflow tests — see `docs/16-END_TO_END_WORKFLOWS.md`
- Every feature page has at least one component test covering the happy path
- Every form has a test for validation errors

---

## Common Pitfalls

- Using `useState` for server data → causes staleness. Use React Query.
- Forgetting to `await` a mutation → race conditions. Use `mutateAsync` or `onSuccess`.
- Rendering an unstable list of hooks (hooks inside `.map()`) → React error. Refactor to child component.
- Overusing Zustand → most state is server state or URL state. Zustand is for genuinely client-only UI state.
- Using `document.querySelector` → almost always the wrong tool. Use refs or state.
- Hardcoding strings that should be config or i18n keys.

---

## Definition of Done for a Frontend Feature

- [ ] TypeScript strict, no `any`
- [ ] Component tests for happy + error paths
- [ ] Playwright E2E for user-facing flow (if part of a workflow)
- [ ] Loading, error, empty states designed
- [ ] Accessible (keyboard nav, labels, contrast)
- [ ] Responsive to 375px width minimum
- [ ] `make test-frontend` green
- [ ] `make lint` green
- [ ] No `console.log` in committed code
- [ ] No new npm packages without approval
