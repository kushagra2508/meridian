import { Router } from 'express'
import { resolveAgentProvider } from '../agents/index.js'
import { createRun, dropRun, getRun, stopRun } from '../agents/runRegistry.js'

const provider = resolveAgentProvider()

export const agentRouter = Router()

agentRouter.get('/provider', (_req, res) => {
  res.json({ provider: provider.name, agentName: provider.agentName })
})

agentRouter.post('/runs', (req, res) => {
  const prompt =
    typeof req.body?.prompt === 'string' && req.body.prompt.trim().length > 0
      ? req.body.prompt.trim()
      : 'Review portfolio exposure and surface actionable alpha.'

  const run = createRun(provider, prompt)
  res.status(201).json({ runId: run.id, prompt: run.prompt, agentName: provider.agentName })
})

agentRouter.post('/runs/:runId/stop', (req, res) => {
  const stopped = stopRun(req.params.runId)
  if (!stopped) {
    res.status(404).json({ error: 'run_not_found' })
    return
  }
  res.json({ ok: true })
})

agentRouter.get('/runs/:runId/stream', async (req, res) => {
  const run = getRun(req.params.runId)

  if (!run) {
    res.status(404).json({ error: 'run_not_found' })
    return
  }

  if (run.consumed) {
    res.status(409).json({ error: 'run_already_streamed' })
    return
  }

  run.consumed = true

  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',
  })
  res.write(`retry: 5000\n\n`)
  res.flushHeaders?.()

  const heartbeat = setInterval(() => res.write(': ping\n\n'), 15000)
  req.on('close', () => run.controller.abort())

  try {
    for await (const event of run.stream) {
      res.write(`event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`)
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'unknown_error'
    res.write(`event: error\ndata: ${JSON.stringify({ message })}\n\n`)
  } finally {
    clearInterval(heartbeat)
    dropRun(run.id)
    res.end()
  }
})
