import { Icon } from '@/components/ui/icon'
import { RadialProgress } from '@/components/charts/RadialProgress'
import { cn } from '@/lib/utils'

type Priority = 'Critical' | 'Important' | 'Standard'

interface Task {
  title: string
  date: string
  time: string
  priority?: Priority
  focus?: boolean
}

const TASKS: Task[] = [
  { title: 'Review Patient Scans', date: 'Today', time: '11:00am', priority: 'Critical' },
  { title: 'Update Care Plan', date: 'Tomorrow', time: '05:00pm', priority: 'Important' },
  { title: 'Consultation Follow-up', date: 'Today', time: '10:00am', priority: 'Standard', focus: true },
  { title: 'Discharge Papers', date: '11.20.26', time: 'Anytime' },
]

const PRIORITY_STYLES: Record<Priority, string> = {
  Critical: 'bg-error-container text-error',
  Important: 'bg-error-container text-error',
  Standard: 'bg-surface-container-highest text-on-surface-variant',
}

function PriorityBadge({ priority }: { priority: Priority }) {
  return (
    <span
      className={cn(
        'inline-block rounded-full px-3 py-1 text-[11px] font-bold',
        PRIORITY_STYLES[priority],
      )}
    >
      {priority}
    </span>
  )
}

function TaskCard({ task, index }: { task: Task; index: number }) {
  const inner = (
    <>
      <div className="mb-3 flex items-start justify-between">
        <h3 className="font-body text-body-md text-on-surface font-bold">{task.title}</h3>
        <button className="text-outline-variant hover:text-primary transition-colors active:scale-90">
          <Icon name="more_vert" className="text-base" />
        </button>
      </div>
      <div className="font-body text-body-sm text-outline mb-4 flex gap-4">
        <span>{task.date}</span>
        <span>{task.time}</span>
      </div>
      {task.priority && <PriorityBadge priority={task.priority} />}
    </>
  )

  if (task.focus) {
    return (
      <div
        className="animate-in fade-in zoom-in-95 relative duration-500"
        style={{ animationDelay: `${index * 70}ms` }}
      >
        <div className="neo-extruded bg-surface absolute inset-0 rounded-xl opacity-50" />
        <div
          className="absolute inset-0 rounded-xl opacity-10"
          style={{
            backgroundImage:
              'repeating-linear-gradient(45deg, transparent, transparent 10px, #0a2540 10px, #0a2540 20px)',
          }}
        />
        <div className="glassmorphism relative ml-3 rounded-xl border border-white/60 p-5 shadow-xl">
          <div className="mb-3 flex items-start justify-between">
            <h3 className="font-body text-body-md text-primary font-bold">{task.title}</h3>
            <button className="text-outline-variant hover:text-primary transition-colors active:scale-90">
              <Icon name="more_vert" className="text-base" />
            </button>
          </div>
          <div className="font-body text-body-sm text-outline mb-4 flex gap-4">
            <span>{task.date}</span>
            <span>{task.time}</span>
          </div>
          {task.priority && <PriorityBadge priority={task.priority} />}
        </div>
      </div>
    )
  }

  return (
    <div
      className="neo-extruded bg-surface animate-in fade-in zoom-in-95 cursor-pointer rounded-xl p-5 transition-all duration-500 hover:-translate-y-0.5 active:scale-[0.98]"
      style={{ animationDelay: `${index * 70}ms` }}
    >
      {inner}
    </div>
  )
}

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-6 xl:flex-row">
      {/* Left column */}
      <div className="flex flex-1 flex-col gap-6">
        {/* Welcome card */}
        <div className="neo-extruded bg-surface animate-in fade-in slide-in-from-bottom-2 relative overflow-hidden rounded-2xl p-6 duration-500 md:p-8">
          <Icon
            name="assignment_ind"
            className="text-secondary pointer-events-none absolute top-1/2 right-8 hidden -translate-y-1/2 text-[120px] opacity-20 sm:block"
          />
          <div className="relative z-10 sm:w-2/3">
            <h2 className="font-display text-primary mb-2 text-2xl font-bold md:text-headline-lg">
              Your Clinical Workspace
            </h2>
            <p className="font-body text-body-sm text-on-surface-variant">
              Here you can edit, reschedule, rearrange &amp; prioritize your clinical tasks
              efficiently with AI assistance.
            </p>
          </div>
        </div>

        {/* Task grid */}
        <div className="gap-card-gap grid grid-cols-1 md:grid-cols-2">
          {TASKS.map((task, i) => (
            <TaskCard key={task.title} task={task} index={i} />
          ))}
        </div>
      </div>

      {/* Right stats rail */}
      <aside className="neo-extruded bg-surface animate-in fade-in slide-in-from-right-2 flex w-full flex-shrink-0 flex-col rounded-2xl p-6 duration-500 md:p-8 xl:w-80 xl:items-center">
        {/* Profile: compact row on mobile, centered column at xl */}
        <div className="border-outline-variant/20 mb-6 flex w-full items-center gap-4 border-b pb-6 xl:mb-8 xl:flex-col xl:pb-8 xl:text-center">
          <span className="neo-extruded bg-primary-container flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-full text-lg font-bold text-white xl:mb-4 xl:h-24 xl:w-24 xl:text-2xl">
            AC
          </span>
          <div>
            <h2 className="font-display text-title-lg text-primary font-bold xl:text-headline-md">
              Good morning, Dr. Chen!
            </h2>
            <p className="font-body text-body-sm text-outline mt-1">Monday, 08/05/26</p>
          </div>
        </div>

        <div className="mb-6 xl:mb-8 xl:text-center">
          <h3 className="font-display text-title-lg text-primary font-bold xl:text-headline-md">
            Your Tasks
          </h3>
          <p className="font-body text-body-sm text-outline mt-1">Stats for this week</p>
        </div>

        {/* Donuts: side by side on mobile/tablet, stacked at xl */}
        <div className="flex flex-row items-center justify-center gap-4 xl:flex-col xl:gap-8">
          <RadialProgress
            value={75}
            size={130}
            color="var(--color-secondary-container)"
            label="Tasks completed"
            sublabel="Completed"
          />
          <RadialProgress
            value={25}
            size={110}
            color="var(--color-outline)"
            label="Tasks postponed"
            sublabel="Postponed"
          />
        </div>
      </aside>
    </div>
  )
}
