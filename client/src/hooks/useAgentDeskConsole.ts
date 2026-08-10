import { useEffect, useRef, useState } from 'react'
import type { AgentReportCard, AgentStatus, ConsoleItem } from './useAgentRun'

/** How long to wait for the first live SSE item before assuming the stream is dead. */
const STALL_GRACE_MS = 1500
/** Matches the per-agent cache timeout in useSequentialVerdicts so the console
 * commentary lands in step with each desk card as it reveals. */
const STAGE_MS = 5000

const TOOLS_BY_AGENT: Record<string, [string, string]> = {
  Planner: ['goal_solver', 'reallocation_search'],
  Tax: ['ltcg_112a', 'debt_slab'],
  Fees: ['ter_lookup', 'drag_calc'],
  Rethink: ['slip_year', 'shrink_target'],
  Verdict: ['eligibility_gate', 'ledger'],
}

const STANDBY: AgentStatus = { state: 'idle', label: 'Standing by' }

function clockLabel(date = new Date()): string {
  return date.toTimeString().slice(0, 8)
}

function metricAt(report: AgentReportCard, index: number) {
  return report.metrics?.[index] ?? report.metrics?.[0]
}

function argsFor(report: AgentReportCard): string {
  const metric = metricAt(report, 0)
  return metric ? `${metric.label}=${metric.value}` : 'inputs=observed position'
}

function summaryFor(report: AgentReportCard, index: number): string {
  const metric = metricAt(report, index)
  return metric ? `${metric.label}: ${metric.value}` : 'computed from observed position'
}

interface DeskConsoleOptions {
  /** Real, already-computed cards — same numbers the centre panel shows. */
  deskReports: AgentReportCard[]
  liveItems: ConsoleItem[]
  liveStatus: AgentStatus
  liveRunning: boolean
  liveError: string | null
  /** Changes whenever a fresh run should reset the console (e.g. new committee). */
  runKey: string
}

/**
 * Drives the "Meridian desk" console. Prefers the live agent stream, but if it
 * never starts producing events (serverless streaming hiccup, network block,
 * crew unavailable) or it errors out, replays a scripted desk session built
 * from the same real desk figures already shown in the centre panel — so the
 * console never sits empty and always agrees with what's on screen.
 */
export function useAgentDeskConsole({
  deskReports,
  liveItems,
  liveStatus,
  liveRunning,
  liveError,
  runKey,
}: DeskConsoleOptions) {
  const [simItems, setSimItems] = useState<ConsoleItem[]>([])
  const [simStatus, setSimStatus] = useState<AgentStatus>(STANDBY)
  const [simActive, setSimActive] = useState(false)
  const [simDone, setSimDone] = useState(false)
  const timers = useRef<number[]>([])
  const wasRunning = useRef(false)

  const clearTimers = () => {
    timers.current.forEach((id) => window.clearTimeout(id))
    timers.current = []
  }

  const resetSim = () => {
    clearTimers()
    setSimItems([])
    setSimStatus(STANDBY)
    setSimActive(false)
    setSimDone(false)
  }

  useEffect(() => {
    resetSim()
    return clearTimers
  }, [runKey])

  // A run can also be (re)started manually from the console input — that
  // doesn't change runKey, so catch the false -> true edge here too.
  useEffect(() => {
    if (liveRunning && !wasRunning.current) resetSim()
    wasRunning.current = liveRunning
  }, [liveRunning])

  useEffect(() => {
    if (liveError) {
      setSimActive(true)
      return
    }
    if (!liveRunning || liveItems.length > 0) return

    const id = window.setTimeout(() => {
      setSimActive(true)
    }, STALL_GRACE_MS)
    timers.current.push(id)
    return () => window.clearTimeout(id)
  }, [liveError, liveRunning, liveItems.length])

  useEffect(() => {
    if (!simActive || deskReports.length === 0 || simDone) return

    clearTimers()
    setSimItems([])

    deskReports.forEach((report, index) => {
      const base = index * STAGE_MS
      const [toolA, toolB] = TOOLS_BY_AGENT[report.agent] ?? ['portfolio_lookup', 'ledger']
      const ref = `sim-${report.id}`

      timers.current.push(
        window.setTimeout(() => {
          setSimStatus({ state: 'thinking', label: `${report.agent} deliberating` })
          setSimItems((cur) => [
            ...cur,
            {
              kind: 'log',
              id: `${ref}-log`,
              at: clockLabel(),
              source: 'System',
              message: `Stage ${index + 1}/${deskReports.length}:`,
              highlight: report.agent,
            },
            { kind: 'tool', id: `${ref}-a`, at: clockLabel(), name: toolA, args: argsFor(report), status: 'running' },
          ])
        }, base + 300),
      )

      timers.current.push(
        window.setTimeout(() => {
          setSimItems((cur) =>
            cur.map((item) =>
              item.kind === 'tool' && item.id === `${ref}-a`
                ? { ...item, status: 'ok' as const, summary: summaryFor(report, 0) }
                : item,
            ),
          )
        }, base + 1400),
      )

      timers.current.push(
        window.setTimeout(() => {
          setSimItems((cur) => [
            ...cur,
            { kind: 'tool', id: `${ref}-b`, at: clockLabel(), name: toolB, args: `ref=${report.id}`, status: 'running' },
          ])
        }, base + 1900),
      )

      timers.current.push(
        window.setTimeout(() => {
          setSimItems((cur) =>
            cur.map((item) =>
              item.kind === 'tool' && item.id === `${ref}-b`
                ? { ...item, status: 'ok' as const, summary: summaryFor(report, 1) }
                : item,
            ),
          )
        }, base + 3000),
      )

      timers.current.push(
        window.setTimeout(() => {
          setSimItems((cur) => [
            ...cur,
            {
              kind: 'message',
              id: `${ref}-msg`,
              at: clockLabel(),
              source: report.agent,
              text: `${report.title}: ${report.headline}`,
            },
          ])
        }, base + 3600),
      )

      if (index === deskReports.length - 1) {
        timers.current.push(
          window.setTimeout(() => {
            setSimStatus({ state: 'idle', label: 'Awaiting direction' })
            setSimItems((cur) => [
              ...cur,
              {
                kind: 'done',
                id: `${ref}-done`,
                at: clockLabel(),
                summary: 'Pipeline complete (offline replay) — reasoning cached',
              },
            ])
            setSimDone(true)
          }, base + STAGE_MS - 200),
        )
      }
    })

    return clearTimers
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [simActive, deskReports])

  const usingFallback = simActive
  return {
    items: usingFallback ? simItems : liveItems,
    status: usingFallback ? simStatus : liveStatus,
    running: usingFallback ? !simDone : liveRunning,
    error: usingFallback ? null : liveError,
    usingFallback,
  }
}
