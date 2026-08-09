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
  src/agents/           AgentProvider interface + mock implementation
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

All agent output currently comes from `MockAgentProvider`, which replays a scripted multi-agent run
over SSE. The provider is chosen by the `AGENT_PROVIDER` environment variable
(`mock` by default) and implements a single interface in `server/src/agents/provider.ts`, so the
CrewAI service can be added as another provider without touching the client.

## Environment

`server/.env` (optional):

```
PORT=4000
AGENT_PROVIDER=mock
```
