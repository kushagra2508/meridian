import { AGENT_GLOSSARY } from '../../edge/agents'
import { useEdgeDispatch } from '../../edge/store'
import { Icon } from '../Icon'

export function GlossaryStep() {
  const dispatch = useEdgeDispatch()

  return (
    <div className="flex flex-1 flex-col overflow-y-auto">
      <header className="border-b border-rule px-margin-page py-stack-loose">
        <p className="font-label-caps text-label-caps uppercase tracking-widest text-on-surface-variant">
          EDGE by Meridian
        </p>
        <h1 className="mt-2 font-display-lg text-display-lg text-ink">Agent glossary</h1>
        <p className="mt-2 max-w-2xl font-body-md text-body-md text-on-surface-variant">
          Positions are computed in TypeScript. Conversation is generated around those numbers.
          No figure on a card originates from an LLM.
        </p>
      </header>

      <section className="flex flex-col gap-stack-dense px-margin-page py-stack-loose">
        {AGENT_GLOSSARY.map((entry) => (
          <article
            key={entry.id}
            className="border border-rule bg-surface p-stack-dense"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-rule pb-stack-compact">
              <div>
                <h2 className="font-headline-md text-headline-md text-ink">{entry.name}</h2>
                <p className="font-data-md text-data-md text-on-surface-variant">{entry.role}</p>
              </div>
              <span className="font-label-caps text-[10px] uppercase tracking-wider text-secondary">
                Fights with · {entry.fightsWith}
              </span>
            </div>
            <p className="mt-stack-compact font-body-md text-body-md text-on-surface">
              {entry.objective}
            </p>
            <ol className="mt-stack-compact list-decimal space-y-1 pl-5 font-data-md text-[13px] leading-relaxed text-on-surface-variant">
              {entry.logic.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ol>
          </article>
        ))}

        <div className="mt-stack-dense flex justify-end">
          <button
            type="button"
            onClick={() => dispatch({ type: 'SET_SCREEN', screen: 'committee' })}
            className="inline-flex items-center gap-2 rounded bg-primary px-6 py-2 font-label-caps text-label-caps uppercase text-on-primary"
          >
            Back to deliberation
            <Icon name="gavel" className="text-[16px]" />
          </button>
        </div>
      </section>
    </div>
  )
}
