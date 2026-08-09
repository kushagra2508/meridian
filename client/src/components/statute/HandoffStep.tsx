import type { ReactNode } from 'react'
import reference from '../../statute/data/reference.json'
import { useStatuteDispatch, useStatuteState } from '../../statute/store'

const RECEIVED_ON = new Date(reference.generated_at)
  .toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
  .toUpperCase()

export function HandoffStep() {
  const { handoff } = useStatuteState()
  const dispatch = useStatuteDispatch()

  return (
    <article className="flex w-full flex-col border border-rule bg-background">
      <header className="flex items-center border-b border-rule bg-surface-container-low px-stack-dense py-stack-compact">
        <h1 className="m-0 font-data-md text-[11px] uppercase tracking-wider text-on-surface-variant">
          Received from acquisition engine · {RECEIVED_ON}
        </h1>
      </header>

      <div className="flex flex-col p-margin-page">
        <dl className="mb-stack-dense grid grid-cols-1 gap-x-stack-dense gap-y-stack-dense sm:grid-cols-[200px_1fr]">
          <Row label="Persona">{handoff.persona}</Row>
          <Row label="Priority tier">{handoff.priorityTier}</Row>
          <Row label="Declared income">
            <span className="tracking-tight">{handoff.declaredIncomeLabel}</span>
          </Row>
          <Row label="Channel used">{handoff.channelUsed}</Row>
          <Row label="Pursue decision">
            <span className="inline-flex items-center rounded-[2px] bg-primary px-2 py-1 font-label-caps text-[10px] uppercase tracking-widest text-on-primary">
              {handoff.pursueDecision}
            </span>
          </Row>
          <Row label="Flagged events">
            <span className="flex flex-col gap-1">
              {handoff.futureEvents.length > 0 ? (
                handoff.futureEvents.map((event) => (
                  <span key={`${event.label}-${event.year}`}>
                    {event.label} ({event.year})
                  </span>
                ))
              ) : (
                <span className="text-on-surface-variant">None declared at intake</span>
              )}
            </span>
          </Row>
        </dl>

        <div className="mb-stack-loose mt-stack-dense">
          <p className="m-0 font-headline-sm text-[18px] italic text-on-surface-variant">
            Declared at intake. STATUTE re-tests against observed position.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-stack-loose border-t border-rule pt-stack-loose">
          <button
            type="button"
            onClick={() => dispatch({ type: 'SET_SCREEN', screen: 'position' })}
            className="rounded-[2px] bg-primary px-8 py-3 font-label-caps text-label-caps uppercase tracking-wider text-on-primary transition-colors hover:bg-ink focus:outline-none focus:ring-2 focus:ring-secondary-container focus:ring-offset-2 focus:ring-offset-background"
          >
            Continue to position
          </button>
          <button
            type="button"
            onClick={() => dispatch({ type: 'RESET' })}
            className="border-b border-secondary-container pb-[2px] font-label-caps text-label-caps uppercase tracking-wider text-on-surface-variant transition-colors hover:border-ink hover:text-ink focus:outline-none"
          >
            Build a new lead
          </button>
        </div>
      </div>
    </article>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="flex items-start pt-1 font-label-caps text-label-caps uppercase text-on-surface-variant">
        {label}
      </dt>
      <dd className="m-0 font-data-md text-data-md text-ink">{children}</dd>
    </>
  )
}
