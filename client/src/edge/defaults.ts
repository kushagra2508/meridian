import { getPersona, seedFromPersona } from './fromPersona'
import type { Goal, Handoff, Position } from './types'

const seeded = seedFromPersona(getPersona('P2'))

export const DEFAULT_HANDOFF: Handoff = seeded.handoff
export const DEFAULT_POSITION: Position = seeded.position
export const DEFAULT_GOAL: Goal = seeded.goal
export const DEFAULT_ROUND1 = seeded.round1
export const DEFAULT_PERSONA_ID = 'P2'
