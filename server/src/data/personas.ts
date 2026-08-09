import type { Persona, PersonaCatalog, PersonaTrait } from '../types.js'

export const personas: Persona[] = [
  {
    id: 'P1',
    name: 'Aspiring High Rollers',
    exhibit: 'Exhibit A',
    incomeBand: '$250k – $500k',
    selfDirectedPct: 80,
    primaryChannel: 'Digital',
    thesis: 'Concentrated growth bets, low patience for advisory friction.',
    profile: {
      age: 34,
      salary: 375_000,
      equityAllocationPct: 85,
      depositAllocationPct: 5,
    },
  },
  {
    id: 'P2',
    name: 'Smart Risk Takers',
    exhibit: 'Exhibit A',
    incomeBand: '$150k – $300k',
    selfDirectedPct: 60,
    primaryChannel: 'Hybrid',
    thesis: 'Self-directs the core, buys advice for the tail risk.',
    profile: {
      age: 42,
      salary: 225_000,
      equityAllocationPct: 65,
      depositAllocationPct: 15,
    },
  },
  {
    id: 'P3',
    name: 'Steady Wealth Builders',
    exhibit: 'Exhibit A',
    incomeBand: '$100k – $200k',
    selfDirectedPct: 40,
    primaryChannel: 'Advisor',
    thesis: 'Goal-anchored accumulation with a standing advisor relationship.',
    profile: {
      age: 51,
      salary: 150_000,
      equityAllocationPct: 45,
      depositAllocationPct: 25,
    },
  },
  {
    id: 'P4',
    name: 'Disciplined Savers',
    exhibit: 'Exhibit A',
    incomeBand: '< $150k',
    selfDirectedPct: 20,
    primaryChannel: 'Retail',
    thesis: 'Capital preservation first, converts slowly to invested products.',
    profile: {
      age: 60,
      salary: 95_000,
      equityAllocationPct: 25,
      depositAllocationPct: 45,
    },
  },
]

// Bounds double as the normalisation ranges for closest-persona matching, so a
// trait only influences the match as much as its span allows.
export const personaTraits: PersonaTrait[] = [
  { key: 'age', label: 'Age', min: 22, max: 72, step: 1, unit: 'years' },
  { key: 'salary', label: 'Salary Income', min: 50_000, max: 600_000, step: 5_000, unit: 'currency' },
  { key: 'equityAllocationPct', label: 'Equity Allocation', min: 0, max: 100, step: 5, unit: 'percent' },
  { key: 'depositAllocationPct', label: 'Deposit Allocation', min: 0, max: 100, step: 5, unit: 'percent' },
]

export const personaCatalog: PersonaCatalog = {
  personas,
  traits: personaTraits,
  defaultPersonaId: 'P2',
}
