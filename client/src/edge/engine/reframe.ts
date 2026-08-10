import type { Goal, Position } from '../types'
import { blendedReturn, yearsToGoal } from './projection'

export type ReframeOption = {
  id: 'slip_year' | 'shrink_target' | 'monthly_topup'
  label: string
  slipYears: number
  slipMonths: number
  reachable: number
  monthly: number
  noPortfolioChange: boolean
}

export type ReframeResult = {
  options: ReframeOption[]
  blendedReturn: number
}

export function runReframe(position: Position, goal: Goal): ReframeResult {
  const n = yearsToGoal(goal)
  const r = blendedReturn(position.alloc)
  const { totalWealth } = position

  let slipYears = n
  if (totalWealth > 0 && r > 0 && goal.amount > 0) {
    slipYears = Math.log(goal.amount / totalWealth) / Math.log(1 + r)
  } else if (r <= 0) {
    slipYears = Number.POSITIVE_INFINITY
  }
  const slipMonths =
    Number.isFinite(slipYears) ? Math.round((slipYears - n) * 12) : 999

  const reachable = totalWealth * Math.pow(1 + Math.max(r, 0), Math.max(n, 0))

  const rm = Math.pow(1 + Math.max(r, 0), 1 / 12) - 1
  const nm = Math.max(n, 0) * 12
  let monthly = 0
  if (rm > 0 && nm > 0) {
    const fvFactor = Math.pow(1 + rm, nm)
    monthly = ((goal.amount - totalWealth * fvFactor) * rm) / (fvFactor - 1)
  } else if (nm > 0) {
    monthly = (goal.amount - totalWealth) / nm
  }
  monthly = Math.max(0, monthly)

  return {
    blendedReturn: r,
    options: [
      {
        id: 'slip_year',
        label: 'Slip the year',
        slipYears: Number.isFinite(slipYears) ? slipYears : n + 50,
        slipMonths,
        reachable,
        monthly: 0,
        noPortfolioChange: true,
      },
      {
        id: 'shrink_target',
        label: 'Shrink the target',
        slipYears: n,
        slipMonths: 0,
        reachable,
        monthly: 0,
        noPortfolioChange: true,
      },
      {
        id: 'monthly_topup',
        label: 'Monthly top-up',
        slipYears: n,
        slipMonths: 0,
        reachable,
        monthly,
        noPortfolioChange: false,
      },
    ],
  }
}
