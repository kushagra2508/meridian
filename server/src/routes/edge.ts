import { Router } from 'express'

type Figure = { key: string; value: number; badge?: { tier: string; label: string } }
type PositionIn = {
  agent: string
  stance: string
  figures: Figure[]
  referencesAgent: string | null
  scopeLimits: string[]
}

const CLAIMS: Record<string, string> = {
  'planner:PROPOSES':
    'Reallocate idle cash into equity funds to close the projected shortfall before the deadline.',
  'planner:CONDITIONS':
    'The goal clears on the current path, subject to the equity-cap and lock-in constraints already priced.',
  'planner:CONCEDES':
    'The stated goal is already funded; no portfolio change is required on feasibility grounds.',
  'tax:OBJECTS':
    'Realising the proposed switch triggers tax above two percent of corpus under the cited sections.',
  'tax:CONDITIONS':
    'Tax on the proposed switch stays within the two-percent corpus threshold after exemptions.',
  'fees:OBJECTS':
    'Distributor-held mutual funds still extract recurring TER drag that compounds against the goal.',
  'fees:CONCEDES':
    'No mutual-fund distributor drag applies on this observed book.',
  'rethink:PROPOSES':
    'The deadline cannot be met inside the equity cap; slip, shrink, or top-up must reprice the goal.',
}

function figureLine(figures: Figure[], key: string): string | null {
  const hit = figures.find((f) => f.key === key)
  if (!hit) return null
  return `${key}=${Math.round(hit.value)}`
}

export const edgeRouter = Router()

edgeRouter.post('/prose', (req, res) => {
  const positions = (req.body?.positions ?? []) as PositionIn[]
  if (!Array.isArray(positions) || positions.length === 0) {
    res.status(400).json({ error: 'positions_required' })
    return
  }

  const prose = positions.map((p, index) => {
    const key = `${p.agent}:${p.stance}`
    const claim =
      CLAIMS[key] ??
      `${p.agent} holds ${p.stance}` +
        (figureLine(p.figures, 'totalTax') || figureLine(p.figures, 'annualDrag')
          ? ` (${figureLine(p.figures, 'totalTax') ?? figureLine(p.figures, 'annualDrag')}).`
          : '.')
    const opening =
      index === 0
        ? null
        : p.referencesAgent
          ? `${p.referencesAgent} set the prior claim.`
          : 'Prior agent spoke.'
    return { agent: p.agent, claim, opening }
  })

  res.json({ prose, source: 'template' })
})
