import type { AgentReportCard } from '../hooks/useAgentRun'
import { displayAgent } from './agents'
import cachedProse from './data/cachedProse.json'
import { formatINR, formatPct } from './lib/format'
import type { AgentId, AgentPosition, CommitteeResult, LedgerRow, Stance } from './types'

function formatFigure(key: string, value: number): string {
  if (key.toLowerCase().includes('return') || key === 'blendedReturn') {
    return formatPct(value, 2)
  }
  if (key === 'slip_year') return `${Math.round(value)} mo`
  return formatINR(value)
}

function cachedClaim(agent: AgentId, stance: Stance): string | null {
  const key = `${agent}:${stance}` as keyof typeof cachedProse
  return cachedProse[key]?.claim ?? null
}

export function committeeToReports(committee: CommitteeResult): AgentReportCard[] {
  const now = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
  const agentCards = committee.positions.map((position) => positionToReport(position, now))
  const verdictCard = verdictToReport(committee, now)
  return [...agentCards, verdictCard]
}

function positionToReport(position: AgentPosition, at: string): AgentReportCard {
  const label = displayAgent(position.agent)
  const claim = cachedClaim(position.agent, position.stance)
  return {
    id: `edge-${position.agent}`,
    at,
    agent: label,
    title: position.stance,
    headline:
      claim ??
      position.scopeLimits[0] ??
      `${label} holds ${position.stance} on the computed figures.`,
    verdict: position.stance,
    metrics: position.figures.slice(0, 4).map((fig) => ({
      label: fig.key,
      value: formatFigure(fig.key, fig.value),
    })),
    bullets: [
      ...(position.referencesAgent
        ? [`References ${displayAgent(position.referencesAgent)}`]
        : []),
      ...position.scopeLimits.slice(0, 2),
    ],
  }
}

function verdictToReport(committee: CommitteeResult, at: string): AgentReportCard {
  const top = committee.ledger[0] as LedgerRow | undefined
  return {
    id: 'edge-verdict',
    at,
    agent: 'Verdict',
    title: committee.verdict.state === 'goal_clears' ? 'Goal Clears' : 'Repriced Goals',
    headline: committee.verdict.summary,
    verdict: committee.verdict.state,
    metrics: top
      ? [
          { label: 'Top path', value: top.label },
          { label: 'Goal prob.', value: formatPct(top.goalProb, 1) },
          { label: 'Tax cost', value: formatINR(top.taxCost) },
          { label: 'Drag saved', value: formatINR(top.annualDragSaved) },
        ]
      : [],
    bullets: [
      ...committee.verdict.survivingObjections,
      'No agent issued this verdict. It is the ledger resolving.',
      ...committee.ledger.slice(0, 3).map((p) => `#${p.rank} ${p.label}`),
    ],
  }
}
