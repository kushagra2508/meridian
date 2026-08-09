import type { AgentEvent } from '../types.js'

export interface AgentRunInput {
  prompt: string
  signal: AbortSignal
}

/**
 * A single seam between the API and whatever produces agent output. The mock
 * implementation replays a scripted run today; a CrewAI-backed provider can be
 * added without any change to the routes or the client.
 */
export interface AgentProvider {
  readonly name: string
  readonly agentName: string
  startRun(input: AgentRunInput): AsyncIterable<AgentEvent>
}
