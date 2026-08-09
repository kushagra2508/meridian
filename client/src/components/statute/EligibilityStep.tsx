import { useEffect, useState } from 'react'
import { formatINRPlain } from '../../statute/lib/format'
import { useStatuteDispatch, useStatuteState } from '../../statute/store'

const DWELL_MS = 3000

export function EligibilityStep() {
  const { committee, position } = useStatuteState()
  const dispatch = useStatuteDispatch()
  const [progress, setProgress] = useState(0)
  const { ladder, highestEligible } = committee.eligibility

  useEffect(() => {
    const start = window.setTimeout(() => setProgress(100), 50)
    const advance = window.setTimeout(() => {
      dispatch({ type: 'SET_SCREEN', screen: 'committee' })
    }, DWELL_MS)
    return () => {
      window.clearTimeout(start)
      window.clearTimeout(advance)
    }
  }, [dispatch])

  const markerIndex = Math.max(
    0,
    ladder.findIndex((lane) => lane.lane === highestEligible),
  )
  const markerLeft = `${((markerIndex + 0.5) / ladder.length) * 100}%`

  return (
    <div className="flex w-full flex-col items-center">
      <div className="mb-stack-loose w-full text-center">
        <h1 className="font-display-lg text-display-lg tracking-tighter text-primary">
          Product shelf
        </h1>
      </div>

      <div className="relative flex w-full flex-col items-center">
        <div className="relative flex h-32 w-full border border-rule bg-background">
          {ladder.map((lane, i) => (
            <div
              key={lane.lane}
              className={`relative flex flex-1 flex-col items-center justify-center p-stack-dense ${
                i < ladder.length - 1 ? 'border-r border-rule' : ''
              } ${
                lane.eligible
                  ? 'z-10 before:absolute before:inset-0 before:-m-px before:border-2 before:border-primary'
                  : 'bg-surface-variant opacity-40'
              }`}
            >
              <span className="mb-base font-label-caps text-label-caps uppercase tracking-widest text-on-surface-variant">
                {lane.label}
              </span>
              <span
                className={`font-data-md text-data-md ${
                  lane.eligible ? 'text-on-background' : 'text-on-surface-variant'
                }`}
              >
                {lane.minimum === 0 ? 'No minimum' : formatINRPlain(lane.minimum)}
              </span>
            </div>
          ))}
        </div>

        <div className="relative mt-stack-compact h-12 w-full">
          <div
            className="absolute flex -translate-x-1/2 flex-col items-center"
            style={{ left: markerLeft }}
          >
            <div className="mb-1 h-0 w-0 border-x-[6px] border-b-[8px] border-x-transparent border-b-primary" />
            <span className="font-data-md text-data-md font-medium text-primary">
              {formatINRPlain(position.totalWealth)}
            </span>
            <span className="font-citation text-citation uppercase text-outline">Client wealth</span>
          </div>
        </div>
      </div>

      <div className="mt-stack-loose flex flex-col items-center gap-stack-dense">
        <p className="font-headline-sm text-headline-sm italic text-on-surface-variant">
          Eligibility is set by SEBI minimums, not by Meridian.
        </p>
        <button
          type="button"
          onClick={() => dispatch({ type: 'SET_SCREEN', screen: 'committee' })}
          className="border-b border-secondary-container pb-[2px] font-label-caps text-label-caps uppercase tracking-wider text-on-surface-variant transition-colors hover:border-ink hover:text-ink"
        >
          Skip to deliberation
        </button>
      </div>

      <div className="fixed bottom-0 left-0 h-px w-full bg-rule">
        <div
          className="h-full bg-primary transition-[width] ease-linear"
          style={{ width: `${progress}%`, transitionDuration: `${DWELL_MS}ms` }}
        />
      </div>
    </div>
  )
}
