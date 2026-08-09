import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { Logo } from '@/components/brand/Logo'
import { Icon } from '@/components/ui/icon'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/pricing', label: 'Pricing' },
  { to: '/contact', label: 'Contact' },
]

/**
 * Public top nav. Desktop: two floating pills (brand + nav left, auth right).
 * Mobile: brand pill + a hamburger that opens a dropdown menu.
 */
export default function MarketingNav() {
  const [open, setOpen] = useState(false)
  const close = () => setOpen(false)

  return (
    <nav className="px-container-padding fixed top-4 right-0 left-0 z-50">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3">
        {/* Left pill: brand + desktop nav */}
        <div className="glassmorphism shadow-glass-panel flex h-14 items-center gap-6 rounded-2xl pr-6 pl-5 md:h-16">
          <Link to="/" onClick={close} className="flex items-center">
            <Logo className="h-8 md:h-10" />
          </Link>
          <div className="hidden items-center gap-6 md:flex">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'font-label text-label-caps pb-1 transition-colors',
                    isActive
                      ? 'text-secondary border-secondary border-b-2 font-bold'
                      : 'text-on-surface-variant hover:text-secondary',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        </div>

        {/* Right pill: desktop auth / mobile hamburger */}
        <div className="glassmorphism shadow-glass-panel flex h-14 items-center gap-2 rounded-2xl px-3 md:h-16">
          <Link
            to="/login"
            className="font-label text-label-caps text-on-surface-variant hover:text-secondary hidden px-3 py-2 transition-colors md:inline-block"
          >
            Log in
          </Link>
          <Link
            to="/login"
            className="shadow-neo-base bg-primary text-on-primary font-label text-label-caps hidden rounded-full px-5 py-2.5 font-bold transition-all duration-300 hover:-translate-y-0.5 active:translate-y-0 md:inline-block"
          >
            Get Started
          </Link>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
            className="text-primary flex h-10 w-10 items-center justify-center md:hidden"
          >
            <Icon name={open ? 'close' : 'menu'} className="text-2xl" />
          </button>
        </div>
      </div>

      {/* Mobile dropdown menu */}
      {open && (
        <>
          <button
            aria-label="Close menu"
            onClick={close}
            className="fixed inset-x-0 top-24 bottom-0 cursor-default md:hidden"
          />
          <div className="bg-surface-container-lowest border-outline-variant/30 shadow-glass-panel animate-in fade-in slide-in-from-top-2 mx-auto mt-3 max-w-7xl rounded-2xl border p-4 duration-200 md:hidden">
            <div className="flex flex-col gap-1">
              {NAV.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={close}
                  className={({ isActive }) =>
                    cn(
                      'font-body text-body-md rounded-xl px-4 py-3 transition-colors',
                      isActive
                        ? 'neo-pressed text-secondary font-bold'
                        : 'text-on-surface-variant hover:text-primary',
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}
              <div className="border-outline-variant/30 mt-2 flex flex-col gap-2 border-t pt-3">
                <Link
                  to="/login"
                  onClick={close}
                  className="font-body text-body-md text-on-surface-variant rounded-xl px-4 py-3 text-center transition-colors"
                >
                  Log in
                </Link>
                <Link
                  to="/login"
                  onClick={close}
                  className="shadow-neo-base bg-primary text-on-primary font-label text-label-caps rounded-full px-5 py-3 text-center font-bold"
                >
                  Get Started
                </Link>
              </div>
            </div>
          </div>
        </>
      )}
    </nav>
  )
}
