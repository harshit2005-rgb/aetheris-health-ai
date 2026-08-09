import { X, Sparkles, ArrowUp } from 'lucide-react'
import { cn } from '@/lib/utils'

const SUGGESTED = [
  "Show today's appointments",
  'Summarize patient history',
  'List high-risk patients',
  'Generate revenue summary',
  'Find pending invoices',
]

interface CopilotPanelProps {
  open: boolean
  onClose: () => void
}

/**
 * Persistent AI Copilot side panel (spec Part 9). Scaffold only — suggested
 * prompts + composer. Wiring to the AI provider is a backend task.
 */
export default function CopilotPanel({ open, onClose }: CopilotPanelProps) {
  return (
    <>
      {open && (
        <button
          aria-label="Close AI Copilot"
          onClick={onClose}
          className="fixed inset-0 z-50 bg-black/20 backdrop-blur-sm"
        />
      )}
      <aside
        className={cn(
          'bg-surface fixed top-0 right-0 z-50 flex h-dvh w-full flex-col shadow-2xl transition-transform duration-300 sm:w-[420px]',
          open ? 'translate-x-0' : 'translate-x-full',
        )}
        aria-hidden={!open}
      >
        {/* Header */}
        <div className="border-outline-variant/30 flex items-center justify-between border-b px-5 py-4">
          <div className="flex items-center gap-2">
            <span className="bg-secondary/10 text-secondary flex size-9 items-center justify-center rounded-xl">
              <Sparkles className="size-5" />
            </span>
            <div>
              <h2 className="font-display text-title-lg text-primary font-bold">AI Copilot</h2>
              <p className="font-body text-outline text-xs">Context-aware assistant</p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-outline hover:text-primary rounded-lg p-1.5 transition-colors"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Conversation area (empty state) */}
        <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
          <span className="bg-secondary/10 text-secondary flex size-14 items-center justify-center rounded-2xl">
            <Sparkles className="size-7" />
          </span>
          <div>
            <p className="font-display text-title-lg text-primary font-bold">
              How can I help today?
            </p>
            <p className="font-body text-body-sm text-on-surface-variant mt-1">
              Ask about patients, appointments, billing, or reports.
            </p>
          </div>
          <div className="mt-2 flex w-full flex-col gap-2">
            {SUGGESTED.map((s) => (
              <button
                key={s}
                className="neo-pressed bg-surface font-body text-body-sm text-on-surface hover:text-secondary rounded-xl px-4 py-2.5 text-left transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Composer */}
        <div className="border-outline-variant/30 border-t p-4">
          <div className="neo-pressed bg-surface flex items-end gap-2 rounded-2xl p-2">
            <textarea
              rows={1}
              placeholder="Ask Aetheris AI..."
              className="font-body text-body-sm text-on-surface placeholder:text-outline-variant max-h-32 flex-1 resize-none bg-transparent px-2 py-1.5 outline-none"
            />
            <button
              aria-label="Send"
              className="bg-primary text-on-primary flex size-9 shrink-0 items-center justify-center rounded-xl transition-transform active:scale-95"
            >
              <ArrowUp className="size-5" />
            </button>
          </div>
          <p className="font-body text-outline mt-2 text-center text-[11px]">
            AI can make mistakes. Verify clinical decisions.
          </p>
        </div>
      </aside>
    </>
  )
}
