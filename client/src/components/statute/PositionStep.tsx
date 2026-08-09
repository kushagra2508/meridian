import { runDrag } from '../../statute/engine/drag'
import { formatINR, formatINRPlain, formatPct, parseINRInput } from '../../statute/lib/format'
import { useStatuteDispatch, useStatuteState } from '../../statute/store'
import type { AssetKey } from '../../statute/types'
import { Icon } from '../Icon'

const ROWS: { key: AssetKey; label: string; tone: string }[] = [
  { key: 'equity_mf', label: 'Equity MFs', tone: 'bg-primary' },
  { key: 'debt_mf', label: 'Debt MFs', tone: 'bg-primary/80' },
  { key: 'fd_cash', label: 'Fixed deposits', tone: 'bg-primary/60' },
  { key: 'direct_equity', label: 'Direct equity', tone: 'bg-secondary-container' },
  { key: 'gold', label: 'Gold (SGB/physical)', tone: 'bg-secondary' },
  { key: 'real_estate', label: 'Real estate (inv)', tone: 'bg-surface-dim' },
]

export function PositionStep() {
  const { position } = useStatuteState()
  const dispatch = useStatuteDispatch()
  const drag = runDrag(position)

  const allocSum = ROWS.reduce((acc, row) => acc + position.alloc[row.key], 0)
  // Mirrors the committee's illiquid definition: gold is treated as half-liquid.
  const illiquidFraction = position.alloc.real_estate + position.alloc.gold * 0.5
  const liquidFraction = Math.max(0, 1 - illiquidFraction)

  return (
    <div className="flex flex-1 flex-col overflow-hidden lg:flex-row">
      <div className="flex w-full flex-col overflow-y-auto bg-background lg:w-[60%]">
        <div className="mx-auto w-full max-w-4xl p-margin-page">
          <div className="mb-stack-loose flex flex-wrap items-end justify-between gap-3 border-b border-rule pb-stack-compact">
            <h2 className="font-headline-md text-headline-md text-primary">Observed position</h2>
            <button
              type="button"
              onClick={() => dispatch({ type: 'LOAD_TYPICAL_P2' })}
              className="flex items-center gap-2 border border-rule bg-surface px-3 py-1.5 font-label-caps text-label-caps uppercase text-on-surface-variant transition-colors hover:text-secondary"
            >
              <Icon name="download" className="text-[14px]" />
              Load typical allocation for P2
            </button>
          </div>

          <div className="mb-stack-loose grid grid-cols-1 gap-stack-compact md:grid-cols-3">
            <SourceTile
              icon="upload_file"
              title="Upload holdings"
              caption="CSV, PDF, Excel"
              state="idle"
            />
            <SourceTile
              icon="keyboard"
              title="Enter manually"
              caption="Active workspace"
              state="selected"
            />
            <SourceTile
              icon="account_tree"
              title="Account Aggregator"
              caption="FIP integration"
              state="disabled"
              flag="Consent rail · production only"
            />
          </div>

          <div className="mb-stack-loose border border-rule bg-surface-container-low p-stack-dense">
            <label className="flex flex-wrap items-baseline gap-x-2 font-headline-sm text-headline-sm leading-relaxed text-primary">
              <span>Total wealth is currently assessed at</span>
              <input
                aria-label="Total wealth"
                value={formatINRPlain(position.totalWealth)}
                onChange={(e) =>
                  dispatch({
                    type: 'SET_POSITION',
                    position: { totalWealth: parseINRInput(e.target.value) },
                  })
                }
                className="inline-block min-w-[200px] border-b-2 border-secondary-container bg-transparent px-1 pb-1 font-data-lg text-data-lg text-primary outline-none transition-colors focus:border-primary focus:bg-surface-container-lowest"
              />
              <span>across all known vehicles.</span>
            </label>
          </div>

          <div className="mb-stack-loose">
            <div className="mb-2 flex items-end justify-between">
              <h4 className="font-label-caps text-label-caps uppercase text-on-surface-variant">
                Asset class allocation
              </h4>
              <span className="rounded-sm bg-tertiary-fixed px-2 py-0.5 font-data-md text-[12px] text-primary">
                {(allocSum * 100).toFixed(2)}%
              </span>
            </div>
            <div className="flex h-1.5 w-full overflow-hidden border border-rule bg-surface">
              {ROWS.map((row) => (
                <div
                  key={row.key}
                  className={`h-full ${row.tone}`}
                  style={{ width: `${position.alloc[row.key] * 100}%` }}
                />
              ))}
            </div>
          </div>

          <div className="flex flex-col border-t border-rule">
            {ROWS.map((row) => (
              <div
                key={row.key}
                className="-mx-2 flex flex-wrap items-center border-b border-rule px-2 py-stack-compact transition-colors hover:bg-surface-container-low"
              >
                <div className="flex w-1/3 min-w-[140px] items-center gap-2 font-body-md text-body-md text-primary">
                  <span className={`inline-block h-2 w-2 rounded-full ${row.tone}`} />
                  {row.label}
                </div>
                <div className="flex-1 px-stack-dense">
                  <input
                    type="range"
                    aria-label={row.label}
                    className="w-full"
                    min={0}
                    max={100}
                    value={Math.round(position.alloc[row.key] * 100)}
                    onChange={(e) =>
                      dispatch({
                        type: 'SET_ALLOC',
                        alloc: { [row.key]: Number(e.target.value) / 100 },
                      })
                    }
                    onBlur={() => dispatch({ type: 'NORMALIZE_ALLOC' })}
                    onMouseUp={() => dispatch({ type: 'NORMALIZE_ALLOC' })}
                    onTouchEnd={() => dispatch({ type: 'NORMALIZE_ALLOC' })}
                  />
                </div>
                <div className="w-16 text-right font-data-md text-data-md text-primary">
                  {(position.alloc[row.key] * 100).toFixed(1)}%
                </div>
                <div className="w-32 text-right font-data-md text-data-md text-on-surface-variant">
                  {formatINR(position.totalWealth * position.alloc[row.key])}
                </div>
              </div>
            ))}
          </div>

          <div className="mb-stack-loose mt-stack-loose">
            <h4 className="mb-stack-compact border-b border-rule pb-2 font-label-caps text-label-caps uppercase text-on-surface-variant">
              Execution channel mix
            </h4>
            <div className="flex flex-col">
              <div className="-mx-2 flex items-center px-2 py-stack-compact transition-colors hover:bg-surface-container-low">
                <div className="w-1/3 font-body-md text-body-md text-primary">Direct / RIA</div>
                <div className="flex-1 px-stack-dense">
                  <input
                    type="range"
                    aria-label="Direct share"
                    className="w-full"
                    min={0}
                    max={100}
                    value={Math.round(position.channel.direct * 100)}
                    onChange={(e) =>
                      dispatch({ type: 'SET_CHANNEL', direct: Number(e.target.value) / 100 })
                    }
                  />
                </div>
                <div className="w-16 text-right font-data-md text-data-md text-primary">
                  {formatPct(position.channel.direct)}
                </div>
              </div>
              <div className="-mx-2 flex items-center px-2 py-stack-compact transition-colors hover:bg-surface-container-low">
                <div className="w-1/3 font-body-md text-body-md text-secondary">Distributor-led</div>
                <div className="flex-1 px-stack-dense">
                  <input
                    type="range"
                    aria-label="Distributor share"
                    className="w-full"
                    min={0}
                    max={100}
                    value={Math.round(position.channel.distributor * 100)}
                    onChange={(e) =>
                      dispatch({ type: 'SET_CHANNEL', direct: 1 - Number(e.target.value) / 100 })
                    }
                  />
                </div>
                <div className="w-16 text-right font-data-md text-data-md text-secondary">
                  {formatPct(position.channel.distributor)}
                </div>
              </div>
            </div>
          </div>

          <div className="mb-stack-loose">
            <h4 className="mb-stack-compact border-b border-rule pb-2 font-label-caps text-label-caps uppercase text-on-surface-variant">
              Advanced
            </h4>
            <div className="-mx-2 flex items-center px-2 py-stack-compact">
              <div className="w-1/3 font-body-md text-body-md text-primary">
                Unrealised gain
                <span className="ml-2 rounded-sm bg-secondary-container px-1.5 py-0.5 font-citation text-citation uppercase tracking-widest text-on-secondary-container">
                  Assumption
                </span>
              </div>
              <div className="flex-1 px-stack-dense">
                <input
                  type="range"
                  aria-label="Unrealised gain percentage"
                  className="w-full"
                  min={0}
                  max={80}
                  value={Math.round(position.unrealisedGainPct * 100)}
                  onChange={(e) =>
                    dispatch({
                      type: 'SET_POSITION',
                      position: { unrealisedGainPct: Number(e.target.value) / 100 },
                    })
                  }
                />
              </div>
              <div className="w-16 text-right font-data-md text-data-md text-primary">
                {formatPct(position.unrealisedGainPct, 0)}
              </div>
            </div>
            <p className="mt-1 px-2 font-citation text-citation uppercase leading-relaxed text-on-surface-variant">
              No source publishes embedded gain per client. Default 25%, adjustable.
            </p>
          </div>

          <div className="flex justify-end border-t border-rule pt-stack-dense">
            <button
              type="button"
              onClick={() => {
                dispatch({ type: 'NORMALIZE_ALLOC' })
                dispatch({ type: 'SET_SCREEN', screen: 'goal' })
              }}
              className="flex items-center gap-2 rounded-[2px] bg-primary px-8 py-3 font-label-caps text-label-caps uppercase tracking-wider text-on-primary transition-colors hover:bg-ink"
            >
              Continue to goal
              <Icon name="arrow_forward" className="text-[16px]" />
            </button>
          </div>

          <div className="h-20" />
        </div>
      </div>

      <aside className="flex w-full flex-col overflow-y-auto border-t border-rule bg-surface lg:w-[40%] lg:border-l lg:border-t-0">
        <div className="flex h-full flex-col p-margin-page">
          <div className="mb-stack-loose flex items-center justify-between">
            <h3 className="font-label-caps text-label-caps uppercase tracking-widest text-on-surface-variant">
              Live ledger summary
            </h3>
            <Icon name="sync" className="text-[18px] text-on-surface-variant" />
          </div>

          <div className="mt-4 flex flex-col gap-stack-loose">
            <div className="flex flex-col gap-1 border-b border-rule pb-stack-dense">
              <span className="font-body-md text-body-md text-on-surface-variant">
                Computed total wealth
              </span>
              <div className="flex items-baseline font-data-lg text-[32px] font-medium leading-none tracking-tight text-primary">
                {formatINRPlain(position.totalWealth)}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-stack-dense border-b border-rule pb-stack-dense">
              <div className="flex flex-col gap-1 border-r border-rule pr-stack-dense">
                <span className="font-body-md text-[13px] text-on-surface-variant">
                  Highly liquid <span className="ml-1 font-citation text-citation">[&lt;30D]</span>
                </span>
                <div className="mt-1 font-data-lg text-data-lg text-primary">
                  {formatINRPlain(position.totalWealth * liquidFraction)}
                </div>
                <span className="font-data-md text-[12px] text-primary/70">
                  {formatPct(liquidFraction)} of total
                </span>
              </div>
              <div className="flex flex-col gap-1 pl-stack-compact">
                <span className="font-body-md text-[13px] text-on-surface-variant">
                  Illiquid <span className="ml-1 font-citation text-citation">[LOCKED]</span>
                </span>
                <div className="mt-1 font-data-lg text-data-lg text-on-surface-variant">
                  {formatINRPlain(position.totalWealth * illiquidFraction)}
                </div>
                <span className="font-data-md text-[12px] text-on-surface-variant/70">
                  {formatPct(illiquidFraction)} of total
                </span>
              </div>
            </div>

            <div className="mt-4 flex flex-col gap-2 border border-l-2 border-secondary-container/30 border-l-secondary-container bg-surface-container p-stack-dense">
              <span className="flex items-center gap-1 font-label-caps text-[10px] uppercase text-secondary">
                <Icon name="warning" className="text-[12px]" />
                Distributor concentration
              </span>
              <div className="font-data-lg text-data-lg text-secondary">
                {formatINRPlain(drag.distributorHeld)}
              </div>
              {drag.annualDrag > 0 ? (
                <span className="font-body-md text-[13px] leading-snug text-secondary/80">
                  {formatPct(position.channel.distributor, 0)} of mutual-fund assets are held
                  through external distributors, costing{' '}
                  <span className="inline-block font-data-md text-[12px]">
                    {formatINRPlain(drag.annualDrag)}/yr
                  </span>{' '}
                  in recurring drag.
                </span>
              ) : (
                <span className="font-body-md text-[13px] leading-snug text-secondary/80">
                  No mutual-fund distributor drag applies on this book.
                </span>
              )}
            </div>
          </div>

          <div className="flex-1" />

          <div className="mt-stack-loose border-t border-dashed border-rule pt-stack-dense">
            <p className="text-justify font-citation text-citation uppercase leading-relaxed text-on-surface-variant hyphens-auto">
              [Note] {drag.scopeNote} Real estate is held as corpus value with no sourceable
              per-client valuation, so it neither grows nor contributes liquidity.
            </p>
          </div>
        </div>
      </aside>
    </div>
  )
}

function SourceTile({
  icon,
  title,
  caption,
  state,
  flag,
}: {
  icon: string
  title: string
  caption: string
  state: 'idle' | 'selected' | 'disabled'
  flag?: string
}) {
  if (state === 'disabled') {
    return (
      <div className="pointer-events-none relative flex flex-col gap-2 border border-rule bg-surface p-stack-dense opacity-50">
        {flag ? (
          <div className="absolute right-2 top-2 rounded-sm bg-secondary-container px-1.5 py-0.5 font-citation text-citation uppercase tracking-widest text-on-secondary-container">
            {flag}
          </div>
        ) : null}
        <div className="mt-3 flex items-start justify-between text-on-surface-variant">
          <Icon name={icon} />
        </div>
        <div>
          <h3 className="font-body-md text-body-md font-bold text-on-surface-variant">{title}</h3>
          <p className="mt-1 font-data-md text-[12px] text-on-surface-variant">{caption}</p>
        </div>
      </div>
    )
  }

  const selected = state === 'selected'
  return (
    <div
      className={`flex flex-col gap-2 border border-rule p-stack-dense ${
        selected
          ? 'border-l-2 border-l-primary bg-surface-container'
          : 'group cursor-pointer bg-surface transition-colors hover:bg-surface-container'
      }`}
    >
      <div
        className={`flex items-start justify-between ${
          selected ? 'text-primary' : 'text-on-surface-variant group-hover:text-primary'
        }`}
      >
        <Icon name={icon} />
        {selected ? <span className="mt-1 h-2 w-2 rounded-full bg-primary" /> : null}
      </div>
      <div>
        <h3 className="font-body-md text-body-md font-bold text-primary">{title}</h3>
        <p className="mt-1 font-data-md text-[12px] text-on-surface-variant">{caption}</p>
      </div>
    </div>
  )
}
