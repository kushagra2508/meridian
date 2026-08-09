import { CrewAgentProvider } from './crewProvider.js'
import { MockAgentProvider } from './mockProvider.js'
import type { AgentProvider } from './provider.js'

/**
 * `mock` stays the default because it is the only provider that runs anywhere.
 * `crew` shells out to a local Python environment, which a Node serverless
 * deployment does not have, so it is opt-in via AGENT_PROVIDER=crew.
 */
const providers: Record<string, () => AgentProvider> = {
  mock: () => new MockAgentProvider(),
  crew: () => new CrewAgentProvider(),
}

export function resolveAgentProvider(
  name = process.env.AGENT_PROVIDER ?? 'mock',
): AgentProvider {
  const factory = providers[name]

  if (!factory) {
    const known = Object.keys(providers).join(', ')
    throw new Error(`Unknown AGENT_PROVIDER "${name}". Available providers: ${known}`)
  }

  return factory()
}

export type { AgentProvider, AgentRunInput } from './provider.js'
