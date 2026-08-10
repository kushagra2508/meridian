import { useState, type FormEvent } from 'react'
import { formatINRPlain, parseINRInput } from '../../edge/lib/format'
import { useEdgeDispatch, useEdgeState } from '../../edge/store'
import { Icon } from '../Icon'

const PURPOSES = ['retirement', 'education', 'property', 'legacy'] as const

const SENTENCE_INPUT =
  'border-0 border-b border-secondary bg-transparent px-1 text-center font-data-lg text-data-lg text-primary outline-none transition-[border-width] focus:border-b-2 focus:outline-none'

export function GoalStep() {
  const { goal } = useEdgeState()
  const dispatch = useEdgeDispatch()
  const [error, setError] = useState<string | null>(null)

  function submit(e: FormEvent) {
    e.preventDefault()
    if (goal.year <= 2026) {
      setError('Goal year must be after 2026.')
      return
    }
    if (goal.amount <= 0) {
      setError('Goal amount must be greater than zero.')
      return
    }
    setError(null)
    dispatch({ type: 'SET_SCREEN', screen: 'eligibility' })
  }

  function shiftYear(delta: number) {
    setError(null)
    dispatch({ type: 'SET_GOAL', goal: { year: goal.year + delta } })
  }

  return (
    <div className="flex w-full flex-col gap-stack-loose">
      <div className="flex items-center gap-stack-compact self-start">
        <span className="rounded border border-rule bg-secondary-container px-2 py-1 font-label-caps text-label-caps uppercase text-on-secondary-container">
          Pre-filled from intake · editable
        </span>
      </div>

      <h1 className="font-display-lg text-display-lg tracking-tight text-ink">Stated goal</h1>

      <form
        onSubmit={submit}
        className="flex flex-col gap-stack-dense border-l border-rule py-stack-compact pl-stack-dense"
      >
        <div className="font-headline-md text-[28px] leading-[1.6] text-ink">
          I want{' '}
          <input
            aria-label="Amount"
            className={`${SENTENCE_INPUT} w-[200px]`}
            value={formatINRPlain(goal.amount)}
            onChange={(e) => {
              setError(null)
              dispatch({ type: 'SET_GOAL', goal: { amount: parseINRInput(e.target.value) } })
            }}
          />{' '}
          by{' '}
          <span className="inline-flex items-center">
            <button
              type="button"
              aria-label="Decrease year"
              onClick={() => shiftYear(-1)}
              className="px-1 align-middle text-secondary transition-colors hover:text-primary"
            >
              <Icon name="remove" className="text-[20px]" />
            </button>
            <input
              aria-label="Year"
              inputMode="numeric"
              className={`${SENTENCE_INPUT} w-[80px]`}
              value={goal.year}
              onChange={(e) => {
                setError(null)
                dispatch({
                  type: 'SET_GOAL',
                  goal: { year: Number(e.target.value.replace(/[^\d]/g, '')) || 0 },
                })
              }}
            />
            <button
              type="button"
              aria-label="Increase year"
              onClick={() => shiftYear(1)}
              className="px-1 align-middle text-secondary transition-colors hover:text-primary"
            >
              <Icon name="add" className="text-[20px]" />
            </button>
          </span>{' '}
          for{' '}
          <select
            aria-label="Purpose"
            className={`${SENTENCE_INPUT} min-w-[150px] cursor-pointer appearance-none`}
            value={goal.purpose}
            onChange={(e) => dispatch({ type: 'SET_GOAL', goal: { purpose: e.target.value } })}
          >
            {PURPOSES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          .
        </div>

        <div className="mt-stack-dense w-full">
          <label
            htmlFor="goal-notes"
            className="mb-stack-compact block font-label-caps text-label-caps uppercase text-on-surface-variant"
          >
            Additional notes
          </label>
          <textarea
            id="goal-notes"
            rows={3}
            placeholder="Anything else we should know..."
            value={goal.note}
            onChange={(e) => dispatch({ type: 'SET_GOAL', goal: { note: e.target.value } })}
            className="w-full resize-none rounded border border-rule bg-surface-container-low p-stack-dense font-body-md text-body-md text-ink transition-colors focus:border-secondary focus:outline-none"
          />
        </div>

        {error ? (
          <p role="alert" className="font-body-md text-body-md text-error">
            {error}
          </p>
        ) : null}

        <div className="mt-stack-dense flex flex-wrap justify-between gap-3">
          <button
            type="button"
            onClick={() => dispatch({ type: 'SET_SCREEN', screen: 'position' })}
            className="border-b border-secondary-container pb-[2px] font-label-caps text-label-caps uppercase tracking-wider text-on-surface-variant transition-colors hover:border-ink hover:text-ink"
          >
            Back to position
          </button>
          <button
            type="submit"
            className="flex items-center gap-2 rounded bg-primary px-stack-loose py-3 font-label-caps text-label-caps uppercase text-on-primary transition-colors hover:bg-primary-container focus:outline-none focus:ring-2 focus:ring-secondary focus:ring-offset-2 focus:ring-offset-background"
          >
            Test reachability
            <Icon name="arrow_forward" className="text-[16px]" />
          </button>
        </div>
      </form>
    </div>
  )
}
