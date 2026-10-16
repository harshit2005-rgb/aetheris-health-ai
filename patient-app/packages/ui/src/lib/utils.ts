import { clsx, type ClassValue } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

/**
 * The type scale from `@atheris/design-tokens` (`--text-*` in tokens.css).
 * tailwind-merge does not know these names, so without them it reads
 * `text-headline-md` as a colour and drops it when a colour such as
 * `text-primary` follows.
 */
const TYPE_SCALE = ['headline-xl', 'headline-lg', 'headline-md', 'title-lg', 'body-lg', 'body-md', 'body-sm', 'label-caps', 'label-mono']

const twMerge = extendTailwindMerge({
  extend: { classGroups: { 'font-size': [{ text: TYPE_SCALE }] } },
})

/** Merge Tailwind classes, resolving conflicts (shadcn/ui convention). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
