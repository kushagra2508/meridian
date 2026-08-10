import type { AgentId } from './types'

/** User-facing names. Engine IDs stay lowercase; UI always shows these. */
export const AGENT_DISPLAY: Record<AgentId | 'verdict', string> = {
  planner: 'Planner',
  tax: 'Tax',
  fees: 'Fees',
  rethink: 'Rethink',
  verdict: 'Verdict',
}

export function displayAgent(id: AgentId | 'verdict' | string): string {
  const key = id.toLowerCase() as AgentId | 'verdict'
  return AGENT_DISPLAY[key] ?? id[0]!.toUpperCase() + id.slice(1)
}

export type AgentGlossaryEntry = {
  id: AgentId | 'verdict'
  name: string
  role: string
  objective: string
  logic: string[]
  fightsWith: string
}

export const AGENT_GLOSSARY: AgentGlossaryEntry[] = [
  {
    id: 'planner',
    name: 'Planner',
    role: 'Goal reachability',
    objective: 'Close the gap to the stated goal without breaking the deadline.',
    logic: [
      'Blended return = Σ allocation × category CAGR from reference.json (real estate contributes 0).',
      'Projected wealth = corpus × (1 + r)^n where n = goal year − 2026.',
      'Searches fd_cash → equity_mf in ₹1L steps until the goal clears, hard-capping total equity at 85%.',
      'If still short after the cap, marks the goal unreachable and hands off to Rethink.',
      'Rules AIF out when the horizon is shorter than the 7-year lock-in.',
    ],
    fightsWith: 'Tax (exit cost) and Rethink (moves the goal instead of the money)',
  },
  {
    id: 'tax',
    name: 'Tax',
    role: 'Realised tax on the proposed switch',
    objective: 'Price the tax consequence of Planner’s switch; object when it exceeds 2% of corpus.',
    logic: [
      'Embedded gain = switch amount × unrealisedGainPct (assumption, default 25%).',
      'Equity sleeves: LTCG §112A at 12.5% after ₹1.25L exemption; STCG §111A at 20% if holding < 12m.',
      'Debt / FD: slab rate from declared income band. Gold: 12.5% LTCG.',
      'Surcharge banded by income (capped 15% on 111A/112A) + 4% cess.',
      'fyStager() prices splitting a switch across two FYs to use the exemption twice.',
    ],
    fightsWith: 'Fees (exiting drag realises gains)',
  },
  {
    id: 'fees',
    name: 'Fees',
    role: 'Distributor drag',
    objective: 'Eliminate ongoing TER drag on distributor-held mutual funds.',
    logic: [
      'MF sleeve = (equity_mf + debt_mf) × corpus.',
      'Annual drag = equity_mf × corpus × distributor × TER_equity + debt_mf × corpus × distributor × TER_debt.',
      'Always reports out-of-scope value (direct equity, gold, real estate, FD) — those have no published plan-type spread.',
      'Objects when annual drag > 0; concedes with ₹0 when the book has no distributor MF.',
    ],
    fightsWith: 'Tax (escaping drag requires an exit)',
  },
  {
    id: 'rethink',
    name: 'Rethink',
    role: 'Repriced goals',
    objective: 'Make the goal reachable by moving the goal, not the portfolio — only when Planner fails.',
    logic: [
      'Slip: years until current path reaches the target (closed-form log).',
      'Shrink: wealth reachable by the stated year at the blended return.',
      'Top-up: monthly PMT so both target and date hold.',
      'Slip and shrink are tagged NO PORTFOLIO CHANGE REQUIRED when no switch is needed.',
    ],
    fightsWith: 'Planner (refuses to stretch the portfolio past the equity cap)',
  },
  {
    id: 'verdict',
    name: 'Verdict',
    role: 'Ledger resolution',
    objective: 'Rank surviving paths. No agent issues advice — the ledger resolves.',
    logic: [
      'Paths ranked by net rupees, then lower tax cost.',
      'State A (goal clears) when Planner was feasible; State B (repriced goals) when Rethink fired.',
      'Surviving objections from Tax and Fees are listed, not smoothed over.',
    ],
    fightsWith: 'None — it only ranks what the others left standing',
  },
]
