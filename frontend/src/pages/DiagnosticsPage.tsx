import { Icon } from '@/components/ui/icon'

const VITALS = [
  { label: 'HEART RATE', value: '72', unit: 'bpm', icon: 'favorite', tone: 'text-secondary' },
  { label: 'BLOOD PRESSURE', value: '120/80', unit: 'mmHg', icon: 'blood_pressure', tone: 'text-primary' },
  { label: 'O2 SATURATION', value: '98', unit: '%', icon: 'air', tone: 'text-secondary' },
]

const FEED = [
  {
    time: '10:42 AM · AGENT ALPHA',
    icon: 'psychiatry',
    body: 'Correlating current MRI findings with patient history from 2023. No significant progression in lesion size.',
  },
  {
    time: '10:39 AM · SYSTEM',
    icon: 'settings_suggest',
    body: 'Vitals logged successfully. Blood pressure normalized post-medication.',
  },
  {
    time: '10:35 AM · AGENT BETA',
    icon: 'warning',
    body: 'Detected slight irregularity in heart rhythm. Recommending secondary ECG screening.',
    alert: true,
  },
]

const RECOMMENDATIONS = [
  {
    title: 'Schedule Follow-up MRI',
    body: 'Recommend a T1-weighted scan in 3 months to monitor hyperintensity.',
  },
  {
    title: 'Adjust Medication Dosage',
    body: 'Consider reducing antihypertensive dose based on stabilized vitals.',
  },
]

function ActionButtons() {
  return (
    <div className="flex w-full gap-3 md:w-auto">
      <button className="neo-extruded font-label text-label-caps text-secondary flex flex-1 items-center justify-center gap-2 rounded-full px-6 py-2.5 font-bold transition-transform active:scale-95 md:flex-none">
        <Icon name="sync" className="text-base" />
        Sync Data
      </button>
      <button className="shadow-neo-base bg-secondary text-on-secondary font-label text-label-caps flex flex-1 items-center justify-center gap-2 rounded-full px-6 py-2.5 font-bold transition-transform active:scale-95 md:flex-none">
        <Icon name="add" className="text-base" />
        New Scan
      </button>
    </div>
  )
}

export default function DiagnosticsPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-8">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <h1 className="font-display text-primary text-3xl font-extrabold tracking-tight md:text-headline-xl">
            AI Diagnostic Engine
          </h1>
          <p className="font-body text-body-md text-on-surface-variant mt-2">
            Real-time clinical analysis and agentic recommendations.
          </p>
        </div>
        <ActionButtons />
      </div>

      {/* Bento grid */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-12">
        {/* Patient Vitals */}
        <section className="neo-extruded bg-surface relative overflow-hidden rounded-2xl p-6 md:col-span-4">
          <Icon
            name="monitor_heart"
            className="text-primary pointer-events-none absolute top-2 right-2 text-[120px] opacity-5"
          />
          <h2 className="font-display text-title-lg text-primary mb-6 flex items-center gap-2 font-bold">
            <Icon name="vital_signs" className="text-secondary" /> Patient Vitals
          </h2>
          <div className="relative z-10 space-y-4">
            {VITALS.map((v) => (
              <div
                key={v.label}
                className="neo-pressed flex items-center justify-between rounded-xl p-4"
              >
                <div>
                  <div className="font-label text-label-caps text-on-surface-variant">{v.label}</div>
                  <div className={`font-display text-2xl font-extrabold ${v.tone}`}>
                    {v.value}{' '}
                    <span className="font-body text-body-sm text-on-surface-variant font-normal">
                      {v.unit}
                    </span>
                  </div>
                </div>
                <Icon name={v.icon} className={v.tone} />
              </div>
            ))}
          </div>
        </section>

        {/* Neural Image Analysis */}
        <section className="neo-extruded bg-surface flex min-h-[380px] flex-col rounded-2xl p-6 md:col-span-8">
          <div className="mb-6 flex items-center justify-between">
            <h2 className="font-display text-title-lg text-primary flex items-center gap-2 font-bold">
              <Icon name="neurology" className="text-primary-container" /> Neural Image Analysis
            </h2>
            <span className="bg-surface-container-high font-label text-on-surface-variant flex items-center gap-2 rounded-full px-3 py-1 text-[11px]">
              <span className="bg-secondary h-2 w-2 animate-pulse rounded-full" /> Processing MRI-T2
            </span>
          </div>
          {/* Stylized scan surface */}
          <div className="neo-pressed relative flex-1 overflow-hidden rounded-2xl bg-primary-container">
            <div
              className="absolute inset-0 opacity-70"
              style={{
                background:
                  'radial-gradient(circle at 45% 40%, rgba(0,210,253,0.35), transparent 45%), radial-gradient(circle at 60% 65%, rgba(69,123,157,0.35), transparent 40%), radial-gradient(circle at 50% 50%, rgba(176,200,235,0.12), transparent 70%)',
              }}
            />
            <div className="from-secondary/25 animate-scanline absolute inset-x-0 top-0 h-1/4 bg-gradient-to-b to-transparent" />
            {/* Anomaly node */}
            <div className="group absolute top-[34%] left-[42%]">
              <div className="bg-error h-4 w-4 cursor-pointer rounded-full shadow-[0_0_16px_var(--color-error)]" />
              <div className="glassmorphism pointer-events-none absolute top-6 left-1/2 w-52 -translate-x-1/2 rounded-lg p-3 opacity-0 shadow-lg transition-opacity duration-300 group-hover:opacity-100">
                <div className="font-label text-error text-[10px] font-bold">ANOMALY DETECTED</div>
                <div className="font-body text-on-surface mt-1 text-xs">
                  Minor hyperintensity in the left frontal lobe. Probability 87%.
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Agentic Feed */}
        <section className="neo-extruded bg-surface rounded-2xl p-6 md:col-span-6">
          <h2 className="font-display text-title-lg text-primary mb-4 flex items-center gap-2 font-bold">
            <Icon name="memory" className="text-secondary" /> Agentic Feed
          </h2>
          <div className="max-h-[320px] space-y-4 overflow-y-auto pr-2">
            {FEED.map((item) => (
              <div
                key={item.time}
                className={`flex items-start gap-3 border-l-2 pl-3 ${
                  item.alert ? 'border-error' : 'border-secondary'
                }`}
              >
                <div
                  className={`mt-0.5 flex-shrink-0 rounded-full p-1.5 ${
                    item.alert ? 'bg-error/10 text-error' : 'bg-secondary/10 text-secondary'
                  }`}
                >
                  <Icon name={item.icon} className="text-base" />
                </div>
                <div>
                  <div className="font-label text-on-surface-variant mb-1 text-[11px]">
                    {item.time}
                  </div>
                  <div className="font-body text-body-sm text-on-surface bg-surface-container-low border-outline-variant/20 rounded-r-xl rounded-bl-xl border p-3">
                    {item.body}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Recommendations */}
        <section className="neo-extruded bg-surface flex flex-col rounded-2xl p-6 md:col-span-6">
          <h2 className="font-display text-title-lg text-primary mb-4 flex items-center gap-2 font-bold">
            <Icon name="checklist" className="text-secondary" /> Recommendations
          </h2>
          <div className="flex-1 space-y-3">
            {RECOMMENDATIONS.map((rec) => (
              <label
                key={rec.title}
                className="neo-pressed flex cursor-pointer items-start gap-3 rounded-xl p-4 transition-colors"
              >
                <input
                  type="checkbox"
                  className="accent-secondary mt-1 h-4 w-4 flex-shrink-0 rounded"
                />
                <div>
                  <div className="font-body text-body-md text-primary font-bold">{rec.title}</div>
                  <div className="font-body text-body-sm text-on-surface-variant mt-0.5">
                    {rec.body}
                  </div>
                </div>
              </label>
            ))}
          </div>
          <button className="shadow-neo-base bg-primary-container text-on-primary font-label text-label-caps mt-5 flex items-center justify-center gap-2 rounded-full py-3 font-bold transition-transform active:scale-[0.98]">
            Approve Selected
            <Icon name="arrow_forward" className="text-base" />
          </button>
        </section>
      </div>
    </div>
  )
}
