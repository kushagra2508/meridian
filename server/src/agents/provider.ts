import type { AgentEvent } from '../types.js'

export interface AgentRunInput {
  prompt: string
  signal: AbortSignal
  /**
   * Structured brief fields, when the caller has them. The mock provider ignores
   * these; a real agent needs numbers rather than a sentence, and guessing them
   * out of the prompt would be worse than asking for them.
   */
  params?: Record<string, string>
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
