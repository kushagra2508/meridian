import type { PortfolioSeries, PortfolioSummary, SeriesPoint, SeriesRange } from '../types.js'

export const portfolioSummary: PortfolioSummary = {
  totalBalance: 1248593.2,
  currency: 'USD',
  ytdChangePct: 12.4,
  periodLabel: 'YTD',
  headline: 'Your portfolio is currently optimized for long-term growth.',
  subheadline:
    'AI analysis confirms risk exposure is low with recommendations for Tech Equities.',
  healthScore: 92,
  healthLabel: 'Portfolio health is optimal',
  healthAdvice:
    'Risk exposure is low. Recommended slight increase in Tech Equities to capture projected Q3 momentum.',
  allocations: [
    { label: 'Equities', weight: 46, changePct: -4.2 },
    { label: 'Fixed Income', weight: 24, changePct: 6.1 },
    { label: 'Alternatives', weight: 18, changePct: 2.3 },
    { label: 'Digital Assets', weight: 12, changePct: 3.4 },
  ],
  watchlist: [
    { ticker: 'AAPL', name: 'Apple Inc.', changePct: 1.2 },
    { ticker: 'BTC', name: 'Bitcoin', changePct: 3.4 },
    { ticker: 'GOOGL', name: 'Alphabet Inc.', changePct: 0.8 },
  ],
}

interface RangeShape {
  points: number
  stepMs: number
  drift: number
  volatility: number
  format: (date: Date) => string
}

const HOUR = 60 * 60 * 1000
const DAY = 24 * HOUR

const rangeShapes: Record<SeriesRange, RangeShape> = {
  '1D': {
    points: 24,
    stepMs: HOUR,
    drift: 0.0004,
    volatility: 0.0022,
    format: (d) => `${String(d.getHours()).padStart(2, '0')}:00`,
  },
  '1W': {
    points: 28,
    stepMs: 6 * HOUR,
    drift: 0.0011,
    volatility: 0.0045,
    format: (d) =>
      `${d.toLocaleDateString('en-US', { weekday: 'short' })} ${String(d.getHours()).padStart(2, '0')}:00`,
  },
  '1M': {
    points: 30,
    stepMs: DAY,
    drift: 0.0018,
    volatility: 0.0065,
    format: (d) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
  },
  '1Y': {
    points: 52,
    stepMs: 7 * DAY,
    drift: 0.0024,
    volatility: 0.011,
    format: (d) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
  },
}

// Deterministic pseudo-random source so the same range always renders the same
// curve across requests and reloads.
function seededNoise(seed: number): () => number {
  let state = seed >>> 0
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0
    return state / 0xffffffff - 0.5
  }
}

const rangeSeeds: Record<SeriesRange, number> = {
  '1D': 8831,
  '1W': 22147,
  '1M': 40913,
  '1Y': 71023,
}

export function buildSeries(range: SeriesRange, now = Date.now()): PortfolioSeries {
  const shape = rangeShapes[range]
  const noise = seededNoise(rangeSeeds[range])
  const end = portfolioSummary.totalBalance
  const steps = shape.points - 1

  // Walk backwards from today's balance so the series always lands on it.
  const reversed: number[] = [end]
  for (let i = 0; i < steps; i += 1) {
    const previous = reversed[reversed.length - 1]!
    const wobble = noise() * shape.volatility
    reversed.push(previous / (1 + shape.drift + wobble))
  }

  const values = reversed.reverse()
  const points: SeriesPoint[] = values.map((value, index) => {
    const date = new Date(now - (steps - index) * shape.stepMs)
    return {
      t: date.toISOString(),
      label: shape.format(date),
      value: Math.round(value * 100) / 100,
    }
  })

  const first = points[0]!.value
  const last = points[points.length - 1]!.value

  return {
    range,
    points,
    changePct: Math.round(((last - first) / first) * 1000) / 10,
    low: Math.min(...values),
    high: Math.max(...values),
  }
}
