import { useTheme } from 'next-themes'
import { Moon, Sun } from 'lucide-react'

/** Light/dark toggle. Reflects the resolved theme (incl. system preference). */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const isDark = resolvedTheme === 'dark'

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Light mode' : 'Dark mode'}
      className="text-outline-variant hover:text-secondary hover:bg-white/20 flex size-10 items-center justify-center rounded-lg transition-colors"
    >
      {isDark ? <Sun className="size-5" /> : <Moon className="size-5" />}
    </button>
  )
}
