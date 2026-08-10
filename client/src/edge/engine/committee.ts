import reference from '../data/reference.json'
import type {
  AgentPosition,
  CommitteeResult,
  Goal,
  Handoff,
  Position,
} from '../types'
import { dragSavedOnNewFlow, runDrag } from './drag'
import { runEligibility } from './eligibility'
import { buildVerdict, rankPaths } from './ledger'
import { runProjection } from './projection'
import { runReframe } from './reframe'
import { priceSwitchTax } from './tax'

const LIVE = { tier: 'live' as const, label: 'mfapi.in' }
const TAX_RULE = { tier: 'statute' as const, label: 'IT Act' }
const ASSUMPTION = { tier: 'assumption' as const, label: 'model' }

function goalProbability(projected: number, goalAmount: number): number {
  if (goalAmount <= 0) return 1
  const ratio = projected / goalAmount
  return Math.max(0, Math.min(0.99, ratio > 1 ? 0.87 + Math.min(0.12, (ratio - 1) * 0.2) : ratio * 0.85))
}

/** Pure, synchronous committee. Never touches the network. */
export function runCommittee(
  position: Position,
  goal: Goal,
  handoff: Handoff,
): CommitteeResult {
  const projection = runProjection(position, goal)
  const drag = runDrag(position)
  const eligibility = runEligibility(position.totalWealth)
  const illiquidPct = position.alloc.real_estate + position.alloc.gold * 0.5

  const alreadyMet = projection.gap <= 0 && projection.switchAmount === 0
  const plannerStance = alreadyMet
    ? 'CONCEDES'
    : projection.feasible
      ? 'PROPOSES'
      : 'CONDITIONS'

  const planner: AgentPosition = {
    agent: 'planner',
    stance: plannerStance,
    figures: [
      {
        key: 'projected',
        value: projection.projected,
        badge: { ...LIVE, label: reference.generated_at.slice(0, 10) },
      },
      { key: 'gap', value: projection.gap, badge: ASSUMPTION },
      {
        key: 'requiredReturn',
        value: projection.requiredReturn,
        badge: ASSUMPTION,
      },
      {
        key: 'switchAmount',
        value: projection.switchAmount,
        badge: ASSUMPTION,
      },
      {
        key: 'blendedReturn',
        value: projection.blendedReturn,
        badge: LIVE,
      },
    ],
    referencesAgent: null,
    scopeLimits: projection.scopeLimits,
  }

  const tax = priceSwitchTax(
    projection.switchAmount,
    'equity_mf',
    position,
    handoff,
  )
  const taxThreshold = 0.02 * position.totalWealth
  const taxStance =
    tax.totalTax > taxThreshold ? 'OBJECTS' : 'CONDITIONS'

  const taxAgent: AgentPosition = {
    agent: 'tax',
    stance: alreadyMet ? 'CONDITIONS' : taxStance,
    figures: [
      {
        key: 'totalTax',
        value: alreadyMet ? 0 : tax.totalTax,
        badge: { ...TAX_RULE, label: tax.lines[0]?.section ?? '§112A' },
      },
      {
        key: 'embeddedGain',
        value: alreadyMet ? 0 : tax.embeddedGain,
        badge: ASSUMPTION,
      },
      {
        key: 'fyStagerSaving',
        value: tax.fyStagerSaving ?? 0,
        badge: { ...TAX_RULE, label: '§112A ×2 FY' },
      },
    ],
    referencesAgent: 'planner',
    scopeLimits: [
      'Set-off, carry-forward, and residency rules are out of scope.',
      `unrealisedGainPct=${position.unrealisedGainPct} is an assumption.`,
    ],
  }

  const feesStance = drag.annualDrag > 0 ? 'OBJECTS' : 'CONCEDES'
  const fees: AgentPosition = {
    agent: 'fees',
    stance: feesStance,
    figures: [
      {
        key: 'annualDrag',
        value: drag.annualDrag,
        badge: {
          tier: 'live',
          label: 'AMFI TER spread',
        },
      },
      {
        key: 'distributorHeld',
        value: drag.distributorHeld,
        badge: ASSUMPTION,
      },
      {
        key: 'outOfScopeValue',
        value: drag.outOfScopeValue,
        badge: ASSUMPTION,
      },
    ],
    referencesAgent: 'tax',
    scopeLimits: [drag.scopeNote],
  }

  const positions: AgentPosition[] = [planner, taxAgent, fees]
  const objections: string[] = []
  if (taxAgent.stance === 'OBJECTS') {
    objections.push(
      `Tax: ₹${Math.round(tax.totalTax).toLocaleString('en-IN')} exceeds 2% of corpus.`,
    )
  }
  if (fees.stance === 'OBJECTS') {
    objections.push(
      `Fees: annual distributor drag ₹${Math.round(drag.annualDrag).toLocaleString('en-IN')} remains.`,
    )
  }

  let reframeFired = false
  if (!projection.feasible) {
    reframeFired = true
    const reframe = runReframe(position, goal)
    positions.push({
      agent: 'rethink',
      stance: 'PROPOSES',
      figures: reframe.options.map((opt) => ({
        key: opt.id,
        value:
          opt.id === 'monthly_topup'
            ? opt.monthly
            : opt.id === 'shrink_target'
              ? opt.reachable
              : opt.slipMonths,
        badge: ASSUMPTION,
      })),
      referencesAgent: 'planner',
      scopeLimits: ['Rethink prices consequences; it does not issue advice.'],
    })
  }

  const dragSavedIfDirect = drag.annualDrag
  const pathDrafts = projection.feasible
    ? [
        {
          path: 'equity_tilt',
          label: 'Aggressive Equity Tilt',
          netRupees: -tax.totalTax + dragSavedIfDirect * projection.n * 0.5,
          taxCost: tax.totalTax,
          annualDragSaved: dragSavedIfDirect * 0.6,
          goalProb: goalProbability(
            Math.max(projection.projected, goal.amount),
            goal.amount,
          ),
          illiquidPct,
          tags: alreadyMet ? ['NO PORTFOLIO CHANGE REQUIRED'] : [],
          notes: [],
        },
        {
          path: 'balanced',
          label: 'Balanced Defensives',
          netRupees: -tax.totalTax * 0.55 + dragSavedIfDirect * 0.3,
          taxCost: tax.totalTax * 0.55,
          annualDragSaved: dragSavedIfDirect * 0.3,
          goalProb: goalProbability(projection.projected, goal.amount) * 0.93,
          illiquidPct: Math.min(0.95, illiquidPct + 0.1),
          tags: [],
          notes: [],
        },
      ]
    : runReframe(position, goal).options.map((opt) => {
        // Slip/shrink leave the book untouched, so tax and drag are genuinely
        // ₹0 (tagged below). Top-up is the one option that moves new money —
        // if that SIP goes Direct instead of following the book's current
        // distributor share, it avoids real, computable TER drag each year.
        const annualDragSaved =
          opt.id === 'monthly_topup' ? dragSavedOnNewFlow(position, opt.monthly * 12) : 0
        const netRupees =
          opt.id === 'monthly_topup'
            ? (annualDragSaved - opt.monthly * 12) * projection.n
            : opt.reachable - goal.amount

        return {
          path: opt.id,
          label: opt.label,
          netRupees,
          taxCost: 0,
          annualDragSaved,
          goalProb:
            opt.id === 'shrink_target'
              ? 0.9
              : opt.id === 'slip_year'
                ? 0.85
                : 0.8,
          illiquidPct,
          tags: opt.noPortfolioChange ? ['NO PORTFOLIO CHANGE REQUIRED'] : [],
          notes:
            opt.id === 'shrink_target'
              ? [`Reachable by ${goal.year}: ₹${Math.round(opt.reachable)}`]
              : opt.id === 'slip_year'
                ? [`Slip ${opt.slipMonths} months`]
                : [
                    `Monthly top-up ₹${Math.round(opt.monthly)}`,
                    `Direct-routed SIP saves ₹${Math.round(annualDragSaved)}/yr in TER drag`,
                  ],
        }
      })

  const ledger = rankPaths(pathDrafts)
  const verdict = buildVerdict(
    reframeFired || !projection.feasible ? 'repriced_goals' : 'goal_clears',
    ledger,
    objections,
  )

  return {
    positions,
    ledger,
    verdict,
    feasible: projection.feasible,
    eligibility,
  }
}
