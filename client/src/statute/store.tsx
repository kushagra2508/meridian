import {
  createContext,
  useContext,
  useMemo,
  useReducer,
  type Dispatch,
  type ReactNode,
} from 'react'
import { runCommittee } from './engine/committee'
import { DEFAULT_GOAL, DEFAULT_HANDOFF, DEFAULT_POSITION } from './defaults'
import { normalizeAlloc } from './engine/projection'
import type {
  AgentProse,
  Alloc,
  CommitteeResult,
  Goal,
  Handoff,
  Position,
  ProseSource,
  StatuteScreen,
} from './types'

export type StatuteState = {
  screen: StatuteScreen
  handoff: Handoff
  position: Position
  goal: Goal
  committee: CommitteeResult
  prose: AgentProse[]
  proseSource: ProseSource
}

type Action =
  | { type: 'SET_SCREEN'; screen: StatuteScreen }
  | { type: 'SET_HANDOFF'; handoff: Partial<Handoff> }
  | { type: 'SET_POSITION'; position: Partial<Position> }
  | { type: 'SET_ALLOC'; alloc: Partial<Alloc> }
  | { type: 'SET_CHANNEL'; direct: number }
  | { type: 'SET_GOAL'; goal: Partial<Goal> }
  | { type: 'NORMALIZE_ALLOC' }
  | { type: 'LOAD_TYPICAL_P2' }
  | { type: 'RESET' }
  | { type: 'RERUN' }
  | { type: 'SET_PROSE'; prose: AgentProse[]; source: ProseSource }

function recompute(state: Omit<StatuteState, 'committee'> & { committee?: CommitteeResult }): StatuteState {
  const committee = runCommittee(state.position, state.goal, state.handoff)
  return { ...state, committee }
}

const initialBase = {
  screen: 'handoff' as StatuteScreen,
  handoff: DEFAULT_HANDOFF,
  position: DEFAULT_POSITION,
  goal: DEFAULT_GOAL,
  prose: [] as AgentProse[],
  proseSource: 'none' as ProseSource,
}

export const initialState: StatuteState = recompute(initialBase)

function reducer(state: StatuteState, action: Action): StatuteState {
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
    case 'NORMALIZE_ALLOC':
      return recompute({
        ...state,
        position: {
          ...state.position,
          alloc: normalizeAlloc(state.position.alloc),
        },
      })
    case 'LOAD_TYPICAL_P2':
      return recompute({
        ...state,
        handoff: DEFAULT_HANDOFF,
        position: DEFAULT_POSITION,
        goal: DEFAULT_GOAL,
      })
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

const StatuteStateContext = createContext<StatuteState | null>(null)
const StatuteDispatchContext = createContext<Dispatch<Action> | null>(null)

export function StatuteProvider({
  children,
}: {
  children: ReactNode
}) {
  const [state, dispatch] = useReducer(reducer, recompute({ ...initialBase, screen: 'handoff' }))
  return (
    <StatuteStateContext.Provider value={state}>
      <StatuteDispatchContext.Provider value={dispatch}>
        {children}
      </StatuteDispatchContext.Provider>
    </StatuteStateContext.Provider>
  )
}

export function useStatuteState(): StatuteState {
  const ctx = useContext(StatuteStateContext)
  if (!ctx) throw new Error('useStatuteState outside StatuteProvider')
  return ctx
}

export function useStatuteDispatch(): Dispatch<Action> {
  const ctx = useContext(StatuteDispatchContext)
  if (!ctx) throw new Error('useStatuteDispatch outside StatuteProvider')
  return ctx
}

export function useStatute(): [StatuteState, Dispatch<Action>] {
  return [useStatuteState(), useStatuteDispatch()]
}

export function useCommitteeFigures() {
  const { committee } = useStatuteState()
  return useMemo(() => committee, [committee])
}
