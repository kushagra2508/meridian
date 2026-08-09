import { useEffect, useState } from 'react'
import { Icon } from '../Icon'

const rows = [
  { ticker: 'AAPL', changePct: 1.2 },
  { ticker: 'BTC', changePct: 3.4 },
  { ticker: 'NVDA', changePct: 2.1 },
  { ticker: 'GOOGL', changePct: 0.8 },
  { ticker: 'MSFT', changePct: 1.6 },
]

export function RebalancingPanel() {
  const [offset, setOffset] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => setOffset((value) => (value + 1) % rows.length), 2600)
    return () => clearInterval(timer)
  }, [])

  const top = rows[offset % rows.length]!
  const bottom = rows[(offset + 1) % rows.length]!

  return (
    <div className="hidden w-56 flex-col gap-3 md:flex">
      <Row ticker={top.ticker} changePct={top.changePct} />

      <div className="flex items-center justify-between rounded border border-primary-container/30 bg-surface-container-low p-3">
        <span className="font-table-header text-[11px] uppercase text-on-surface">
          Rebalancing...
        </span>
        <Icon name="autorenew" className="animate-spin text-sm text-primary-container" />
      </div>

      <Row ticker={bottom.ticker} changePct={bottom.changePct} />
    </div>
  )
}

function Row({ ticker, changePct }: { ticker: string; changePct: number }) {
  return (
    <div
      key={ticker}
      className="flex animate-fade-in-up items-center justify-between rounded border border-outline-variant bg-surface p-3"
    >
      <span className="font-table-header text-[11px] uppercase text-on-surface">{ticker}</span>
      <span className="font-table-header text-[11px] text-primary-container">
        +{changePct.toFixed(1)}%
      </span>
    </div>
  )
}
