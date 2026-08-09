import { useEffect, useRef, useState } from 'react'
import type { AgentReportCard } from './useAgentRun'

/**
 * Reveals desk verdict cards one at a time, gated by agent stage completion.
 *
 * Desk/committee numbers may already be cached, but a card stays hidden until
 * the matching agent reports in the live stream. Local stagger is intentionally
 * omitted — that flashed later stages ahead of the console.
 */
export function useSequentialVerdicts(
  deskReports: AgentReportCard[],
  streamReports: AgentReportCard[],
) {
  const [visible, setVisible] = useState<AgentReportCard[]>([])
  const revealed = useRef<Set<string>>(new Set())
  const deskKey = deskReports.map((r) => r.id).join('|')

  useEffect(() => {
    revealed.current = new Set()
    setVisible([])
  }, [deskKey])

  // Unlock each desk card only when its agent stage has reported.
  // Clearing the stream (new run) hides cards again until stages complete.
  useEffect(() => {
    if (streamReports.length === 0) {
      revealed.current = new Set()
      setVisible([])
      return
    }
    setVisible((prev) => {
      let next = prev
      for (const stream of streamReports) {
        const desk = deskReports.find((d) => d.agent === stream.agent)
        if (!desk || revealed.current.has(desk.id)) continue
        revealed.current.add(desk.id)
        next = next.some((p) => p.id === desk.id) ? next : [...next, desk]
      }
      return next
    })
  }, [streamReports, deskReports])

  const pendingAgent =
    visible.length < deskReports.length ? deskReports[visible.length]?.agent : null

  return {
    visibleReports: visible,
    expectedCount: deskReports.length,
    pendingAgent,
    isComplete: deskReports.length > 0 && visible.length >= deskReports.length,
  }
}
