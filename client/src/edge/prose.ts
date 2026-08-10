import cached from './data/cachedProse.json'
import type { AgentId, AgentPosition, AgentProse, ProseSource, Stance } from './types'

type CacheKey = `${AgentId}:${Stance}`

function cacheKey(agent: AgentId, stance: Stance): CacheKey {
  return `${agent}:${stance}`
}

export function loadCachedProse(positions: AgentPosition[]): AgentProse[] {
  return positions.map((p) => {
    const key = cacheKey(p.agent, p.stance)
    const entry = (cached as Record<string, { claim: string; opening: string | null }>)[key]
    const fallback = (cached as Record<string, { claim: string; opening: string | null }>)[
      cacheKey(p.agent, 'PROPOSES')
    ]
    const hit = entry ?? fallback
    return {
      agent: p.agent,
      claim: hit?.claim ?? `${p.agent} holds stance ${p.stance}.`,
      opening: hit?.opening ?? null,
    }
  })
}

function offlineFlag(): boolean {
  return import.meta.env.VITE_OFFLINE === '1'
}

/** Best-effort prose; always falls back to cache. Numbers never come from here. */
export async function requestProse(
  positions: AgentPosition[],
): Promise<{ prose: AgentProse[]; source: ProseSource }> {
  if (offlineFlag()) {
    return { prose: loadCachedProse(positions), source: 'cached' }
  }

  try {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 6000)
    const res = await fetch('/api/edge/prose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        positions: positions.map((p) => ({
          agent: p.agent,
          stance: p.stance,
          figures: p.figures,
          referencesAgent: p.referencesAgent,
          scopeLimits: p.scopeLimits,
        })),
      }),
      signal: controller.signal,
    })
    window.clearTimeout(timeout)
    if (!res.ok) throw new Error(`prose ${res.status}`)
    const data = (await res.json()) as { prose?: AgentProse[] }
    if (!Array.isArray(data.prose) || data.prose.length === 0) {
      throw new Error('empty prose')
    }
    const agents = new Set(positions.map((p) => p.agent))
    const valid = data.prose.every((p) => agents.has(p.agent))
    if (!valid) throw new Error('unknown agent')
    return { prose: data.prose, source: 'live' }
  } catch {
    return { prose: loadCachedProse(positions), source: 'cached' }
  }
}
