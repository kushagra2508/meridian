import { Router } from 'express'
import { resolveAgentProvider } from '../agents/index.js'

const provider = resolveAgentProvider()

export const agentRouter = Router()

agentRouter.get('/provider', (_req, res) => {
  res.json({ provider: provider.name, agentName: provider.agentName })
})

/**
 * A run is created and streamed within a single request so that nothing has to
 * be remembered between requests. That keeps the endpoint correct when each
 * request may land on a different serverless instance, and it lets the client
 * halt a run simply by closing the stream.
 */
agentRouter.get('/stream', async (req, res) => {
  const requested = req.query.prompt
  const prompt =
    typeof requested === 'string' && requested.trim().length > 0
      ? requested.trim()
      : 'Review portfolio exposure and surface actionable alpha.'

  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',
  })
  res.write('retry: 5000\n\n')
  res.flushHeaders?.()

  const controller = new AbortController()
  const heartbeat = setInterval(() => res.write(': ping\n\n'), 15000)
  req.on('close', () => controller.abort())

  try {
    for await (const event of provider.startRun({ prompt, signal: controller.signal })) {
      res.write(`event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`)
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'unknown_error'
    res.write(`event: error\ndata: ${JSON.stringify({ message })}\n\n`)
  } finally {
    clearInterval(heartbeat)
    res.end()
  }
})
