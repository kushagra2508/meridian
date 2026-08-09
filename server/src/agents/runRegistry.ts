import { randomUUID } from 'node:crypto'
import type { AgentEvent } from '../types.js'
import type { AgentProvider } from './provider.js'

export interface AgentRun {
  id: string
  prompt: string
  createdAt: string
  controller: AbortController
  stream: AsyncIterable<AgentEvent>
  consumed: boolean
}

const RUN_TTL_MS = 10 * 60 * 1000

const runs = new Map<string, AgentRun>()

export function createRun(provider: AgentProvider, prompt: string): AgentRun {
  const controller = new AbortController()
  const run: AgentRun = {
    id: randomUUID(),
    prompt,
    createdAt: new Date().toISOString(),
    controller,
    stream: provider.startRun({ prompt, signal: controller.signal }),
    consumed: false,
  }

  runs.set(run.id, run)
  setTimeout(() => runs.delete(run.id), RUN_TTL_MS).unref?.()

  return run
}

export function getRun(id: string): AgentRun | undefined {
  return runs.get(id)
}

export function stopRun(id: string): boolean {
  const run = runs.get(id)
  if (!run) return false
  run.controller.abort()
  return true
}

export function dropRun(id: string): void {
  runs.delete(id)
}
