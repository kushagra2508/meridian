import type { LedgerRow, Verdict, VerdictState } from '../types'

export type PathDraft = {
  path: string
  label: string
  netRupees: number
  taxCost: number
  annualDragSaved: number
  goalProb: number
  illiquidPct: number
  tags?: string[]
  notes?: string[]
}

export function rankPaths(drafts: PathDraft[]): LedgerRow[] {
  const sorted = [...drafts].sort((a, b) => {
    if (b.netRupees !== a.netRupees) return b.netRupees - a.netRupees
    return a.taxCost - b.taxCost
  })
  return sorted.map((row, i) => ({
    path: row.path,
    label: row.label,
    netRupees: row.netRupees,
    taxCost: row.taxCost,
    annualDragSaved: row.annualDragSaved,
    goalProb: row.goalProb,
    illiquidPct: row.illiquidPct,
    rank: i + 1,
    tags: row.tags ?? [],
    notes: row.notes ?? [],
  }))
}

export function buildVerdict(
  state: VerdictState,
  paths: LedgerRow[],
  survivingObjections: string[],
): Verdict {
  return {
    state,
    paths,
    survivingObjections,
    summary:
      state === 'goal_clears'
        ? 'Goal Clears'
        : 'Repriced goals — deadline unreachable inside constraints',
  }
}
