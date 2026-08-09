import { randomUUID } from 'node:crypto'
import type { AgentEvent } from '../types.js'
import type { AgentProvider, AgentRunInput } from './provider.js'

const AGENT_NAME = 'Analyst-7'

class RunAborted extends Error {}

function clockLabel(date = new Date()): string {
  return date.toTimeString().slice(0, 8)
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) return Promise.reject(new RunAborted())

  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', onAbort)
      resolve()
    }, ms)

    function onAbort() {
      clearTimeout(timer)
      reject(new RunAborted())
    }

    signal.addEventListener('abort', onAbort, { once: true })
  })
}

interface ScriptStep {
  delay: number
  build: (ctx: { toolRef: string; prompt: string }) => AgentEvent | AgentEvent[]
}

const script: ScriptStep[] = [
  {
    delay: 200,
    build: () => ({
      type: 'status',
      id: randomUUID(),
      state: 'thinking',
      label: 'Processing multi-agent flow',
    }),
  },
  {
    delay: 500,
    build: () => ({
      type: 'log',
      id: randomUUID(),
      at: clockLabel(),
      source: 'System',
      message: 'Initializing context: Portfolio_ID_883...',
    }),
  },
  {
    delay: 900,
    build: ({ prompt }) => ({
      type: 'log',
      id: randomUUID(),
      at: clockLabel(),
      source: AGENT_NAME,
      message: `Interpreting directive: "${prompt}"`,
    }),
  },
  {
    delay: 900,
    build: () => ({
      type: 'log',
      id: randomUUID(),
      at: clockLabel(),
      source: AGENT_NAME,
      message: 'Spawning sub-task:',
      highlight: 'Fetch SEC Filings',
    }),
  },
  {
    delay: 400,
    build: () => ({
      type: 'tool_call',
      id: 'tool-edgar',
      at: clockLabel(),
      name: 'get_edgar_data',
      args: 'ticker="AAPL", form="10-Q"',
      status: 'running',
    }),
  },
  {
    delay: 1400,
    build: () => ({
      type: 'tool_result',
      id: randomUUID(),
      ref: 'tool-edgar',
      status: 'ok',
      summary: '12 filings parsed, 348 KB of MD&A extracted',
    }),
  },
  {
    delay: 700,
    build: () => ({
      type: 'log',
      id: randomUUID(),
      at: clockLabel(),
      source: AGENT_NAME,
      message: 'Data retrieved. Spawning sub-task:',
      highlight: 'Run Monte Carlo Sim',
    }),
  },
  {
    delay: 400,
    build: ({ toolRef }) => ({
      type: 'tool_call',
      id: toolRef,
      at: clockLabel(),
      name: 'monte_carlo_risk',
      args: 'params={horizon: 24m, paths: 10000}',
      status: 'running',
    }),
  },
  ...[12, 28, 45, 65, 82, 96, 100].map((percent) => ({
    delay: 550,
    build: ({ toolRef }: { toolRef: string }): AgentEvent => ({
      type: 'tool_progress',
      id: randomUUID(),
      ref: toolRef,
      label: 'Iterations: 10,000',
      percent,
    }),
  })),
  {
    delay: 500,
    build: ({ toolRef }) => ({
      type: 'tool_result',
      id: randomUUID(),
      ref: toolRef,
      status: 'ok',
      summary: 'VaR (95%) 4.1% | expected shortfall 6.8%',
    }),
  },
  {
    delay: 800,
    build: () => ({
      type: 'message',
      id: randomUUID(),
      at: clockLabel(),
      source: AGENT_NAME,
      text: 'Custom-silicon cohort shows 14% higher projected margin resilience over 24 months. Recommend a 2.5% overweight to Tech Equities funded from short-duration fixed income.',
    }),
  },
  {
    delay: 400,
    build: () => [
      { type: 'status', id: randomUUID(), state: 'idle', label: 'Awaiting direction' },
      {
        type: 'done',
        id: randomUUID(),
        at: clockLabel(),
        summary: 'Run complete - 2 tools called, 1 recommendation produced',
      },
    ],
  },
]

export class MockAgentProvider implements AgentProvider {
  readonly name = 'mock'
  readonly agentName = AGENT_NAME

  async *startRun({ prompt, signal }: AgentRunInput): AsyncIterable<AgentEvent> {
    const ctx = { toolRef: `tool-mc-${randomUUID().slice(0, 8)}`, prompt }

    try {
      for (const step of script) {
        await sleep(step.delay, signal)
        const produced = step.build(ctx)
        for (const event of Array.isArray(produced) ? produced : [produced]) {
          yield event
        }
      }
    } catch (error) {
      if (error instanceof RunAborted) {
        yield {
          type: 'status',
          id: randomUUID(),
          state: 'halted',
          label: 'Halted by operator',
        }
        return
      }
      throw error
    }
  }
}
