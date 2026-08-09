import { useCallback } from 'react'
import { Icon } from '../components/Icon'
import { AgentConsole } from '../components/intelligence/AgentConsole'
import { useAsyncData } from '../hooks/useAsyncData'
import { getIntelligenceReports } from '../lib/api'
import { formatSignedPct } from '../lib/format'
import type { RiskParity, Sentiment, SentimentRegion } from '../lib/types'

const barTone: Record<RiskParity['bars'][number]['tone'], string> = {
  primary: 'bg-primary/40 border-primary',
  secondary: 'bg-secondary/40 border-secondary',
  error: 'bg-error/40 border-error',
}

const footnoteTone: Record<RiskParity['footnotes'][number]['tone'], string> = {
  neutral: 'text-on-surface-variant',
  positive: 'text-secondary',
  negative: 'text-error',
}

export function Intelligence() {
  const { data, loading, error } = useAsyncData(
    useCallback((signal: AbortSignal) => getIntelligenceReports(signal), []),
  )

  return (
    <main className="flex flex-1 flex-col gap-gutter overflow-hidden bg-surface p-gutter pt-24 lg:h-screen lg:flex-row">
      <section className="flex flex-1 flex-col gap-gutter overflow-y-auto pb-stack-lg pr-1">
        <header className="mb-stack-sm">
          <h2 className="flex items-center gap-2 font-page-title text-page-title text-primary">
            Intelligence Hub
            <Icon name="auto_awesome" className="text-[24px] text-primary" />
          </h2>
          <p className="mt-2 font-subtitle text-subtitle text-on-surface-variant">
            Real-time quantitative analysis and narrative reporting.
          </p>
        </header>

        {error ? (
          <div className="flex items-center gap-2 rounded border border-error/40 bg-error-container px-4 py-3 text-body text-on-error-container">
            <Icon name="error" className="text-[18px]" />
            Could not load intelligence reports. Check that the API is running.
          </div>
        ) : null}

        {loading || !data ? (
          <div className="glass-panel-light flex h-40 items-center justify-center rounded-xl font-body text-on-surface-variant">
            Loading reports...
          </div>
        ) : (
          <>
            <article className="glass-panel-light ai-glow relative flex flex-col gap-stack-md overflow-hidden rounded-xl p-gutter">
              <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary-fixed/30 to-transparent" />

              <div className="z-10 flex items-start justify-between gap-4">
                <div>
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-primary-container bg-primary-container px-3 py-1 font-section-kicker text-[11px] uppercase tracking-wider text-on-primary-container">
                      {data.alpha.tag}
                    </span>
                    <span className="font-footnote text-footnote text-on-surface-variant">
                      ID: {data.alpha.id}
                    </span>
                  </div>
                  <h3 className="font-panel-header text-panel-header text-on-background">
                    {data.alpha.title}
                  </h3>
                </div>
                <button
                  type="button"
                  aria-label="Share report"
                  className="text-on-surface-variant transition-colors hover:text-primary"
                >
                  <Icon name="ios_share" />
                </button>
              </div>

              <div className="z-10 font-body text-body text-on-surface-variant">
                {data.alpha.paragraphs.map((paragraph) => (
                  <p key={paragraph.slice(0, 32)} className="mb-3 last:mb-0">
                    {paragraph}
                  </p>
                ))}
              </div>

              <div className="z-10 mt-4 flex flex-wrap items-center gap-stack-md border-t border-outline-variant pt-stack-md">
                <button
                  type="button"
                  className="flex items-center gap-2 rounded-lg border border-primary bg-primary px-4 py-2 font-body text-body text-on-primary transition-colors hover:bg-primary-container"
                >
                  <Icon name="add" className="text-[18px]" />
                  Add to Portfolio Sim
                </button>
                <button
                  type="button"
                  className="flex items-center gap-1 font-body text-body text-on-surface-variant transition-colors hover:text-primary"
                >
                  View Underlying Data
                  <Icon name="arrow_forward" className="text-[16px]" />
                </button>
              </div>
            </article>

            <div className="grid grid-cols-1 gap-gutter md:grid-cols-2">
              <div className="glass-panel-light flex flex-col rounded-xl p-gutter">
                <div className="mb-stack-md flex items-center justify-between gap-2">
                  <h4 className="flex items-center gap-2 font-panel-header text-panel-header text-primary">
                    <Icon name="balance" className="text-secondary" />
                    {data.riskParity.title}
                  </h4>
                  <span className="rounded bg-surface-container-high px-2 py-1 font-footnote text-footnote uppercase tracking-wider text-on-surface-variant">
                    {data.riskParity.status}
                  </span>
                </div>

                <div className="mb-stack-md flex h-32 w-full items-end gap-2 overflow-hidden rounded-lg border border-outline-variant bg-surface-container-low p-2">
                  {data.riskParity.bars.map((bar) => (
                    <div
                      key={bar.label}
                      title={`${bar.label}: ${bar.value}`}
                      style={{ height: `${bar.value}%` }}
                      className={`w-1/4 rounded-t-sm border-t-2 transition-[height] duration-700 ${barTone[bar.tone]}`}
                    />
                  ))}
                </div>

                <div className="flex justify-between font-table-header text-table-header uppercase">
                  {data.riskParity.footnotes.map((note) => (
                    <span key={note.label} className={footnoteTone[note.tone]}>
                      {note.label}
                    </span>
                  ))}
                </div>
              </div>

              <SentimentPanel sentiment={data.sentiment} />
            </div>
          </>
        )}
      </section>

      <AgentConsole />
    </main>
  )
}

function sentimentClasses(score: number): string {
  if (score >= 2) return 'bg-primary/20 border-primary/50 text-primary font-bold'
  if (score > 0.5) return 'bg-primary-fixed/40 border-primary-fixed/80 text-primary font-bold'
  if (score > 0) return 'bg-primary-fixed/20 border-primary-fixed/50 text-primary'
  if (score === 0) return 'bg-surface-container-high border-outline-variant text-on-surface-variant'
  if (score > -1) return 'bg-error-container border-error/50 text-error'
  return 'bg-error/20 border-error/80 text-error font-bold'
}

function SentimentPanel({ sentiment }: { sentiment: Sentiment }) {
  return (
    <div className="glass-panel-light flex flex-col rounded-xl p-gutter">
      <div className="mb-stack-md flex items-center justify-between">
        <h4 className="flex items-center gap-2 font-panel-header text-panel-header text-primary">
          <Icon name="public" className="text-primary-fixed-dim" />
          {sentiment.title}
        </h4>
      </div>

      <div className="mb-stack-md grid h-32 grid-cols-3 grid-rows-2 gap-2">
        {sentiment.regions.map((region: SentimentRegion) => (
          <div
            key={region.code}
            className={`flex items-center justify-center rounded border font-table-header text-table-header ${sentimentClasses(region.score)}`}
          >
            {region.code} {formatSignedPct(region.score).replace('%', '')}
          </div>
        ))}
      </div>

      <p className="mt-auto font-body text-body text-on-surface-variant">{sentiment.summary}</p>
    </div>
  )
}
