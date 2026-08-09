import { Router } from 'express'
import { buildSeries, portfolioSummary } from '../data/portfolio.js'
import { SERIES_RANGES, isSeriesRange } from '../types.js'

export const portfolioRouter = Router()

portfolioRouter.get('/summary', (_req, res) => {
  res.json(portfolioSummary)
})

portfolioRouter.get('/series', (req, res) => {
  const range = req.query.range ?? '1M'

  if (!isSeriesRange(range)) {
    res.status(400).json({
      error: 'invalid_range',
      message: `range must be one of ${SERIES_RANGES.join(', ')}`,
    })
    return
  }

  res.json(buildSeries(range))
})
