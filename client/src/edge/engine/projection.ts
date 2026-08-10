import reference from '../data/reference.json'
import type { Alloc, AssetKey, Goal, Position } from '../types'

const ASSET_KEYS = Object.keys(reference.categories) as AssetKey[]
const STEP = 100_000
const EQUITY_CAP = 0.85
const BASE_YEAR = 2026

export type ProjectionResult = {
  n: number
  blendedReturn: number
  projected: number
  gap: number
  requiredReturn: number
  feasible: boolean
  proposedAlloc: Alloc
  switchAmount: number
  aifRuledOut: boolean
  aifRuleReason: string | null
  scopeLimits: string[]
}

export function yearsToGoal(goal: Goal): number {
  return goal.year - BASE_YEAR
}

export function normalizeAlloc(alloc: Alloc): Alloc {
  const sum = ASSET_KEYS.reduce((acc, key) => acc + (alloc[key] ?? 0), 0)
  if (sum <= 0) {
    return { ...alloc }
  }
  const next = { ...alloc }
  for (const key of ASSET_KEYS) {
    next[key] = (alloc[key] ?? 0) / sum
  }
  return next
}

/**
 * Move one sled in a fixed budget: `key` takes `value`, and the other classes
 * absorb the difference in proportion to how much they already hold, so the six
 * weights always sum to exactly 1 and no drag can push the book past 100%.
 * When the others are all empty there is no proportion to preserve, so the
 * remainder is spread evenly instead.
 */
export function setAllocBudgeted(alloc: Alloc, key: AssetKey, value: number): Alloc {
  const target = Math.min(1, Math.max(0, value))
  const others = ASSET_KEYS.filter((k) => k !== key)
  const othersSum = others.reduce((acc, k) => acc + (alloc[k] ?? 0), 0)
  const remainder = 1 - target

  const next = { ...alloc, [key]: target } as Alloc
  for (const k of others) {
    next[k] =
      othersSum > 0 ? ((alloc[k] ?? 0) / othersSum) * remainder : remainder / others.length
  }
  return next
}

export function blendedReturn(alloc: Alloc): number {
  const a = normalizeAlloc(alloc)
  return ASSET_KEYS.reduce((acc, key) => {
    const cagr = reference.categories[key]?.cagr ?? 0
    return acc + a[key] * cagr
  }, 0)
}

export function projectWealth(totalWealth: number, alloc: Alloc, n: number): number {
  const r = blendedReturn(alloc)
  return totalWealth * Math.pow(1 + r, Math.max(n, 0))
}

export function requiredReturn(totalWealth: number, goalAmount: number, n: number): number {
  if (totalWealth <= 0 || n <= 0) return Number.POSITIVE_INFINITY
  return Math.pow(goalAmount / totalWealth, 1 / n) - 1
}

function equityWeight(alloc: Alloc): number {
  return (alloc.equity_mf ?? 0) + (alloc.direct_equity ?? 0)
}

/** Shift fd_cash → equity_mf in ₹1L steps until projected ≥ goal or equity cap. */
export function reallocationSearch(
  position: Position,
  goal: Goal,
): {
  feasible: boolean
  proposedAlloc: Alloc
  switchAmount: number
  projected: number
} {
  const n = yearsToGoal(goal)
  let alloc = normalizeAlloc(position.alloc)
  let projected = projectWealth(position.totalWealth, alloc, n)
  if (projected >= goal.amount) {
    return { feasible: true, proposedAlloc: alloc, switchAmount: 0, projected }
  }

  let switchAmount = 0
  while (projected < goal.amount) {
    const fdRupees = alloc.fd_cash * position.totalWealth
    if (fdRupees < STEP) break
    if (equityWeight(alloc) >= EQUITY_CAP - 1e-9) break

    const move = Math.min(STEP, fdRupees)
    const moveFrac = move / position.totalWealth
    const room = EQUITY_CAP - equityWeight(alloc)
    const applied = Math.min(moveFrac, room)
    if (applied <= 0) break

    alloc = {
      ...alloc,
      fd_cash: alloc.fd_cash - applied,
      equity_mf: alloc.equity_mf + applied,
    }
    switchAmount += applied * position.totalWealth
    projected = projectWealth(position.totalWealth, alloc, n)
  }

  return {
    feasible: projected >= goal.amount - 1e-6,
    proposedAlloc: normalizeAlloc(alloc),
    switchAmount,
    projected,
  }
}

export function runProjection(position: Position, goal: Goal): ProjectionResult {
  const n = yearsToGoal(goal)
  const alloc = normalizeAlloc(position.alloc)
  const r = blendedReturn(alloc)
  const projected = projectWealth(position.totalWealth, alloc, n)
  const gap = goal.amount - projected
  const req = requiredReturn(position.totalWealth, goal.amount, n)
  const search = reallocationSearch(position, goal)

  const aifMin = reference.sebi_minimums.aif
  const aifRuledOut =
    n < reference.aif_lockin_years && position.totalWealth >= aifMin
  const aifRuleReason = aifRuledOut
    ? `AIF ruled out: horizon ${n}y < ${reference.aif_lockin_years}y lock-in while corpus ≥ ₹1Cr.`
    : null

  const scopeLimits: string[] = []
  if (reference.categories.real_estate.excluded) {
    scopeLimits.push(reference.categories.real_estate.exclusion_note)
  }
  if (reference.categories.direct_equity.proxy) {
    scopeLimits.push(reference.categories.direct_equity.proxy_note)
  }
  if (aifRuleReason) scopeLimits.push(aifRuleReason)

  const alreadyMet = projected >= goal.amount
  return {
    n,
    blendedReturn: r,
    projected,
    gap,
    requiredReturn: req,
    feasible: alreadyMet || search.feasible,
    proposedAlloc: alreadyMet ? alloc : search.proposedAlloc,
    switchAmount: alreadyMet ? 0 : search.switchAmount,
    aifRuledOut,
    aifRuleReason,
    scopeLimits,
  }
}
