import reference from '../data/reference.json'
import type { Position } from '../types'

export type DragResult = {
  mfValue: number
  distributorHeld: number
  annualDrag: number
  outOfScopeValue: number
  scopeNote: string
}

export function runDrag(position: Position): DragResult {
  const { totalWealth, alloc, channel } = position
  const mfValue = (alloc.equity_mf + alloc.debt_mf) * totalWealth
  const distributorHeld = mfValue * channel.distributor
  const annualDrag =
    alloc.equity_mf * totalWealth * channel.distributor * reference.ter_spread.equity_mf +
    alloc.debt_mf * totalWealth * channel.distributor * reference.ter_spread.debt_mf
  const outOfScopeValue = totalWealth - mfValue

  return {
    mfValue,
    distributorHeld,
    annualDrag,
    outOfScopeValue,
    scopeNote: reference.ter_spread.scope_note,
  }
}

/**
 * TER drag avoided on a fresh annual contribution (e.g. a Rethink top-up SIP)
 * if it is routed Direct instead of following the book's current distributor
 * share. Mirrors runDrag's rate, scaled to the new money and split across the
 * MF sleeves in the same proportion the existing book already holds them.
 */
export function dragSavedOnNewFlow(position: Position, annualAmount: number): number {
  if (annualAmount <= 0) return 0
  const { alloc, channel } = position
  const mfWeight = alloc.equity_mf + alloc.debt_mf
  if (mfWeight <= 0) return 0

  const equityShare = alloc.equity_mf / mfWeight
  const debtShare = alloc.debt_mf / mfWeight
  const blendedTerSpread =
    equityShare * reference.ter_spread.equity_mf + debtShare * reference.ter_spread.debt_mf

  return annualAmount * channel.distributor * blendedTerSpread
}
