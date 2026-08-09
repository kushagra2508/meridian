import type { IntelligenceReports } from '../types.js'

export const intelligenceReports: IntelligenceReports = {
  alpha: {
    id: 'AR-9942',
    tag: 'Alpha Generation',
    title: 'Q3 Tech Sector Divergence',
    paragraphs: [
      'Proprietary NLP models analyzing recent earnings calls indicate a significant structural divergence in capital expenditure among mega-cap technology firms, specifically regarding AI infrastructure.',
      'Firms heavily investing in custom silicon (e.g., AAPL, GOOGL) are exhibiting a 14% higher projected margin resilience over a 24-month horizon compared to peers relying solely on general-purpose compute.',
    ],
  },
  riskParity: {
    title: 'Risk Parity Shift',
    status: 'Live',
    bars: [
      { label: 'Equities', value: 60, tone: 'primary' },
      { label: 'Alternatives', value: 40, tone: 'primary' },
      { label: 'Fixed Income', value: 80, tone: 'secondary' },
      { label: 'Cash Drag', value: 30, tone: 'error' },
    ],
    footnotes: [
      { label: 'Equities: -4.2%', tone: 'neutral' },
      { label: 'Fixed Inc: +6.1%', tone: 'positive' },
    ],
  },
  sentiment: {
    title: 'Global Sentiment',
    regions: [
      { code: 'NA', score: 1.2 },
      { code: 'EU', score: -0.8 },
      { code: 'APAC', score: 3.1 },
      { code: 'LATAM', score: 0 },
      { code: 'MEA', score: 0.4 },
      { code: 'UK', score: -1.5 },
    ],
    summary: 'Heavy APAC accumulation detected in semi-conductors.',
  },
}
