import reference from '../data/reference.json'
import type { EligibilityLane, EligibilityResult } from '../types'

const LADDER: { lane: EligibilityLane; minimum: number; label: string }[] = [
  { lane: 'direct', minimum: 0, label: 'Direct Plans' },
  { lane: 'pms', minimum: reference.sebi_minimums.pms, label: 'PMS' },
  { lane: 'aif', minimum: reference.sebi_minimums.aif, label: 'AIF' },
  { lane: 'uhni', minimum: reference.sebi_minimums.uhni, label: 'UHNI Advisory' },
]

const RANK: Record<EligibilityLane, number> = {
  direct: 0,
  pms: 1,
  aif: 2,
  uhni: 3,
}

export function runEligibility(investableCorpus: number): EligibilityResult {
  const ladder = LADDER.map((row) => ({
    ...row,
    eligible: investableCorpus >= row.minimum,
  }))
  const eligible = ladder.filter((r) => r.eligible).map((r) => r.lane)
  const blocked = ladder.filter((r) => !r.eligible && r.lane !== 'direct').map((r) => r.lane)
  const highestEligible = eligible.reduce((best, lane) =>
    RANK[lane] > RANK[best] ? lane : best,
  )

  return {
    investableCorpus,
    highestEligible,
    eligible,
    blocked,
    ladder,
  }
}
