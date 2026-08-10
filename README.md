# Lumina Wealth

AI-first wealth management platform. React (Vite + TypeScript) front end, Express (TypeScript) API,
managed as a single npm workspaces repo.

## Requirements

- Node.js >= 20 (developed on v24)
- npm >= 10

## Getting started

```bash
npm install
npm run dev
```

- Client: http://localhost:5173
- API: http://localhost:4000 (the Vite dev server proxies `/api` to it)

## Scripts

| Command             | Description                                        |
| ------------------- | -------------------------------------------------- |
| `npm run dev`       | Runs the API and the Vite dev server together       |
| `npm run dev:client`| Vite dev server only                                |
| `npm run dev:server`| API only, with watch mode                           |
| `npm run build`     | Type-checks and builds both workspaces              |
| `npm run start`     | Runs the compiled API from `server/dist`            |
| `npm run lint`      | Lints the client                                    |

## Layout

```
client/                 Vite + React + TypeScript SPA
  tailwind.config.js    Design tokens (colors, spacing, type scale)
  src/routes/           Home, Dashboard, Intelligence
  src/components/       AppShell, SideNav, TopAppBar, panels, cards
  src/lib/              API and SSE helpers, shared types
server/
  src/routes/           portfolio, intelligence, agent
  src/data/             dummy fixtures
  src/agents/           AgentProvider interface + mock and CrewAI implementations
crew/                   CrewAI Planner agent (Python), see crew/README.md
```

## Routes

- `/` marketing home
- `/dashboard` portfolio overview
- `/intelligence` AI intelligence hub with the live agent console

## API

| Method | Path                              | Description                                     |
| ------ | --------------------------------- | ----------------------------------------------- |
| GET    | `/api/health`                     | Liveness probe                                   |
| GET    | `/api/portfolio/summary`          | Balance, YTD delta, health score, allocations    |
| GET    | `/api/portfolio/series?range=1M`  | Time series for `1D`, `1W`, `1M`, `1Y`           |
| GET    | `/api/intelligence/reports`       | Alpha report, risk parity, regional sentiment    |
| GET    | `/api/agent/provider`             | Active provider and agent name                   |
| GET    | `/api/agent/stream?prompt=...`    | Runs an agent and streams events over SSE        |

A run starts and streams inside one request, so nothing is held between
requests and the endpoint stays correct when each request lands on a different
serverless instance. Closing the stream halts the run.

## Agent engine

Agent output comes from an `AgentProvider`, a single interface in
`server/src/agents/provider.ts` chosen by the `AGENT_PROVIDER` environment variable. Both
implementations emit the same event union, so the client renders either without knowing which
is running.

| `AGENT_PROVIDER` | Behaviour                                                                      |
| ---------------- | ------------------------------------------------------------------------------ |
| `mock` (default) | Replays a scripted multi-agent run. No dependencies, runs anywhere.            |
| `crew`           | Runs the real CrewAI Planner agent in `crew/` and streams its actual work.  |

`crew` spawns `python -m meridian_crew --stream` and translates its newline-delimited JSON
into SSE events, which is why it needs a local Python environment (see `crew/README.md`) and
why `mock` remains the default: the Vercel deployment is Node-only and cannot run Python, so
the hosted demo streams the mock while `crew` is selected when running locally.

The `/api/agent/stream` endpoint accepts optional brief fields alongside `prompt` —
`target-amount`, `years`, `current-corpus`, `monthly-contribution`, `client-age`,
`allocation`, `max-equity-pct`, `step-up`, `currency`, `goal`. The `crew` provider falls back
to a worked tuition example when they are absent, because a real agent needs numbers and
guessing them out of a sentence would be worse than defaulting.

```bash
# Stream the real agent locally
cd crew && uv venv --python 3.12 && uv pip install -e ".[dev]" && cp .env.example .env
cd ../server && AGENT_PROVIDER=crew npm run dev
```

## Environment

`server/.env` (optional):

```
PORT=4000
AGENT_PROVIDER=mock
# Only read by the crew provider; both default to crew/ beside the server.
CREW_DIR=../crew
CREW_PYTHON=../crew/.venv/bin/python
```
