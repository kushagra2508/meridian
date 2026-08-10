import type { AgentReportCard } from '../../hooks/useAgentRun'

const agentTone: Record<string, string> = {
  Planner: 'border-primary/40 bg-primary/5',
  Tax: 'border-secondary/40 bg-secondary/5',
  Fees: 'border-tertiary/40 bg-tertiary/5',
  Rethink: 'border-primary/30 bg-surface-container-low',
  Verdict: 'border-outline-variant bg-surface-container-high/40',
}

interface AgentReportsProps {
  reports: AgentReportCard[]
  running: boolean
  statusLabel: string
  expectedCount?: number
  pendingAgent?: string | null
}

export function AgentReports({
  reports,
  running,
  statusLabel,
  expectedCount = 0,
  pendingAgent = null,
}: AgentReportsProps) {
  const awaiting = running && expectedCount > 0 && reports.length < expectedCount

  if (reports.length === 0 && !awaiting) {
    return (
      <div className="glass-panel-light flex min-h-40 flex-col items-start justify-center rounded-xl p-gutter">
        <p className="font-section-kicker text-[11px] uppercase tracking-wider text-on-surface-variant">
          Agent desk output
        </p>
        <h3 className="mt-2 font-panel-header text-panel-header text-on-background">
          {running ? statusLabel : 'Waiting for the desk'}
        </h3>
        <p className="mt-2 max-w-xl font-body text-body text-on-surface-variant">
          Planner through Verdict write their verdicts here as each stage
          finishes. Tool calls stay in the console on the right.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-gutter">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="font-section-kicker text-[11px] uppercase tracking-wider text-on-surface-variant">
            Agent desk output
          </p>
          <h3 className="mt-1 font-panel-header text-panel-header text-on-background">
            Sequential verdicts
          </h3>
        </div>
        <span className="font-footnote text-footnote text-on-surface-variant">
          {running
            ? statusLabel
            : `${reports.length}${expectedCount ? ` / ${expectedCount}` : ''} stage${reports.length === 1 ? '' : 's'}`}
        </span>
      </div>

      <div className="flex flex-col gap-gutter">
        {reports.map((report) => (
          <article
            key={report.id}
            className={`animate-fade-in-up rounded-xl border p-gutter ${
              agentTone[report.agent] ?? 'border-outline-variant bg-surface-container-low'
            }`}
          >
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="rounded-full border border-outline-variant bg-surface px-3 py-1 font-section-kicker text-[11px] uppercase tracking-wider text-on-surface">
                  {report.agent}
                </span>
                <span className="font-footnote text-footnote text-on-surface-variant">
                  {report.title}
                </span>
                {report.source === 'cached' ? (
                  <span className="rounded bg-surface-container-high px-2 py-0.5 font-label-caps text-[10px] uppercase tracking-wider text-on-surface-variant">
                    Cached · &lt;5s
                  </span>
                ) : null}
              </div>
              <span className="font-footnote text-footnote text-on-surface-variant">{report.at}</span>
            </div>

            <h4 className="font-body text-body font-bold text-on-background">{report.headline}</h4>

            {report.metrics && report.metrics.length > 0 ? (
              <dl className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
                {report.metrics.map((metric) => (
                  <div key={`${report.id}-${metric.label}`}>
                    <dt className="font-footnote text-footnote uppercase tracking-wider text-on-surface-variant">
                      {metric.label}
                    </dt>
                    <dd className="mt-1 font-body text-body text-on-background">{metric.value}</dd>
                  </div>
                ))}
              </dl>
            ) : null}

            {report.bullets && report.bullets.length > 0 ? (
              <ul className="mt-4 space-y-1 font-body text-body text-on-surface-variant">
                {report.bullets.map((bullet) => (
                  <li key={bullet}>— {bullet}</li>
                ))}
              </ul>
            ) : null}
          </article>
        ))}

        {awaiting ? (
          <div className="animate-pulse rounded-xl border border-dashed border-outline-variant bg-surface-container-low/60 p-gutter">
            <p className="font-section-kicker text-[11px] uppercase tracking-wider text-on-surface-variant">
              {pendingAgent ? `${pendingAgent} deliberating` : 'Next stage'}
            </p>
            <p className="mt-2 font-body text-body text-on-surface-variant">{statusLabel}</p>
          </div>
        ) : null}
      </div>
    </div>
  )
}
