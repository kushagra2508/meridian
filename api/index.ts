import { app } from '../server/src/app.js'

// Vercel invokes the default export as the request handler; an Express app is
// already `(req, res) => void`, so it can be handed over directly.
export default app
