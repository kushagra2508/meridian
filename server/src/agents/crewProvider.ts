import { spawn } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { createInterface } from 'node:readline'
import { fileURLToPath } from 'node:url'
import type { AgentEvent } from '../types.js'
import type { AgentProvider, AgentRunInput } from './provider.js'

const AGENT_NAME = 'Meridian desk'

const here = path.dirname(fileURLToPath(import.meta.url))
// src/agents at dev time, dist/agents after a build; the package sits beside both.
const CREW_DIR = process.env.CREW_DIR ?? path.resolve(here, '../../../crew')
const CREW_PYTHON = process.env.CREW_PYTHON ?? path.join(CREW_DIR, '.venv/bin/python')

/**
 * The default brief. The console sends a sentence, not a funding plan, so a run
 * with no parameters demonstrates the agent against a known case rather than
 * inventing numbers from prose.
 */
const DEFAULT_BRIEF: Record<string, string> = {
  goal: "Daughter's undergraduate tuition",
  'target-amount': '5000000',
  years: '7',
  'current-corpus': '900000',
  'monthly-contribution': '25000',
  'client-age': '42',
  allocation:
    'equity_large_cap=30,hybrid_aggressive=20,debt_short_duration=30,debt_liquid=20',
}

/** Only these may come off the query string, and each is passed as one argv pair. */
const ALLOWED_PARAMS = new Set([
  'goal',
  'target-amount',
  'years',
  'current-corpus',
  'monthly-contribution',
  'client-age',
  'currency',
  'step-up',
  'max-equity-pct',
  'allocation',
  'model',
])

/** What the Python process writes, one per line. */
interface StreamEvent {
  type: string
  state?: 'thinking' | 'idle' | 'halted'
  label?: string
  source?: string
  message?: string
  highlight?: string
  ref?: string
  name?: string
  args?: string
  status?: 'ok' | 'error'
  summary?: string
  text?: string
  report?: {
    agent: string
    title: string
    headline: string
    verdict?: string
    metrics?: { label: string; value: string }[]
    bullets?: string[]
  }
}

function clockLabel(date = new Date()): string {
  return date.toTimeString().slice(0, 8)
}

function buildArgs(params: Record<string, string>): string[] {
  const merged = { ...DEFAULT_BRIEF, ...params }
  const args = ['-m', 'meridian_crew', '--stream']

  for (const [key, value] of Object.entries(merged)) {
    if (!ALLOWED_PARAMS.has(key) || value.trim().length === 0) continue
    args.push(`--${key}`, value)
  }

  return args
}

/**
 * Maps one Python event onto the `AgentEvent` the client already renders. Ids and
 * timestamps are minted here rather than in Python, so they describe when the
 * event reached the stream.
 */
function toAgentEvent(event: StreamEvent): AgentEvent | null {
  const id = randomUUID()

  switch (event.type) {
    case 'status':
      return {
        type: 'status',
        id,
        state: event.state ?? 'thinking',
        label: event.label ?? '',
      }
    case 'log':
      return {
        type: 'log',
        id,
        at: clockLabel(),
        source: event.source ?? AGENT_NAME,
        message: event.message ?? '',
        ...(event.highlight ? { highlight: event.highlight } : {}),
      }
    case 'tool_call':
      return {
        type: 'tool_call',
        // The client keys results to the call by id, so the Python ref becomes the id.
        id: event.ref ?? id,
        at: clockLabel(),
        name: event.name ?? 'tool',
        args: event.args ?? '',
        status: 'running',
      }
    case 'tool_result':
      return {
        type: 'tool_result',
        id,
        ref: event.ref ?? '',
        status: event.status ?? 'ok',
        summary: event.summary ?? '',
      }
    case 'message':
      return {
        type: 'message',
        id,
        at: clockLabel(),
        source: event.source ?? AGENT_NAME,
        text: event.text ?? '',
        ...(event.report ? { report: event.report } : {}),
      }
    case 'done':
      return { type: 'done', id, at: clockLabel(), summary: event.summary ?? '' }
    case 'error':
      // Surfaced as a log so the console shows it in place instead of ending the run.
      return {
        type: 'log',
        id,
        at: clockLabel(),
        source: AGENT_NAME,
        message: event.message ?? 'unknown error',
        highlight: 'error',
      }
    default:
      return null
  }
}

/**
 * Runs the CrewAI Feasibility agent as a child process and translates its NDJSON
 * output into the SSE event stream.
 *
 * This provider needs a local Python environment, so it cannot run on a Node
 * serverless deployment. `resolveAgentProvider` keeps `mock` as the default for
 * exactly that reason; select this one with AGENT_PROVIDER=crew when running the
 * server on a machine where `crew/` is installed.
 */
export class CrewAgentProvider implements AgentProvider {
  readonly name = 'crew'
  readonly agentName = AGENT_NAME

  async *startRun({ prompt, signal, params = {} }: AgentRunInput): AsyncIterable<AgentEvent> {
    if (!existsSync(CREW_PYTHON)) {
      throw new Error(
        `CrewAI provider needs a Python environment at ${CREW_PYTHON}. ` +
          'Run `uv venv --python 3.12 && uv pip install -e ".[dev]"` in crew/, ' +
          'or set CREW_PYTHON.',
      )
    }

    const args = buildArgs(params)
    // The operator's sentence is context, not a brief field, so it rides as a note.
    args.push('--notes', prompt)

    const child = spawn(CREW_PYTHON, args, {
      cwd: CREW_DIR,
      stdio: ['ignore', 'pipe', 'pipe'],
    })

    const stderr: string[] = []
    child.stderr.on('data', (chunk: Buffer) => {
      stderr.push(chunk.toString())
    })

    const onAbort = () => child.kill('SIGTERM')
    signal.addEventListener('abort', onAbort, { once: true })

    const exited = new Promise<number>((resolve) => {
      child.once('close', (code) => resolve(code ?? 0))
    })

    try {
      for await (const line of createInterface({ input: child.stdout })) {
        const trimmed = line.trim()
        if (trimmed.length === 0) continue

        let parsed: StreamEvent
        try {
          parsed = JSON.parse(trimmed) as StreamEvent
        } catch {
          // Anything the agent prints outside the protocol is still worth seeing.
          yield {
            type: 'log',
            id: randomUUID(),
            at: clockLabel(),
            source: 'python',
            message: trimmed,
          }
          continue
        }

        const event = toAgentEvent(parsed)
        if (event) yield event
      }

      const code = await exited

      if (signal.aborted) {
        yield {
          type: 'status',
          id: randomUUID(),
          state: 'halted',
          label: 'Halted by operator',
        }
        return
      }

      if (code !== 0) {
        const detail = stderr.join('').trim().split('\n').slice(-3).join(' ')
        yield {
          type: 'log',
          id: randomUUID(),
          at: clockLabel(),
          source: 'python',
          message: `Agent exited with code ${code}${detail ? `: ${detail}` : ''}`,
          highlight: 'error',
        }
      }
    } finally {
      signal.removeEventListener('abort', onAbort)
      if (child.exitCode === null) child.kill('SIGKILL')
    }
  }
}
