import { useState, type ReactNode } from 'react'
import { FLOW_STEPS, stepIndex } from '../../statute/flow'
import { useStatuteDispatch, useStatuteState } from '../../statute/store'
import { Icon } from '../Icon'

/**
 * Navigation shell for the workspace screens. Steps ahead of the current one
 * are not reachable — the flow only moves forward on an explicit action.
 */
export function StatuteChrome({ children }: { children: ReactNode }) {
  const [navOpen, setNavOpen] = useState(false)

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background font-body-md text-on-surface antialiased">
      {navOpen ? (
        <button
          type="button"
          aria-label="Close navigation"
          onClick={() => setNavOpen(false)}
          className="fixed inset-0 z-30 bg-inverse-surface/40 md:hidden"
        />
      ) : null}

      <FlowNav open={navOpen} onNavigate={() => setNavOpen(false)} />

      <main className="relative flex h-full flex-1 flex-col overflow-hidden md:ml-[240px]">
        <TopBar onOpenNav={() => setNavOpen(true)} />
        {children}
      </main>
    </div>
  )
}

function FlowNav({ open, onNavigate }: { open: boolean; onNavigate: () => void }) {
  const { screen } = useStatuteState()
  const dispatch = useStatuteDispatch()
  const current = stepIndex(screen)

  return (
    <nav
      aria-label="STATUTE flow"
      className={`fixed left-0 top-0 z-40 flex h-screen w-[240px] flex-col border-r border-rule bg-surface-container-low py-stack-dense transition-transform duration-200 md:translate-x-0 ${
        open ? 'translate-x-0' : '-translate-x-full'
      }`}
    >
      <div className="mb-stack-loose px-stack-dense">
        <h1 className="font-headline-sm text-headline-sm tracking-tight text-primary">STATUTE</h1>
        <p className="mt-1 font-data-md text-data-md text-on-surface-variant">Wealth Engine v1.2</p>
      </div>

      <ol className="flex flex-1 flex-col gap-1">
        {FLOW_STEPS.map((step, i) => {
          const active = i === current
          const reachable = i <= current
          return (
            <li key={step.id}>
              <button
                type="button"
                disabled={!reachable}
                aria-current={active ? 'step' : undefined}
                onClick={() => {
                  dispatch({ type: 'SET_SCREEN', screen: step.id })
                  onNavigate()
                }}
                className={`flex w-full items-center gap-3 px-stack-dense py-2 text-left transition-colors ${
                  active
                    ? 'border-r-2 border-secondary-container bg-primary text-on-primary'
                    : reachable
                      ? 'text-on-surface-variant hover:bg-surface-variant'
                      : 'cursor-not-allowed text-outline-variant'
                }`}
              >
                <Icon name={step.icon} className="text-[18px]" />
                <span className="font-label-caps text-label-caps uppercase">{step.label}</span>
              </button>
            </li>
          )
        })}
      </ol>

      <div className="my-stack-dense px-stack-dense">
        <button
          type="button"
          onClick={() => {
            dispatch({ type: 'RESET' })
            onNavigate()
          }}
          className="w-full rounded bg-primary py-2 font-label-caps text-label-caps uppercase text-on-primary transition-opacity hover:opacity-90"
        >
          New Scenario
        </button>
      </div>
    </nav>
  )
}

function TopBar({ onOpenNav }: { onOpenNav: () => void }) {
  const { handoff } = useStatuteState()

  return (
    <header className="sticky top-0 z-20 flex h-20 w-full shrink-0 items-center justify-between border-b border-rule bg-background px-margin-page">
      <div className="flex items-center gap-stack-dense">
        <button
          type="button"
          onClick={onOpenNav}
          aria-label="Open navigation"
          className="text-on-surface-variant transition-colors hover:text-primary md:hidden"
        >
          <Icon name="menu" />
        </button>
        <span className="font-display-lg text-[32px] leading-none tracking-tighter text-primary lg:text-display-lg">
          STATUTE
        </span>
      </div>

      <div className="flex items-center gap-stack-dense">
        <span className="hidden font-data-md text-data-md text-on-surface-variant lg:inline">
          {handoff.persona}
        </span>
        <span className="inline-flex items-center rounded bg-primary px-2 py-1 font-label-caps text-[10px] uppercase tracking-widest text-on-primary">
          {handoff.pursueDecision}
        </span>
      </div>
    </header>
  )
}
