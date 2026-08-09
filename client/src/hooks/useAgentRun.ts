import { useCallback, useEffect, useRef, useState } from 'react'
import { startAgentRun, stopAgentRun, subscribeToAgentRun } from '../lib/api'
import type { AgentEvent } from '../lib/types'

export type ConsoleItem =
  | { kind: 'log'; id: string; at: string; source: string; message: string; highlight?: string }
  | { kind: 'message'; id: string; at: string; source: string; text: string }
  | {
      kind: 'tool'
      id: string
      at: string
      name: string
      args: string
      status: 'running' | 'ok' | 'error'
      progressLabel?: string
      percent?: number
      summary?: string
    }
  | { kind: 'done'; id: string; at: string; summary: string }

export interface AgentStatus {
  state: 'thinking' | 'idle' | 'halted'
  label: string
}

function reduceEvent(items: ConsoleItem[], event: AgentEvent): ConsoleItem[] {
  switch (event.type) {
    case 'log':
      return [
        ...items,
        {
          kind: 'log',
          id: event.id,
          at: event.at,
          source: event.source,
          message: event.message,
          highlight: event.highlight,
        },
      ]
    case 'message':
      return [
        ...items,
        { kind: 'message', id: event.id, at: event.at, source: event.source, text: event.text },
      ]
    case 'tool_call':
      return [
        ...items,
        {
          kind: 'tool',
          id: event.id,
          at: event.at,
          name: event.name,
          args: event.args,
          status: 'running',
        },
      ]
    case 'tool_progress':
      return items.map((item) =>
        item.kind === 'tool' && item.id === event.ref
          ? { ...item, progressLabel: event.label, percent: event.percent }
          : item,
      )
    case 'tool_result':
      return items.map((item) =>
        item.kind === 'tool' && item.id === event.ref
          ? { ...item, status: event.status, summary: event.summary }
          : item,
      )
    case 'done':
      return [...items, { kind: 'done', id: event.id, at: event.at, summary: event.summary }]
    default:
      return items
  }
}

const IDLE_STATUS: AgentStatus = { state: 'idle', label: 'Standing by' }

export function useAgentRun(initialPrompt: string) {
  const [items, setItems] = useState<ConsoleItem[]>([])
  const [status, setStatus] = useState<AgentStatus>(IDLE_STATUS)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const closeRef = useRef<(() => void) | null>(null)
  const runIdRef = useRef<string | null>(null)
  const generationRef = useRef(0)

  const teardown = useCallback(() => {
    generationRef.current += 1
    closeRef.current?.()
    closeRef.current = null
    runIdRef.current = null
  }, [])

  const start = useCallback(
    async (prompt: string) => {
      teardown()
      const generation = generationRef.current

      setItems([])
      setError(null)
      setRunning(true)
      setStatus({ state: 'thinking', label: 'Connecting to engine' })

      try {
        const handle = await startAgentRun(prompt)
        if (generation !== generationRef.current) return

        runIdRef.current = handle.runId
        closeRef.current = subscribeToAgentRun(handle.runId, {
          onEvent: (event) => {
            if (generation !== generationRef.current) return
            if (event.type === 'status') {
              setStatus({ state: event.state, label: event.label })
              return
            }
            setItems((current) => reduceEvent(current, event))
          },
          onError: (streamError) => {
            if (generation !== generationRef.current) return
            setError(streamError.message)
          },
          onClose: () => {
            if (generation !== generationRef.current) return
            setRunning(false)
          },
        })
      } catch {
        if (generation !== generationRef.current) return
        setRunning(false)
        setStatus(IDLE_STATUS)
        setError('Could not reach the agent service. Is the API running?')
      }
    },
    [teardown],
  )

  const halt = useCallback(async () => {
    const runId = runIdRef.current
    teardown()
    setRunning(false)
    setStatus({ state: 'halted', label: 'Halted by operator' })
    if (runId) {
      await stopAgentRun(runId).catch(() => undefined)
    }
  }, [teardown])

  useEffect(() => {
    void start(initialPrompt)
    return teardown
    // Kicks off exactly one run when the console mounts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { items, status, running, error, start, halt }
}
