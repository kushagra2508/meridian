import { useEffect, useRef, useState } from 'react'
import { Icon } from '../Icon'
import type { AgentStatus, ConsoleItem } from '../../hooks/useAgentRun'

const DEFAULT_PROMPT = 'Can we fund tuition with the current plan?'

interface AgentConsoleProps {
  items: ConsoleItem[]
  status: AgentStatus
  running: boolean
  error: string | null
  onStart: (prompt: string) => void
  onHalt: () => void
}

export function AgentConsole({
  items,
  status,
  running,
  error,
  onStart,
  onHalt,
}: AgentConsoleProps) {
  const [draft, setDraft] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const node = scrollRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [items, status])

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    const prompt = draft.trim()
    if (!prompt || running) return
    setDraft('')
    onStart(prompt)
  }

  return (
    <aside className="flex h-full w-full min-w-0 shrink-0 flex-col overflow-hidden rounded-xl border border-outline bg-console-bg shadow-lg lg:w-[34%] lg:min-w-[340px] lg:max-w-[420px]">
      <div className="flex shrink-0 items-center justify-between border-b border-console-border bg-console-panel p-gutter">
        <div className="flex items-center gap-3">
          <div className="relative flex h-10 w-10 items-center justify-center rounded-full border border-secondary-fixed bg-console-bg text-secondary-fixed">
            <Icon name="psychology" filled />
            <span
              className={`absolute -bottom-1 -right-1 h-3 w-3 rounded-full border-2 border-console-panel ${
                running ? 'bg-secondary-fixed pulse-active' : 'bg-console-muted'
              }`}
            />
          </div>
          <div>
            <h3 className="m-0 font-body text-body font-bold leading-tight text-white">
              Meridian desk
            </h3>
            <span className="font-footnote text-footnote uppercase tracking-wider text-secondary-fixed">
              {status.label}
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={onHalt}
          disabled={!running}
          title="Halt agent"
          aria-label="Halt agent"
          className="p-1 text-console-muted transition-colors hover:text-error-container disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Icon name="stop_circle" />
        </button>
      </div>

      <div
        ref={scrollRef}
        className="console-scroll flex flex-1 flex-col gap-3 overflow-y-auto p-gutter font-mono text-[12px] leading-relaxed"
      >
        {items.map((item) => (
          <ConsoleRow key={item.id} item={item} />
        ))}

        {error ? (
          <div className="rounded border border-error/50 bg-error/10 px-3 py-2 text-[#ffb4ab]">
            {error}
          </div>
        ) : null}

        <div className="mt-2 text-secondary-fixed">
          &gt; <span className={running ? 'animate-pulse' : 'opacity-40'}>_</span>
        </div>
      </div>

      <form onSubmit={submit} className="shrink-0 border-t border-console-border bg-console-panel p-gutter">
        <div className="relative">
          <input
            type="text"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            disabled={running}
            aria-label="Direct Meridian desk"
            placeholder={running ? 'Desk is working...' : DEFAULT_PROMPT}
            className="w-full rounded-lg border border-console-border bg-console-bg py-2 pl-3 pr-10 font-body text-body text-white transition-all placeholder:text-console-dim focus:border-secondary-fixed focus:outline-none focus:ring-1 focus:ring-secondary-fixed disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={running || draft.trim().length === 0}
            aria-label="Send directive"
            className="absolute right-2 top-1/2 -translate-y-1/2 text-console-muted transition-colors hover:text-secondary-fixed disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Icon name="send" className="text-[20px]" />
          </button>
        </div>
      </form>
    </aside>
  )
}

function ConsoleRow({ item }: { item: ConsoleItem }) {
  if (item.kind === 'log') {
    return (
      <div className="animate-fade-in-up text-console-muted">
        <span className="text-console-dim">{item.at}</span> [{item.source}] {item.message}
        {item.highlight ? (
          <span className="text-on-tertiary-container"> {item.highlight}</span>
        ) : null}
      </div>
    )
  }

  if (item.kind === 'message') {
    return (
      <div className="animate-fade-in-up rounded-r border-l-2 border-secondary-fixed bg-secondary-fixed/5 py-2 pl-4 pr-2 text-white">
        <div className="mb-1 text-[10px] uppercase tracking-wider text-secondary-fixed">
          {item.source} · {item.at}
        </div>
        {item.text}
      </div>
    )
  }

  if (item.kind === 'done') {
    return (
      <div className="animate-fade-in-up text-console-dim">
        <span className="text-console-dim">{item.at}</span> — {item.summary}
      </div>
    )
  }

  const active = item.status === 'running'

  return (
    <div
      className={`animate-fade-in-up border-l-2 py-1 pl-4 ${
        active ? 'rounded-r border-secondary-fixed bg-secondary-fixed/5' : 'border-console-border'
      }`}
    >
      <div
        className={`mb-1 text-[11px] ${active ? 'font-bold text-secondary-fixed' : 'text-console-dim'}`}
      >
        TOOL CALL: {item.name}({item.args})
      </div>

      {item.percent !== undefined && active ? (
        <div className="mt-2 flex flex-col gap-1 text-white">
          <div className="flex justify-between text-[10px] text-console-muted">
            <span>{item.progressLabel}</span>
            <span>{item.percent}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-console-border">
            <div
              className="h-full bg-secondary-fixed transition-[width] duration-500"
              style={{ width: `${item.percent}%` }}
            />
          </div>
        </div>
      ) : null}

      {active && item.percent === undefined ? (
        <div className="flex items-center gap-2 text-secondary-fixed/70">
          <Icon name="progress_activity" className="animate-spin text-[14px]" />
          Awaiting response...
        </div>
      ) : null}

      {item.summary ? (
        <div className="flex items-start gap-2 text-console-muted">
          <Icon
            name={item.status === 'ok' ? 'check_circle' : 'error'}
            className={`text-[14px] ${item.status === 'ok' ? 'text-secondary-fixed' : 'text-error'}`}
          />
          {item.summary}
        </div>
      ) : null}
    </div>
  )
}
