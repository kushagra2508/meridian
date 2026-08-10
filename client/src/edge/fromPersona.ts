import personas from './data/personas.json'
import { normalizeAlloc } from './engine/projection'
import type { Alloc, Goal, Handoff, Position } from './types'

export type Round1Levers = {
  age: number
  salary: number
  equityAllocationPct: number
  depositAllocationPct: number
}

export type PersonaRecord = (typeof personas.personas)[number]

export function listPersonas(): PersonaRecord[] {
  return personas.personas
}

export function getPersona(id: string): PersonaRecord {
  return personas.personas.find((p) => p.id === id) ?? personas.personas[1]!
}

/**
 * Map Round-1 Equity % + Deposit % into the six sleeves.
 * Equity splits 70/30 across equity_mf / direct_equity.
 * Deposits split 60/40 across fd_cash / debt_mf.
 * Remainder (always ≥ 0) goes to gold + real estate.
 */
export function allocFromRound1(equityPct: number, depositPct: number): Alloc {
  const equity = Math.min(100, Math.max(0, equityPct)) / 100
  // Deposit cannot push the book past 100% once equity is set.
  const deposit = Math.min(100 - equity * 100, Math.max(0, depositPct)) / 100
  const rest = Math.max(0, 1 - equity - deposit)

  return normalizeAlloc({
    equity_mf: equity * 0.7,
    direct_equity: equity * 0.3,
    fd_cash: deposit * 0.6,
    debt_mf: deposit * 0.4,
    gold: rest * 0.35,
    real_estate: rest * 0.65,
  })
}

/** Round-1 used salary × 55 as a stand-in for investable corpus. */
export function wealthFromSalary(salary: number): number {
  return Math.round(salary * 55)
}

export function round1FromAlloc(alloc: Alloc): { equityPct: number; depositPct: number } {
  const equityPct = Math.round((alloc.equity_mf + alloc.direct_equity) * 100)
  const depositPct = Math.round((alloc.fd_cash + alloc.debt_mf) * 100)
  return { equityPct, depositPct }
}

export function seedFromPersona(persona: PersonaRecord): {
  handoff: Handoff
  position: Position
  goal: Goal
  round1: Round1Levers
} {
  return {
    handoff: {
      ...persona.handoff,
      pursueDecision: persona.handoff.pursueDecision as Handoff['pursueDecision'],
      futureEvents: [...persona.handoff.futureEvents],
    },
    position: {
      totalWealth: persona.typicalPosition.totalWealth,
      alloc: normalizeAlloc(persona.typicalPosition.alloc),
      channel: { ...persona.typicalPosition.channel },
      unrealisedGainPct: persona.typicalPosition.unrealisedGainPct,
    },
    goal: { ...persona.typicalGoal },
    round1: { ...persona.round1 },
  }
}
