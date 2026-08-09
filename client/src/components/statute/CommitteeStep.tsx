import { useEffect, useMemo } from 'react'
import { useAgentRun } from '../../hooks/useAgentRun'
import { useSequentialVerdicts } from '../../hooks/useSequentialVerdicts'
import { committeeToReports } from '../../statute/mapToReports'
import { useStatuteDispatch, useStatuteState } from '../../statute/store'
import { Icon } from '../Icon'
import { AgentConsole } from '../intelligence/AgentConsole'
import { AgentReports } from '../intelligence/AgentReports'

const DEFAULT_PROMPT = 'Can we fund the stated goal with the current plan?'

export function CommitteeStep() {
  const { committee, handoff, proseSource } = useStatuteState()
  const dispatch = useStatuteDispatch()
  const {
    items,
    reports,
    status,
    running,
    error: agentError,
    start,
    halt,
  } = useAgentRun(DEFAULT_PROMPT)

  const deskReports = useMemo(() => committeeToReports(committee), [committee])
  const { visibleReports, expectedCount, pendingAgent } = useSequentialVerdicts(
    deskReports,
    reports,
  )

  const committeeKey = useMemo(
    () =>
      committee.positions
        .map((p) => `${p.agent}:${p.stance}:${p.figures.map((f) => f.value).join(',')}`)
        .join('|'),
    [committee],
  )

  useEffect(() => {
    start(DEFAULT_PROMPT)
  }, [committeeKey, start])

  const hasReframe = committee.positions.some((p) => p.agent === 'reframe')

  return (
    <div className="flex flex-1 flex-col gap-gutter overflow-y-auto p-margin-page lg:flex-row lg:overflow-hidden">
      <section className="flex flex-1 flex-col gap-gutter overflow-y-auto pb-stack-lg pr-1">
        <header className="mb-stack-compact border-b border-rule pb-stack-compact">
          <h1 className="flex items-center gap-2 font-display-lg text-display-lg text-primary">
            Deliberation
            <Icon name="gavel" className="text-[28px] text-primary" />
          </h1>
          <p className="mt-2 font-body-md text-body-md text-on-surface-variant">
            {handoff.persona} · Feasibility → Statute → Channel
            {hasReframe ? ' → Reframe' : ''}. Verdict cards appear as each stage completes.
          </p>
          {proseSource === 'cached' ? (
            <p className="mt-2 inline-flex bg-surface-container-high px-2 py-1 font-label-caps text-label-caps uppercase tracking-wider text-on-surface-variant">
              Reasoning cached
            </p>
          ) : null}
        </header>

        <AgentReports
          reports={visibleReports}
          running={running}
          statusLabel={status.label}
          expectedCount={expectedCount}
          pendingAgent={pendingAgent}
        />

        <div className="flex flex-wrap justify-between gap-3 border-t border-rule pt-stack-dense">
          <button
            type="button"
            onClick={() => dispatch({ type: 'SET_SCREEN', screen: 'position' })}
            className="rounded border border-rule px-6 py-2 font-label-caps text-label-caps uppercase text-on-surface-variant transition-colors hover:bg-surface-variant"
          >
            Adjust position
          </button>
          <button
            type="button"
            onClick={() => dispatch({ type: 'SET_SCREEN', screen: 'verdict' })}
            className="inline-flex items-center gap-2 rounded bg-primary px-6 py-2 font-label-caps text-label-caps uppercase text-on-primary transition-colors hover:bg-ink"
          >
            View verdict
            <Icon name="arrow_forward" className="text-[16px]" />
          </button>
        </div>
      </section>

      <AgentConsole
        items={items}
        status={status}
        running={running}
        error={agentError}
        onStart={start}
        onHalt={halt}
      />
    </div>
  )
}
