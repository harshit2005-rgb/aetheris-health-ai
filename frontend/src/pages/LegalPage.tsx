import MarketingNav from '@/components/layout/MarketingNav'
import MarketingFooter from '@/components/layout/MarketingFooter'
import type { LegalDoc } from '@/content/legal'

export default function LegalPage({ doc }: { doc: LegalDoc }) {
  return (
    <div className="min-h-screen overflow-x-hidden">
      <MarketingNav />

      <main className="px-container-padding mx-auto max-w-3xl pt-28 pb-16 md:pt-36">
        <header className="border-outline-variant/40 mb-10 border-b pb-8">
          <p className="font-label text-label-caps text-outline mb-3">
            Last updated · {doc.updated}
          </p>
          <h1 className="font-display text-headline-xl text-primary">{doc.title}</h1>
          <p className="font-body text-body-md text-on-surface-variant mt-4">{doc.intro}</p>
          {/* Remove once final language is issued by legal counsel. */}
          <p className="neo-pressed bg-surface text-on-surface-variant font-body mt-6 rounded-xl px-4 py-3 text-xs">
            This page is a working template. Final legal language will be issued by Aetheris counsel.
          </p>
        </header>

        <div className="space-y-10">
          {doc.sections.map((section) => (
            <section key={section.heading}>
              <h2 className="font-display text-title-lg text-primary mb-3 font-bold">
                {section.heading}
              </h2>
              <div className="space-y-3">
                {section.body.map((p, i) => (
                  <p
                    key={i}
                    className="font-body text-body-md text-on-surface-variant leading-relaxed"
                  >
                    {p}
                  </p>
                ))}
              </div>
            </section>
          ))}
        </div>
      </main>

      <MarketingFooter />
    </div>
  )
}
