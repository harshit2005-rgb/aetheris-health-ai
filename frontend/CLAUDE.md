# Frontend Context (React / TypeScript)

You are in the frontend of Aetheris Health AI. The root `../CLAUDE.md` is in effect — read it first. This file adds frontend-specific rules.

---

## Stack

- **Framework:** React 18 + Vite
- **Language:** TypeScript (strict mode)
- **Styling:** Tailwind CSS (utility-first)
- **Component library:** Shadcn UI (extend, don't fork)
- **Server state:** TanStack React Query
- **Client state:** Zustand (only when React Query isn't enough)
- **Forms:** React Hook Form + Zod validation
- **Routing:** React Router v6
- **HTTP:** Axios (wrapped in a typed client)
- **Testing:** Vitest + Testing Library + Playwright (E2E)
- **Package manager:** `pnpm`

---

## Directory Layout

```
frontend/src/
├── api/               # API client, generated types, hooks (React Query)
├── components/
│   ├── ui/            # Shadcn primitives (Button, Input, Dialog, etc.)
│   └── shared/        # cross-module components
├── features/          # one folder per module (auth, patients, appointments...)
│   └── <module>/
│       ├── components/
│       ├── hooks/
│       ├── pages/
│       └── schemas/
├── layouts/           # AppShell, AuthLayout
├── lib/               # utils, formatters, constants
├── router/            # route definitions
├── stores/            # Zustand stores
└── main.tsx
```

**Feature folders are self-contained.** A component in `features/patients/` should not import from `features/billing/`. Shared cross-module UI goes to `components/shared/`.

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
