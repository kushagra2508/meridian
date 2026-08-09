export type SeriesRange = '1D' | '1W' | '1M' | '1Y'

export const SERIES_RANGES: SeriesRange[] = ['1D', '1W', '1M', '1Y']

export function isSeriesRange(value: unknown): value is SeriesRange {
  return typeof value === 'string' && (SERIES_RANGES as string[]).includes(value)
}

export interface Allocation {
  label: string
  weight: number
  changePct: number
}

export interface Holding {
  ticker: string
  name: string
  changePct: number
}

export interface PortfolioSummary {
  totalBalance: number
  currency: string
  ytdChangePct: number
  periodLabel: string
  headline: string
  subheadline: string
  healthScore: number
  healthLabel: string
  healthAdvice: string
  allocations: Allocation[]
  watchlist: Holding[]
}

export interface SeriesPoint {
  t: string
  label: string
  value: number
}

export interface PortfolioSeries {
  range: SeriesRange
  points: SeriesPoint[]
  changePct: number
  low: number
  high: number
}

export interface AlphaReport {
  id: string
  tag: string
  title: string
  paragraphs: string[]
}

export interface RiskParity {
  title: string
  status: string
  bars: { label: string; value: number; tone: 'primary' | 'secondary' | 'error' }[]
  footnotes: { label: string; tone: 'neutral' | 'positive' | 'negative' }[]
}

export interface SentimentRegion {
  code: string
  score: number
}

export interface Sentiment {
  title: string
  regions: SentimentRegion[]
  summary: string
}

export interface IntelligenceReports {
  alpha: AlphaReport
  riskParity: RiskParity
  sentiment: Sentiment
}

export type AgentEvent =
  | { type: 'log'; id: string; at: string; source: string; message: string; highlight?: string }
  | { type: 'tool_call'; id: string; at: string; name: string; args: string; status: 'running' }
  | { type: 'tool_progress'; id: string; ref: string; label: string; percent: number }
  | {
      type: 'tool_result'
      id: string
      ref: string
      status: 'ok' | 'error'
      summary: string
    }
  | { type: 'message'; id: string; at: string; source: string; text: string }
  | { type: 'status'; id: string; state: 'thinking' | 'idle' | 'halted'; label: string }
  | { type: 'done'; id: string; at: string; summary: string }
