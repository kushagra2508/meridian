import type { AssetKey, Handoff, Position } from '../types'

const LTCG_EXEMPTION = 125_000
const LTCG_RATE = 0.125
const STCG_RATE = 0.2
const GOLD_LTCG_RATE = 0.125
const CESS = 0.04
const SURCHARGE_CAP_EQUITY = 0.15

const SLAB: Record<string, number> = {
  '<50L': 0.3,
  '50L-1Cr': 0.3,
  '1Cr-2Cr': 0.3,
}

export type TaxLine = {
  amount: number
  section: string
  label: string
}

export type TaxResult = {
  embeddedGain: number
  baseTax: number
  surcharge: number
  cess: number
  totalTax: number
  lines: TaxLine[]
  fyStagerSaving: number | null
}

function surchargeRate(incomeBand: string, isEquityGain: boolean): number {
  // Simplified band: mid/high income → 15%, capped for 111A/112A.
  const base = incomeBand === '<50L' ? 0.1 : 0.15
  return isEquityGain ? Math.min(base, SURCHARGE_CAP_EQUITY) : base
}

function equityTax(gain: number, holdingLt12m: boolean): TaxLine {
  if (holdingLt12m) {
    return {
      amount: gain * STCG_RATE,
      section: '§111A',
      label: 'STCG equity',
    }
  }
  const taxable = Math.max(0, gain - LTCG_EXEMPTION)
  return {
    amount: taxable * LTCG_RATE,
    section: '§112A',
    label: 'LTCG equity',
  }
}

export function fyStager(gain: number): number | null {
  if (gain <= LTCG_EXEMPTION) return null
  const saving = Math.min(gain - LTCG_EXEMPTION, LTCG_EXEMPTION) * LTCG_RATE
  return saving
}

/** Tax on rupees moved out of a sleeve (default LTCG for equity). */
export function priceSwitchTax(
  switchAmount: number,
  sleeve: AssetKey,
  position: Position,
  handoff: Handoff,
  holdingLt12m = false,
): TaxResult {
  const embeddedGain = switchAmount * position.unrealisedGainPct
  const lines: TaxLine[] = []
  let baseTax = 0
  let isEquityGain = false

  if (switchAmount <= 0 || embeddedGain <= 0) {
    return {
      embeddedGain: Math.max(0, embeddedGain),
      baseTax: 0,
      surcharge: 0,
      cess: 0,
      totalTax: 0,
      lines: [
        {
          amount: 0,
          section: '§112A',
          label: 'Below exemption / no switch',
        },
      ],
      fyStagerSaving: null,
    }
  }

  if (sleeve === 'equity_mf' || sleeve === 'direct_equity') {
    isEquityGain = true
    const line = equityTax(embeddedGain, holdingLt12m)
    lines.push(line)
    baseTax = line.amount
  } else if (sleeve === 'debt_mf' || sleeve === 'fd_cash') {
    const rate = SLAB[handoff.declaredIncomeBand] ?? 0.3
    const line: TaxLine = {
      amount: embeddedGain * rate,
      section: 'slab',
      label: `Debt/FD at ${Math.round(rate * 100)}% slab`,
    }
    lines.push(line)
    baseTax = line.amount
  } else if (sleeve === 'gold') {
    const line: TaxLine = {
      amount: embeddedGain * GOLD_LTCG_RATE,
      section: 'LTCG gold',
      label: 'Gold LTCG 12.5% after 24m',
    }
    lines.push(line)
    baseTax = line.amount
  } else {
    // real_estate: out of pricing scope for switch model
    return {
      embeddedGain,
      baseTax: 0,
      surcharge: 0,
      cess: 0,
      totalTax: 0,
      lines: [
        {
          amount: 0,
          section: 'n/a',
          label: 'Real estate switch not priced',
        },
      ],
      fyStagerSaving: null,
    }
  }

  const surRate = surchargeRate(handoff.declaredIncomeBand, isEquityGain)
  const surcharge = baseTax * surRate
  const cess = (baseTax + surcharge) * CESS
  const totalTax = baseTax + surcharge + cess
  const fy =
    isEquityGain && !holdingLt12m ? fyStager(embeddedGain) : null

  return {
    embeddedGain,
    baseTax,
    surcharge,
    cess,
    totalTax: Math.max(0, totalTax),
    lines,
    fyStagerSaving: fy,
  }
}
