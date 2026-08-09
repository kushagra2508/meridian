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
