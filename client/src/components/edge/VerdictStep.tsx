import { useState } from 'react'
import { formatINR, formatPct } from '../../edge/lib/format'
import { useEdgeDispatch, useEdgeState } from '../../edge/store'
import type { LedgerRow } from '../../edge/types'

export function VerdictStep() {
  const { committee } = useEdgeState()
  const dispatch = useEdgeDispatch()
  const { verdict } = committee
  const [selected, setSelected] = useState<string | null>(null)

  return (
    <div className="flex flex-1 flex-col overflow-y-auto">
      <header className="border-b border-rule px-margin-page py-stack-loose">
        <h1 className="mb-stack-compact font-display-lg text-display-lg text-ink">Verdict</h1>
        <p className="font-body-lg text-body-lg text-on-surface-variant">
          {verdict.state === 'goal_clears' ? 'State A: Goal clears' : 'State B: Repriced goals'}
        </p>
      </header>

      <section className="flex flex-1 flex-col gap-stack-dense px-margin-page py-stack-loose">
        {verdict.paths.map((path) => (
          <PathCard
            key={path.path}
            path={path}
            selected={selected === path.path}
            dimmed={selected !== null && selected !== path.path}
            onSelect={() => setSelected(path.path)}
          />
        ))}

        {verdict.survivingObjections.length > 0 ? (
          <div className="mt-stack-loose flex flex-col gap-stack-compact border-l-4 border-secondary-container bg-surface-container-low p-stack-dense">
            {verdict.survivingObjections.map((objection) => (
              <div key={objection} className="flex flex-wrap items-center gap-stack-dense">
                <span className="bg-secondary-container px-2 py-1 font-label-caps text-label-caps uppercase text-on-secondary-container">
                  Surviving objection
                </span>
                <span className="font-data-md text-data-md text-ink">{objection}</span>
              </div>
            ))}
          </div>
        ) : null}

        <div className="mt-stack-loose flex flex-wrap items-center justify-between gap-stack-dense border-t border-rule pt-stack-dense">
          <button
            type="button"
            onClick={() => dispatch({ type: 'SET_SCREEN', screen: 'committee' })}
            className="rounded border border-rule px-6 py-2 font-label-caps text-label-caps uppercase text-on-surface-variant transition-colors hover:bg-surface-variant"
          >
            Back to deliberation
          </button>
          <button
            type="button"
            onClick={() => dispatch({ type: 'SET_SCREEN', screen: 'position' })}
            className="rounded bg-primary px-6 py-2 font-label-caps text-label-caps uppercase text-on-primary transition-colors hover:bg-ink"
          >
            Adjust position and re-run
          </button>
        </div>

        <div className="mt-auto pt-stack-loose text-center">
          <p className="font-headline-sm text-headline-sm italic text-on-surface-variant">
            &ldquo;No agent issued this verdict. It is the ledger resolving.&rdquo;
          </p>
        </div>
      </section>
    </div>
  )
}

function PathCard({
  path,
  selected,
  dimmed,
  onSelect,
}: {
  path: LedgerRow
  selected: boolean
  dimmed: boolean
  onSelect: () => void
}) {
  return (
    <article
      className={`flex flex-col items-start gap-stack-loose border bg-surface p-stack-dense transition-opacity md:flex-row md:items-center ${
        selected ? 'border-primary' : 'border-rule'
      } ${dimmed ? 'opacity-70 hover:opacity-100' : ''}`}
    >
      <div className="flex min-w-[200px] items-center gap-stack-dense">
        <div className="font-display-lg text-display-lg text-outline">
          {String(path.rank).padStart(2, '0')}
        </div>
        <div>
          <div className="font-headline-md text-headline-md text-ink">{path.label}</div>
          {path.tags.map((tag) => (
            <span
              key={tag}
              className="mt-1 inline-block bg-tertiary-fixed px-1.5 py-0.5 font-citation text-citation uppercase tracking-widest text-primary"
            >
              {tag}
            </span>
          ))}
        </div>
      </div>

      <dl className="grid w-full flex-1 grid-cols-2 gap-stack-dense lg:grid-cols-4">
        <Metric label="Goal prob." value={formatPct(path.goalProb, 1)} tone="text-primary" />
        <Metric label="Tax cost" value={formatINR(path.taxCost)} tone="text-secondary" />
        <Metric
          label="Annual drag saved"
          value={formatINR(path.annualDragSaved)}
          tone="text-primary"
        />
        <Metric label="Illiquid exp." value={formatPct(path.illiquidPct, 0)} tone="text-ink" />
      </dl>

      <div className="mt-stack-compact flex w-full justify-end border-t border-rule pt-stack-compact md:mt-0 md:w-auto md:border-t-0 md:pt-0">
        <button
          type="button"
          onClick={onSelect}
          className={`whitespace-nowrap rounded border px-6 py-2 font-label-caps text-label-caps uppercase transition-colors ${
            selected
              ? 'border-primary bg-primary text-on-primary'
              : 'border-rule text-on-surface-variant hover:bg-surface-variant'
          }`}
        >
          {selected ? 'Path selected' : 'Select path'}
        </button>
      </div>
    </article>
  )
}

function Metric({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="flex flex-col gap-base border-l border-rule pl-stack-compact">
      <dt className="font-label-caps text-label-caps uppercase text-on-surface-variant">{label}</dt>
      <dd className={`font-data-md text-data-md ${tone}`}>{value}</dd>
    </div>
  )
}
