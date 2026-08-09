import { Router } from 'express'
import { intelligenceReports } from '../data/intelligence.js'

export const intelligenceRouter = Router()

intelligenceRouter.get('/reports', (_req, res) => {
  res.json(intelligenceReports)
})
