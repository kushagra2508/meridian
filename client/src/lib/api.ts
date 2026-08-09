import type {
  AgentEvent,
  AgentRunHandle,
  IntelligenceReports,
  PortfolioSeries,
  PortfolioSummary,
  SeriesRange,
} from './types'

const API_BASE = import.meta.env.VITE_API_URL ?? '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })

  if (!response.ok) {
    throw new Error(`Request to ${path} failed with ${response.status}`)
  }

  return (await response.json()) as T
}

export function getPortfolioSummary(signal?: AbortSignal) {
  return request<PortfolioSummary>('/portfolio/summary', { signal })
}

export function getPortfolioSeries(range: SeriesRange, signal?: AbortSignal) {
  return request<PortfolioSeries>(`/portfolio/series?range=${range}`, { signal })
}

export function getIntelligenceReports(signal?: AbortSignal) {
  return request<IntelligenceReports>('/intelligence/reports', { signal })
}

export function startAgentRun(prompt: string) {
  return request<AgentRunHandle>('/agent/runs', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  })
}

export function stopAgentRun(runId: string) {
  return request<{ ok: boolean }>(`/agent/runs/${runId}/stop`, { method: 'POST' })
}

const AGENT_EVENT_TYPES = [
  'log',
  'tool_call',
  'tool_progress',
  'tool_result',
  'message',
  'status',
  'done',
] as const

export interface AgentStreamHandlers {
  onEvent: (event: AgentEvent) => void
  onError?: (error: Error) => void
  onClose?: () => void
}

/**
 * Subscribes to a run's SSE stream. EventSource retries on its own, so the
 * source is closed explicitly once the run reports `done`.
 */
export function subscribeToAgentRun(
  runId: string,
  { onEvent, onError, onClose }: AgentStreamHandlers,
): () => void {
  const source = new EventSource(`${API_BASE}/agent/runs/${runId}/stream`)
  let closed = false

  const close = () => {
    if (closed) return
    closed = true
    source.close()
    onClose?.()
  }

  for (const type of AGENT_EVENT_TYPES) {
    source.addEventListener(type, (event) => {
      try {
        const parsed = JSON.parse((event as MessageEvent<string>).data) as AgentEvent
        onEvent(parsed)
        if (parsed.type === 'done') close()
      } catch {
        onError?.(new Error(`Could not parse agent event of type "${type}"`))
      }
    })
  }

  source.addEventListener('error', () => {
    if (source.readyState === EventSource.CLOSED) {
      close()
      return
    }
    onError?.(new Error('Lost connection to the agent stream'))
    close()
  })

  return close
}
