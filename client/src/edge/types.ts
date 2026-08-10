export type AssetKey =
  | 'equity_mf'
  | 'debt_mf'
  | 'fd_cash'
  | 'direct_equity'
  | 'gold'
  | 'real_estate'

export type Alloc = Record<AssetKey, number>

export type Position = {
  totalWealth: number
  alloc: Alloc
  channel: { direct: number; distributor: number }
  unrealisedGainPct: number
}

export type Goal = {
  amount: number
  year: number
  purpose: string
  note: string
}

export type Handoff = {
  clientName: string
  persona: string
  priorityTier: number
  declaredIncomeBand: string
  declaredIncomeLabel: string
  channelUsed: string
  pursueDecision: 'PURSUE' | 'DEFER'
  futureEvents: { label: string; year: number }[]
  acquisitionCost: number
}

export type BadgeTier = 'live' | 'statute' | 'assumption'

export type FigureBadge = {
  tier: BadgeTier
  label: string
}

export type AgentId = 'planner' | 'tax' | 'fees' | 'rethink'

export type Stance = 'PROPOSES' | 'OBJECTS' | 'CONDITIONS' | 'CONCEDES'

export type AgentFigure = {
  key: string
  value: number
  badge: FigureBadge
}

export type AgentPosition = {
  agent: AgentId
  stance: Stance
  figures: AgentFigure[]
  referencesAgent: AgentId | null
  scopeLimits: string[]
  claim?: string
  opening?: string | null
}

export type EdgeScreen =
  | 'handoff'
  | 'position'
  | 'goal'
  | 'eligibility'
  | 'committee'
  | 'verdict'
  | 'glossary'

export type LedgerRow = {
  path: string
  label: string
  netRupees: number
  taxCost: number
  annualDragSaved: number
  goalProb: number
  illiquidPct: number
  rank: number
  tags: string[]
  notes: string[]
}

export type VerdictState = 'goal_clears' | 'repriced_goals'

export type Verdict = {
  state: VerdictState
  paths: LedgerRow[]
  survivingObjections: string[]
  summary: string
}

export type CommitteeResult = {
  positions: AgentPosition[]
  ledger: LedgerRow[]
  verdict: Verdict
  feasible: boolean
  eligibility: EligibilityResult
}

export type EligibilityLane = 'direct' | 'pms' | 'aif' | 'uhni'

export type EligibilityResult = {
  investableCorpus: number
  highestEligible: EligibilityLane
  eligible: EligibilityLane[]
  blocked: EligibilityLane[]
  ladder: { lane: EligibilityLane; minimum: number; label: string; eligible: boolean }[]
}

export type AgentProse = {
  agent: AgentId
  claim: string
  opening: string | null
}

export type ProseSource = 'live' | 'cached' | 'none'