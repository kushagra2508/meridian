import { MockAgentProvider } from './mockProvider.js'
import type { AgentProvider } from './provider.js'

const providers: Record<string, () => AgentProvider> = {
  mock: () => new MockAgentProvider(),
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
