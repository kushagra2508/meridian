import { useEffect, useRef, useState } from 'react'
import type { AgentReportCard } from './useAgentRun'

const AGENT_TIMEOUT_MS = 5000

/**
 * Reveals desk verdict cards one at a time.
 *
 * Prefer a matching live stream report. If the pending agent has not reported
 * within AGENT_TIMEOUT_MS, unlock the pre-computed desk card (numbers never
 * came from the network) and mark it cached so the demo keeps moving.
 */
export function useSequentialVerdicts(
  deskReports: AgentReportCard[],
  streamReports: AgentReportCard[],
  options?: { timeoutMs?: number; forceCached?: boolean },
) {
  const timeoutMs = options?.timeoutMs ?? AGENT_TIMEOUT_MS
  const forceCached = options?.forceCached ?? false
  const [visible, setVisible] = useState<AgentReportCard[]>([])
  const [usedCache, setUsedCache] = useState(false)
  const revealed = useRef<Set<string>>(new Set())
  const deskKey = deskReports.map((r) => r.id).join('|')

  useEffect(() => {
    revealed.current = new Set()
    setVisible([])
    setUsedCache(false)
  }, [deskKey])

  // Unlock from the live stream when an agent reports.
  useEffect(() => {
    if (streamReports.length === 0) return
    setVisible((prev) => {
      let next = prev
      for (const stream of streamReports) {
        const desk = deskReports.find((d) => d.agent === stream.agent)
        if (!desk || revealed.current.has(desk.id)) continue
        revealed.current.add(desk.id)
        next = next.some((p) => p.id === desk.id)
          ? next
          : [...next, { ...desk, source: 'live' as const }]
      }
      return next
    })
  }, [streamReports, deskReports])

  // Per-agent 5s timeout — advance with cached desk numbers.
  useEffect(() => {
    if (deskReports.length === 0) return
    if (visible.length >= deskReports.length) return

    const pending = deskReports[visible.length]
    if (!pending || revealed.current.has(pending.id)) return

    const timer = window.setTimeout(() => {
      if (revealed.current.has(pending.id)) return
      revealed.current.add(pending.id)
      setUsedCache(true)
      setVisible((prev) =>
        prev.some((p) => p.id === pending.id)
          ? prev
          : [...prev, { ...pending, source: 'cached' as const }],
      )
    }, timeoutMs)

    return () => window.clearTimeout(timer)
  }, [deskReports, visible.length, timeoutMs])

  // Stream hard-failed: flush the rest from cache immediately.
  useEffect(() => {
    if (!forceCached || deskReports.length === 0) return
    setUsedCache(true)
    setVisible(() => {
      const next: AgentReportCard[] = []
      for (const desk of deskReports) {
        if (!revealed.current.has(desk.id)) revealed.current.add(desk.id)
        next.push({ ...desk, source: 'cached' })
      }
      return next
    })
  }, [forceCached, deskReports])

  const pendingAgent =
    visible.length < deskReports.length ? deskReports[visible.length]?.agent : null

  return {
    visibleReports: visible,
    expectedCount: deskReports.length,
    pendingAgent,
    usedCache,
    isComplete: deskReports.length > 0 && visible.length >= deskReports.length,
  }
}
