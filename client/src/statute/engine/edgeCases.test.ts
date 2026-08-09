import { describe, expect, it } from 'vitest'
import { DEFAULT_GOAL, DEFAULT_HANDOFF, DEFAULT_POSITION } from '../defaults'
import type { Goal, Position } from '../types'
import { runCommittee } from './committee'
import { runDrag } from './drag'
import { runEligibility } from './eligibility'
import { normalizeAlloc, runProjection } from './projection'
import { fyStager, priceSwitchTax } from './tax'

const basePos = (): Position => structuredClone(DEFAULT_POSITION)
const baseGoal = (): Goal => structuredClone(DEFAULT_GOAL)

describe('STATUTE edge cases', () => {
  it('blocks conceptually when goal.year <= 2026 (engine treats n<=0)', () => {
    const goal = { ...baseGoal(), year: 2026 }
    expect(goal.year <= 2026).toBe(true)
    const proj = runProjection(basePos(), goal)
    expect(proj.n).toBeLessThanOrEqual(0)
  })

  it('100% real estate → blended return 0, gap enormous, Reframe leads', () => {
    const position = basePos()
    position.alloc = normalizeAlloc({
      equity_mf: 0,
      debt_mf: 0,
      fd_cash: 0,
      direct_equity: 0,
      gold: 0,
      real_estate: 1,
    })
    const result = runCommittee(position, baseGoal(), DEFAULT_HANDOFF)
    expect(result.feasible).toBe(false)
    expect(result.positions.some((p) => p.agent === 'reframe')).toBe(true)
    const feas = result.positions.find((p) => p.agent === 'feasibility')!
    const blended = feas.figures.find((f) => f.key === 'blendedReturn')!.value
    expect(blended).toBe(0)
  })

  it('direct equity 90%, MF 0% → Channel drag ₹0', () => {
    const position = basePos()
    position.alloc = normalizeAlloc({
      equity_mf: 0,
      debt_mf: 0,
      fd_cash: 0.05,
      direct_equity: 0.9,
      gold: 0.05,
      real_estate: 0,
    })
    const drag = runDrag(position)
    expect(drag.annualDrag).toBe(0)
    const result = runCommittee(position, baseGoal(), DEFAULT_HANDOFF)
    const channel = result.positions.find((p) => p.agent === 'channel')!
    expect(channel.stance).toBe('CONCEDES')
    expect(channel.figures.find((f) => f.key === 'annualDrag')!.value).toBe(0)
  })

  it('wealth ₹10L → ladder greys PMS+, paths still compute', () => {
    const position = { ...basePos(), totalWealth: 1_000_000 }
    const elig = runEligibility(position.totalWealth)
    expect(elig.eligible).toEqual(['direct'])
    expect(elig.blocked).toContain('pms')
    const result = runCommittee(position, baseGoal(), DEFAULT_HANDOFF)
    expect(result.ledger.length).toBeGreaterThan(0)
  })

  it('goal already met → Feasibility CONCEDES, Statute ₹0', () => {
    const position = basePos()
    const goal = { ...baseGoal(), amount: 1_000_000, year: 2030 }
    const result = runCommittee(position, goal, DEFAULT_HANDOFF)
    const feas = result.positions.find((p) => p.agent === 'feasibility')!
    expect(feas.stance).toBe('CONCEDES')
    const statute = result.positions.find((p) => p.agent === 'statute')!
    expect(statute.figures.find((f) => f.key === 'totalTax')!.value).toBe(0)
    expect(result.verdict.paths.some((p) => p.tags.includes('NO PORTFOLIO CHANGE REQUIRED'))).toBe(
      true,
    )
  })

  it('allocation summing to 99% normalises on normalizeAlloc', () => {
    const alloc = normalizeAlloc({
      equity_mf: 0.35,
      debt_mf: 0.2,
      fd_cash: 0.15,
      direct_equity: 0.1,
      gold: 0.05,
      real_estate: 0.14, // 0.99
    })
    const sum = Object.values(alloc).reduce((a, b) => a + b, 0)
    expect(sum).toBeCloseTo(1, 10)
  })

  it('gain below ₹1.25L → Statute tax ₹0, never negative', () => {
    const position = { ...basePos(), unrealisedGainPct: 0.01 }
    const tax = priceSwitchTax(1_000_000, 'equity_mf', position, DEFAULT_HANDOFF)
    // embedded gain = 10_000 < 125_000 exemption
    expect(tax.embeddedGain).toBe(10_000)
    expect(tax.totalTax).toBe(0)
    expect(tax.totalTax).toBeGreaterThanOrEqual(0)
    expect(fyStager(100_000)).toBeNull()
  })
})
