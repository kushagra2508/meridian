import cors from 'cors'
import express from 'express'
import { agentRouter } from './routes/agent.js'
import { intelligenceRouter } from './routes/intelligence.js'
import { personaRouter } from './routes/personas.js'
import { portfolioRouter } from './routes/portfolio.js'
import { statuteRouter } from './routes/statute.js'

export function createApp() {
  const app = express()

  app.use(cors())
  app.use(express.json())

  app.get('/api/health', (_req, res) => {
    res.json({ status: 'ok', uptime: process.uptime() })
  })

  app.use('/api/personas', personaRouter)
  app.use('/api/portfolio', portfolioRouter)
  app.use('/api/intelligence', intelligenceRouter)
  app.use('/api/agent', agentRouter)
  app.use('/api/statute', statuteRouter)

  app.use('/api', (_req, res) => {
    res.status(404).json({ error: 'not_found' })
  })

  return app
}

export const app = createApp()
