import {
  createContext,
  useContext,
  useMemo,
  useReducer,
  type Dispatch,
  type ReactNode,
} from 'react'
import {
  DEFAULT_GOAL,
  DEFAULT_HANDOFF,
  DEFAULT_PERSONA_ID,
  DEFAULT_POSITION,
  DEFAULT_ROUND1,
} from './defaults'
import { runCommittee } from './engine/committee'
import { normalizeAlloc, setAllocBudgeted } from './engine/projection'
import {
  allocFromRound1,
  getPersona,
  round1FromAlloc,
  seedFromPersona,
  wealthFromSalary,
  type Round1Levers,
} from './fromPersona'
import type {
  AgentProse,
  Alloc,
  AssetKey,
  CommitteeResult,
  Goal,
  Handoff,
  Position,
  ProseSource,
  EdgeScreen,
} from './types'

export type EdgeState = {
  screen: EdgeScreen
  personaId: string
  round1: Round1Levers
  handoff: Handoff
  position: Position
  goal: Goal
  committee: CommitteeResult
  prose: AgentProse[]
  proseSource: ProseSource
}

type Action =
  | { type: 'SET_SCREEN'; screen: EdgeScreen }
  | { type: 'SET_HANDOFF'; handoff: Partial<Handoff> }
  | { type: 'SET_POSITION'; position: Partial<Position> }
  | { type: 'SET_ALLOC'; alloc: Partial<Alloc> }
  | { type: 'SET_ALLOC_WEIGHT'; key: AssetKey; value: number }
  | { type: 'SET_CHANNEL'; direct: number }
  | { type: 'SET_GOAL'; goal: Partial<Goal> }
  | { type: 'SET_ROUND1'; levers: Partial<Round1Levers> }
  | { type: 'LOAD_PERSONA'; id: string }
  | { type: 'NORMALIZE_ALLOC' }
  | { type: 'LOAD_TYPICAL_P2' }
  | { type: 'RESET' }
  | { type: 'RERUN' }
  | { type: 'SET_PROSE'; prose: AgentProse[]; source: ProseSource }

function recompute(state: Omit<EdgeState, 'committee'> & { committee?: CommitteeResult }): EdgeState {
  const committee = runCommittee(state.position, state.goal, state.handoff)
  return { ...state, committee }
}

const initialBase = {
  screen: 'handoff' as EdgeScreen,
  personaId: DEFAULT_PERSONA_ID,
  round1: DEFAULT_ROUND1,
  handoff: DEFAULT_HANDOFF,
  position: DEFAULT_POSITION,
  goal: DEFAULT_GOAL,
  prose: [] as AgentProse[],
  proseSource: 'none' as ProseSource,
}

export const initialState: EdgeState = recompute(initialBase)

function applyRound1(state: EdgeState, patch: Partial<Round1Levers>): EdgeState {
  const next: Round1Levers = { ...state.round1, ...patch }
  // Cap deposit so equity + deposit never exceeds 100 (Round-1 rule).
  if (next.equityAllocationPct + next.depositAllocationPct > 100) {
    if (patch.equityAllocationPct !== undefined) {
      next.depositAllocationPct = Math.max(0, 100 - next.equityAllocationPct)
    } else {
      next.equityAllocationPct = Math.max(0, 100 - next.depositAllocationPct)
    }
  }
  const wealth =
    patch.salary !== undefined ? wealthFromSalary(next.salary) : state.position.totalWealth
  return recompute({
    ...state,
    round1: next,
    position: {
      ...state.position,
      totalWealth: wealth,
      alloc: allocFromRound1(next.equityAllocationPct, next.depositAllocationPct),
    },
  })
}

function reducer(state: EdgeState, action: Action): EdgeState {
  switch (action.type) {
    case 'SET_SCREEN':
      return { ...state, screen: action.screen }
    case 'SET_HANDOFF':
      return recompute({
        ...state,
        handoff: { ...state.handoff, ...action.handoff },
      })
    case 'SET_POSITION':
      return recompute({
        ...state,
        position: { ...state.position, ...action.position },
      })
    case 'SET_ALLOC':
      return recompute({
        ...state,
        position: {
          ...state.position,
          alloc: { ...state.position.alloc, ...action.alloc },
        },
      })
    case 'SET_ALLOC_WEIGHT': {
      const alloc = setAllocBudgeted(state.position.alloc, action.key, action.value)
      const { equityPct, depositPct } = round1FromAlloc(alloc)
      return recompute({
        ...state,
        round1: {
          ...state.round1,
          equityAllocationPct: equityPct,
          depositAllocationPct: depositPct,
        },
        position: { ...state.position, alloc },
      })
    }
    case 'SET_CHANNEL': {
      const direct = Math.min(1, Math.max(0, action.direct))
      return recompute({
        ...state,
        position: {
          ...state.position,
          channel: { direct, distributor: 1 - direct },
        },
      })
    }
    case 'SET_GOAL':
      return recompute({
        ...state,
        goal: { ...state.goal, ...action.goal },
      })
    case 'SET_ROUND1':
      return applyRound1(state, action.levers)
    case 'LOAD_PERSONA': {
      const seeded = seedFromPersona(getPersona(action.id))
      return recompute({
        ...state,
        personaId: action.id,
        round1: seeded.round1,
        handoff: seeded.handoff,
        position: seeded.position,
        goal: seeded.goal,
      })
    }
    case 'NORMALIZE_ALLOC':
      return recompute({
        ...state,
        position: {
          ...state.position,
          alloc: normalizeAlloc(state.position.alloc),
        },
      })
    case 'LOAD_TYPICAL_P2':
      return reducer(state, { type: 'LOAD_PERSONA', id: 'P2' })
    case 'RESET':
      return recompute({ ...initialBase, screen: 'handoff' })
    case 'RERUN':
      return recompute({ ...state })
    case 'SET_PROSE':
      return { ...state, prose: action.prose, proseSource: action.source }
    default:
      return state
  }
}

const EdgeStateContext = createContext<EdgeState | null>(null)
const EdgeDispatchContext = createContext<Dispatch<Action> | null>(null)

export function EdgeProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, recompute({ ...initialBase, screen: 'handoff' }))
  return (
    <EdgeStateContext.Provider value={state}>
      <EdgeDispatchContext.Provider value={dispatch}>
        {children}
      </EdgeDispatchContext.Provider>
    </EdgeStateContext.Provider>
  )
}

export function useEdgeState(): EdgeState {
  const ctx = useContext(EdgeStateContext)
  if (!ctx) throw new Error('useEdgeState outside EdgeProvider')
  return ctx
}

export function useEdgeDispatch(): Dispatch<Action> {
  const ctx = useContext(EdgeDispatchContext)
  if (!ctx) throw new Error('useEdgeDispatch outside EdgeProvider')
  return ctx
}

export function useEdge(): [EdgeState, Dispatch<Action>] {
  return [useEdgeState(), useEdgeDispatch()]
}

export function useCommitteeFigures() {
  const { committee } = useEdgeState()
  return useMemo(() => committee, [committee])
}
