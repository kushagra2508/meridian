import { randomUUID } from 'node:crypto'
import type { AgentEvent } from '../types.js'
import type { AgentProvider, AgentRunInput } from './provider.js'

const AGENT_NAME = 'Meridian desk'

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
      label: 'Running Feasibility → Statute → Channel',
    }),
  },
  {
    delay: 400,
    build: () => ({
      type: 'log',
      id: randomUUID(),
      at: clockLabel(),
      source: 'System',
      message: 'Stage 1/3:',
      highlight: 'Feasibility',
    }),
  },
  {
    delay: 500,
    build: ({ prompt }) => ({
      type: 'log',
      id: randomUUID(),
      at: clockLabel(),
      source: 'Feasibility',
      message: `Interpreting directive: "${prompt}"`,
    }),
  },
  {
    delay: 400,
    build: () => ({
      type: 'tool_call',
      id: 'tool-goal',
      at: clockLabel(),
      name: 'goal_solver',
      args: 'target=5000000, years=7',
      status: 'running',
    }),
  },
  {
    delay: 900,
    build: () => ({
      type: 'tool_result',
      id: randomUUID(),
      ref: 'tool-goal',
      status: 'ok',
      summary: 'Projected INR 4,398,702 | shortfall INR 601,298',
    }),
  },
  {
    delay: 400,
    build: () => ({
      type: 'tool_call',
      id: 'tool-realloc',
      at: clockLabel(),
      name: 'reallocation_search',
      args: 'required_return=0.112',
      status: 'running',
    }),
  },
  {
    delay: 900,
    build: () => ({
      type: 'tool_result',
      id: randomUUID(),
      ref: 'tool-realloc',
      status: 'ok',
      summary: 'Smallest shift 29ppt; debt_liquid -> equity_mid_cap',
    }),
  },
  {
    delay: 500,
    build: () => ({
      type: 'message',
      id: randomUUID(),
      at: clockLabel(),
      source: 'Feasibility',
      text: 'Short by INR 601,298; a 29 point shift into mid-cap equity closes it.',
      report: {
        agent: 'Feasibility',
        title: 'Goal feasibility',
        headline: 'Short by INR 601,298; a 29 point shift into mid-cap equity closes it.',
        verdict: 'reachable_with_changes',
        metrics: [
          { label: 'Projected corpus', value: 'INR 4,398,702' },
          { label: 'Target', value: 'INR 5,000,000' },
          { label: 'Shortfall', value: 'INR 601,298' },
          { label: 'Expected return', value: '8.42%' },
        ],
        bullets: ['debt_liquid -> equity_mid_cap: 20.0%', 'hybrid_aggressive -> equity_mid_cap: 9.0%'],
      },
    }),
  },
  {
    delay: 400,
    build: () => ({
      type: 'status',
      id: randomUUID(),
      state: 'thinking',
      label: 'Statute pricing the switch',
    }),
  },
  {
    delay: 300,
    build: () => ({
      type: 'log',
      id: randomUUID(),
      at: clockLabel(),
      source: 'System',
      message: 'Stage 2/3:',
      highlight: 'Statute',
    }),
  },
  {
    delay: 400,
    build: () => ({
      type: 'tool_call',
      id: 'tool-112a',
      at: clockLabel(),
      name: 'ltcg_112a',
      args: 'disposals=[equity legs]',
      status: 'running',
    }),
  },
  {
    delay: 800,
    build: () => ({
      type: 'tool_result',
      id: randomUUID(),
      ref: 'tool-112a',
      status: 'ok',
      summary: 'Section 112A tax INR 0 before surcharge (inside exemption)',
    }),
  },
  {
    delay: 400,
    build: () => ({
      type: 'tool_call',
      id: 'tool-slab',
      at: clockLabel(),
      name: 'debt_slab',
      args: 'other_income=1200000',
      status: 'running',
    }),
  },
  {
    delay: 800,
    build: () => ({
      type: 'tool_result',
      id: randomUUID(),
      ref: 'tool-slab',
      status: 'ok',
      summary: 'Debt legs at slab: INR 18,720 before surcharge',
    }),
  },
  {
    delay: 500,
    build: () => ({
      type: 'message',
      id: randomUUID(),
      at: clockLabel(),
      source: 'Statute',
      text: 'The switch costs about INR 19,500 including surcharge and cess; staging across FYs saves little here.',
      report: {
        agent: 'Statute',
        title: 'Switch tax cost',
        headline:
          'The switch costs about INR 19,500 including surcharge and cess; staging across FYs saves little here.',
        verdict: 'price',
        metrics: [
          { label: 'Total tax', value: 'INR 19,469' },
          { label: 'Debt / slab', value: 'INR 18,720' },
          { label: 'Staging saves', value: 'INR 0' },
        ],
        bullets: ['Sections: 50AA/slab', '112A legs sit inside the annual exemption'],
      },
    }),
  },
  {
    delay: 400,
    build: () => ({
      type: 'status',
      id: randomUUID(),
      state: 'thinking',
      label: 'Channel measuring TER drag',
    }),
  },
  {
    delay: 300,
    build: () => ({
      type: 'log',
      id: randomUUID(),
      at: clockLabel(),
      source: 'System',
      message: 'Stage 3/3:',
      highlight: 'Channel',
    }),
  },
  {
    delay: 400,
    build: () => ({
      type: 'tool_call',
      id: 'tool-ter',
      at: clockLabel(),
      name: 'ter_lookup',
      args: 'categories=allocation',
      status: 'running',
    }),
  },
  {
    delay: 700,
    build: () => ({
      type: 'tool_result',
      id: randomUUID(),
      ref: 'tool-ter',
      status: 'ok',
      summary: 'Largest gap: equity sleeves ~1.1 ppt Regular over Direct',
    }),
  },
  {
    delay: 400,
    build: () => ({
      type: 'tool_call',
      id: 'tool-drag',
      at: clockLabel(),
      name: 'drag_calc',
      args: 'portfolio_value=900000, plan=regular',
      status: 'running',
    }),
  },
  {
    delay: 800,
    build: () => ({
      type: 'tool_result',
      id: randomUUID(),
      ref: 'tool-drag',
      status: 'ok',
      summary: 'Annual Regular drag INR 7,740 on the MF sleeve',
    }),
  },
  {
    delay: 500,
    build: () => ({
      type: 'message',
      id: randomUUID(),
      at: clockLabel(),
      source: 'Channel',
      text: 'Staying on Regular plans costs about INR 7,740 a year on this book.',
      report: {
        agent: 'Channel',
        title: 'Regular vs Direct drag',
        headline: 'Staying on Regular plans costs about INR 7,740 a year on this book.',
        verdict: 'drag',
        metrics: [
          { label: 'Annual drag', value: 'INR 7,740' },
          { label: 'Drag / portfolio', value: '0.860%' },
          { label: 'Five-year floor', value: 'INR 38,700' },
        ],
        bullets: ['Largest gaps on equity_large_cap and hybrid_aggressive'],
      },
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
        summary: 'Pipeline complete - Feasibility: ok; Statute: ok; Channel: ok',
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
