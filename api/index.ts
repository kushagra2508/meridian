// Imports the compiled server output rather than its TypeScript source: Vercel
// transpiles this entrypoint without bundling, so the target must be a real
// file on disk at runtime. `npm run build` emits it before functions are built.
import { app } from '../server/dist/app.js'

// Vercel invokes the default export as the request handler; an Express app is
// already `(req, res) => void`, so it can be handed over directly.
export default app
