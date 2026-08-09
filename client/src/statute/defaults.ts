import personas from './data/personas.json'
import type { Goal, Handoff, Position } from './types'
import { normalizeAlloc } from './engine/projection'

const p2 = personas.personas[0]

export const DEFAULT_HANDOFF: Handoff = {
  persona: p2.handoff.persona,
  priorityTier: p2.handoff.priorityTier,
  declaredIncomeBand: p2.handoff.declaredIncomeBand,
  declaredIncomeLabel: p2.handoff.declaredIncomeLabel,
  channelUsed: p2.handoff.channelUsed,
  pursueDecision: p2.handoff.pursueDecision as Handoff['pursueDecision'],
  futureEvents: p2.handoff.futureEvents,
  acquisitionCost: p2.handoff.acquisitionCost,
}

export const DEFAULT_POSITION: Position = {
  totalWealth: p2.typicalPosition.totalWealth,
  alloc: normalizeAlloc(p2.typicalPosition.alloc),
  channel: { ...p2.typicalPosition.channel },
  unrealisedGainPct: p2.typicalPosition.unrealisedGainPct,
}

export const DEFAULT_GOAL: Goal = { ...p2.typicalGoal }
