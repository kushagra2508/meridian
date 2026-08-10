import type { ReactNode } from 'react'
import reference from '../../edge/data/reference.json'
import { listPersonas } from '../../edge/fromPersona'
import { CURRENT_RM, greeting } from '../../edge/rm'
import { useEdgeDispatch, useEdgeState } from '../../edge/store'

const RECEIVED_ON = new Date(reference.generated_at)
  .toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
  .toUpperCase()

export function HandoffStep() {
  const { handoff, personaId } = useEdgeState()
  const dispatch = useEdgeDispatch()
  const leads = listPersonas()
  const queued = leads.filter((lead) => lead.id !== personaId)

  return (
    <article className="flex w-full flex-col border border-rule bg-background">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-rule bg-surface-container-low px-stack-dense py-stack-compact">
        <h1 className="m-0 font-data-md text-[11px] uppercase tracking-wider text-on-surface-variant">
          Received from acquisition engine · {RECEIVED_ON}
        </h1>
        <p className="m-0 font-data-md text-[11px] uppercase tracking-wider text-on-surface-variant">
          {greeting()}, {CURRENT_RM.name} · {CURRENT_RM.desk}
        </p>
      </header>

      <div className="flex flex-col p-margin-page">
        <div className="mb-stack-loose flex flex-wrap items-baseline justify-between gap-2 border-b border-rule pb-stack-compact">
          <div>
            <p className="m-0 font-label-caps text-label-caps uppercase text-on-surface-variant">
              Lead
            </p>
            <h2 className="mt-1 font-headline-md text-headline-md text-primary">
              {handoff.clientName}
            </h2>
          </div>
          {queued.length > 0 ? (
            <div className="flex flex-col items-end gap-1">
              <p className="m-0 font-label-caps text-[10px] uppercase tracking-wider text-on-surface-variant">
                {queued.length} more in queue
              </p>
              <div className="flex flex-wrap justify-end gap-1.5">
                {queued.map((lead) => (
                  <button
                    key={lead.id}
                    type="button"
                    onClick={() => dispatch({ type: 'LOAD_PERSONA', id: lead.id })}
                    className="rounded border border-rule bg-surface px-2.5 py-1 font-label-caps text-[10px] uppercase tracking-wider text-on-surface-variant transition-colors hover:border-primary hover:text-primary"
                  >
                    {lead.name}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>

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
            Declared at intake. EDGE re-tests against observed position.
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
