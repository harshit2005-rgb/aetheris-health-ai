/**
 * Shared Clinical Glass control surface — the sunken neomorphic field used by
 * Input, Textarea, and the Select trigger so every form control matches.
 */
export const controlClass = [
  'neo-pressed bg-surface w-full rounded-xl px-4 py-2.5',
  'font-body text-body-sm text-on-surface placeholder:text-outline-variant',
  'outline-none transition-shadow',
  'focus-visible:ring-2 focus-visible:ring-secondary',
  'aria-[invalid=true]:ring-2 aria-[invalid=true]:ring-error',
  'disabled:cursor-not-allowed disabled:opacity-60',
].join(' ')
