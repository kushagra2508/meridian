import { useCallback, useRef, useState } from 'react'
import { Icon } from '../components/Icon'
import { BalanceChart } from '../components/dashboard/BalanceChart'
import { HealthGauge } from '../components/dashboard/HealthGauge'
import { PersonaSelector } from '../components/dashboard/PersonaSelector'
import { useAsyncData } from '../hooks/useAsyncData'
import { getPortfolioSeries, getPortfolioSummary } from '../lib/api'
import { formatCurrency, formatSignedPct } from '../lib/format'
import { SERIES_RANGES, type Persona, type SeriesRange } from '../lib/types'

export function Dashboard() {
  const [range, setRange] = useState<SeriesRange>('1M')
  const [persona, setPersona] = useState<Persona | null>(null)
  const positionRef = useRef<HTMLDivElement>(null)

  const scrollToPosition = useCallback(() => {
    positionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  const summaryState = useAsyncData(
    useCallback((signal: AbortSignal) => getPortfolioSummary(signal), []),
  )
  const seriesState = useAsyncData(
    useCallback((signal: AbortSignal) => getPortfolioSeries(range, signal), [range]),
  )

  const summary = summaryState.data
  const series = seriesState.data
  const failed = summaryState.error ?? seriesState.error

  return (
    <main className="z-10 flex-1 overflow-y-auto bg-background p-gutter pt-24">
      {failed ? (
        <div className="mb-stack-md flex items-center gap-2 rounded border border-error/40 bg-error-container px-4 py-3 text-body text-on-error-container">
          <Icon name="error" className="text-[18px]" />
          Could not reach the Lumina API. Start it with <code className="mx-1">npm run dev</code>
          and reload.
        </div>
      ) : null}

      <PersonaSelector onPersonaChange={setPersona} onContinue={scrollToPosition} />

      <div
        ref={positionRef}
        className="mb-stack-lg flex scroll-mt-24 flex-col items-start justify-between gap-4 md:flex-row md:items-end"
      >
        <div>
          {persona ? (
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-outline-variant bg-surface-container px-3 py-1 font-table-header text-table-header uppercase tracking-[0.1em] text-on-surface-variant">
              <Icon name="person" className="text-[14px] text-primary" />
              Planning for {persona.id} · {persona.name}
            </div>
          ) : null}
          <h2 className="max-w-3xl font-page-title text-page-title tracking-tight text-on-surface">
            {summary?.headline ?? 'Loading your portfolio position...'}
          </h2>
          <p className="mt-2 font-subtitle text-subtitle text-on-surface-variant">
            {summary?.subheadline ?? 'Fetching the latest AI analysis.'}
          </p>
        </div>

        <div className="flex gap-3">
          <button
            type="button"
            className="rounded border border-primary px-6 py-2 font-body text-primary transition-colors hover:bg-primary/10"
          >
            Download Report
          </button>
          <button
            type="button"
            className="flex items-center gap-2 rounded bg-primary px-6 py-2 font-body font-semibold text-on-primary transition-opacity hover:opacity-90"
          >
            <Icon name="add" className="text-sm" />
            Add Funds
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-gutter md:grid-cols-12">
        <section className="glass-panel col-span-1 flex h-[420px] flex-col rounded-xl p-gutter md:col-span-8">
          <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="mb-1 font-section-kicker text-section-kicker uppercase text-on-surface-variant">
                Total Balance
              </div>
              <div className="font-page-title text-[40px] leading-none text-primary md:text-[48px]">
                {summary ? formatCurrency(summary.totalBalance) : '—'}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="flex items-center rounded bg-secondary/10 px-2 py-0.5 font-body text-secondary">
                  <Icon name="trending_up" className="mr-1 text-[16px]" />
                  {summary ? formatSignedPct(summary.ytdChangePct) : '—'} (
                  {summary?.periodLabel ?? 'YTD'})
                </span>
                <span className="font-body text-on-surface-variant">
                  {series ? `${formatSignedPct(series.changePct)} over ${range}` : 'vs last year'}
                </span>
              </div>
            </div>

            <div
              role="tablist"
              aria-label="Chart range"
              className="flex rounded border border-outline-variant bg-surface-container p-1"
            >
              {SERIES_RANGES.map((option) => (
                <button
                  key={option}
                  type="button"
                  role="tab"
                  aria-selected={range === option}
                  onClick={() => setRange(option)}
                  className={`rounded px-3 py-1 text-body transition-colors ${
                    range === option
                      ? 'bg-surface font-medium text-primary shadow'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>

          <div className="relative min-h-0 flex-1">
            {series ? (
              <BalanceChart series={series} />
            ) : (
              <div className="flex h-full items-center justify-center font-body text-on-surface-variant">
                {seriesState.loading ? 'Loading chart...' : 'No data available'}
              </div>
            )}
          </div>
        </section>

        <section className="glass-panel col-span-1 flex h-[420px] flex-col justify-between rounded-xl p-gutter md:col-span-4">
          <div className="flex items-start justify-between gap-2">
            <div className="font-section-kicker text-section-kicker uppercase text-on-surface-variant">
              {summary?.healthLabel ?? 'Portfolio health'}
            </div>
            <Icon name="health_and_safety" className="text-secondary" filled />
          </div>

          <HealthGauge score={summary?.healthScore ?? 0} />

          <div className="mt-4 rounded border border-outline-variant bg-surface p-3">
            <div className="flex items-start gap-2">
              <Icon name="tips_and_updates" className="mt-0.5 text-[18px] text-primary" />
              <p className="font-body text-body leading-tight text-on-surface-variant">
                {summary?.healthAdvice ?? 'Awaiting the latest AI assessment.'}
              </p>
            </div>
          </div>
        </section>

        <section className="glass-panel col-span-1 rounded-xl p-gutter md:col-span-8">
          <h3 className="mb-stack-md font-panel-header text-panel-header text-primary">
            Allocation
          </h3>
          <ul className="space-y-stack-sm">
            {(summary?.allocations ?? []).map((allocation) => (
              <li key={allocation.label} className="flex items-center gap-4">
                <span className="w-32 shrink-0 font-body text-body text-on-surface">
                  {allocation.label}
                </span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-container-high">
                  <div
                    className="h-full rounded-full bg-primary transition-[width] duration-700"
                    style={{ width: `${allocation.weight}%` }}
                  />
                </div>
                <span className="w-12 text-right font-table-header text-table-header text-on-surface-variant">
                  {allocation.weight}%
                </span>
                <span
                  className={`w-16 text-right font-table-header text-table-header ${
                    allocation.changePct >= 0 ? 'text-secondary' : 'text-error'
                  }`}
                >
                  {formatSignedPct(allocation.changePct)}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="glass-panel col-span-1 rounded-xl p-gutter md:col-span-4">
          <h3 className="mb-stack-md font-panel-header text-panel-header text-primary">
            Watchlist
          </h3>
          <ul className="space-y-stack-sm">
            {(summary?.watchlist ?? []).map((holding) => (
              <li
                key={holding.ticker}
                className="flex items-center justify-between rounded border border-outline-variant bg-surface p-3"
              >
                <div>
                  <div className="font-table-header text-[11px] uppercase text-on-surface">
                    {holding.ticker}
                  </div>
                  <div className="font-footnote text-footnote text-on-surface-variant">
                    {holding.name}
                  </div>
                </div>
                <span
                  className={`font-table-header text-[11px] ${
                    holding.changePct >= 0 ? 'text-primary-container' : 'text-error'
                  }`}
                >
                  {formatSignedPct(holding.changePct)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  )
}
