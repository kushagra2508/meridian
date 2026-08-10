# Meridian Crew — Planner agent

A [CrewAI](https://docs.crewai.com/v1.15.14/en/introduction) agent that answers one
question: **can this client reach this goal, and if not, what is the smallest
change that gets them there?**

The agent owns four tools. Every tool is deterministic and offline — the LLM
decides *which* tool to call and how to read the result, but never does the
arithmetic itself.

| Tool | What it does | Implementation |
| --- | --- | --- |
| `nav_history` | Reads pre-fetched category CAGR + volatility | `data/nav_history.json`, rebuilt by `scripts/pull_nav_history.py` from [mfapi.in](https://www.mfapi.in) |
| `goal_solver` | Projects wealth to the target year, computes the shortfall, solves the required return | `numpy-financial` (`fv`, `rate`, `pmt`) |
| `reallocation_search` | Finds the smallest allocation shift that closes the gap | Greedy donor/receiver search |
| `horizon_filter` | Rules out products whose lock-in outlives the goal year | `data/products.json` rule table |

### The tools hand off to each other

The output of each tool is shaped to be the input of the next, so the model never
has to transcribe a number between steps:

- `goal_solver` takes an `allocation` of category keys and blends the returns
  itself. Nothing asks the LLM to compute a weighted average.
- `goal_solver.required_annual_return` feeds `reallocation_search.required_annual_return`.
- `horizon_filter.eligible_categories` feeds `reallocation_search.eligible_categories`,
  so the search cannot propose something the goal date rules out.

Every rate is a decimal (`0.11` means 11%) in both directions.

## Setup

```bash
cd crew
uv venv --python 3.12
uv pip install -e ".[dev]"
cp .env.example .env    # then paste your OPENROUTER_API_KEY
```

## Run the agent

```bash
uv run feasibility \
  --goal "Daughter's undergraduate tuition" \
  --target-amount 5000000 \
  --years 7 \
  --current-corpus 900000 \
  --monthly-contribution 25000 \
  --allocation equity_large_cap=30,hybrid_aggressive=20,debt_short_duration=30,debt_liquid=20
```

`--dry-run` prints the resolved brief and exits without spending tokens.
`--trace` streams every tool call and its result as the agent works.

## Tests

```bash
uv run pytest                  # deterministic tool maths, no network, no LLM
uv run pytest -m live          # one real agent run, needs OPENROUTER_API_KEY
uv run pytest -m network       # re-checks that mfapi.in still answers
```

The default run excludes `live` and `network`, so it stays fast and free.

The offline tests carry the weight. They check that solving for a required return
and then projecting at that return lands back on the target, that the loop used
for stepped-up contributions agrees with `numpy_financial.fv` where they overlap,
that `total_shift_pct` equals the weight that actually changed hands, and that no
search result breaches a cap it was given.

The live test asserts something the offline tests cannot: that the numbers in the
agent's verdict are the same numbers the tools return when called directly. It
also records the tool calls off the CrewAI event bus rather than asking the model
what it did, since a self-report proves nothing.

## Refreshing market data

```bash
uv run python scripts/pull_nav_history.py               # all 13 categories
uv run python scripts/pull_nav_history.py --only debt_gilt
```

The script resolves two to three representative direct-plan schemes per
category, downloads their full NAV series, derives trailing CAGR, annualised
volatility and max drawdown, then takes the **median across schemes** so one
fund's tracking error cannot define a category.

Scheme selection is strict on purpose: a mis-bucketed fund silently poisons every
projection downstream. A name pattern narrows the ~37,000 scheme universe, then
mfapi's own `scheme_category` has to confirm the bucket, and anything whose latest
NAV is stale (a merged or wound-up fund) is dropped. Direct plans only, so returns
are never compared across different expense ratios.

## The two judgement calls

Both concern the same problem: trailing returns are not forward returns.

**A haircut on the trailing CAGR.** Quoting trailing CAGR as a forward return
systematically over-promises on whichever asset class just had the best run, so
each category's figure is cut before it reaches the projection maths
(`FORWARD_RETURN_HAIRCUT` in `config.py`: 20% equity, 12% hybrid, 5% debt, 25%
commodity). `nav_history` returns the raw trailing numbers *and* the adjusted
`assumed_forward_return`, so nothing is hidden from the agent.

**A weight cap on commodity.** Gold's trailing five-year CAGR is the highest
number in the dataset, so an unconstrained return search puts the portfolio in
gold. No haircut big enough to change that would be honest about the measured
data, so the judgement is expressed where it belongs — as a portfolio-construction
limit. `DEFAULT_ASSET_CLASS_CAPS` in `reallocation_search.py` caps commodity at
10%: a diversifier held in single digits, not a growth engine. Override per call
with `max_asset_class_pct` when a mandate says otherwise.

These are planning assumptions, not forecasts. Change them deliberately.

## Layout

```
crew/
├── scripts/pull_nav_history.py    # mfapi.in ETL
├── src/meridian_crew/
│   ├── config.py                  # model selection + return assumptions
│   ├── datasets.py                # cached JSON loaders
│   ├── data/                      # nav_history.json, products.json
│   ├── tools/                     # the four tools
│   ├── agent.py                   # Planner agent + task
│   ├── crew.py                    # crew assembly and kickoff
│   ├── trace.py                   # event-bus tap for --trace and --stream
│   ├── stream.py                  # NDJSON events for the Express bridge
│   └── __main__.py                # CLI
└── tests/
```

## Two things the first live run taught us

Both are pinned by tests now, and both are worth knowing before adding a fifth tool.

**Never put a free-keyed mapping in a tool schema.** `allocation` started life as
`dict[str, float]`. JSON Schema can only describe that through
`additionalProperties`, which strict function-calling does not support, so the
model was handed an object with no nameable keys — and it dutifully sent `{}` four
times in a row before giving up. Allocations now cross the boundary as
`[{"category": ..., "weight_pct": ...}]`, where every field is declared. The
`coerce_allocation` layer still accepts dicts and strings for human callers.

**Do not let the model set house policy.** In that same run gpt-5-mini filled in
every optional argument, including `max_weight_per_category=100`, apparently
guessing at the default and switching off the concentration limit in the process.
Per-client constraints (`max_equity_pct`, `locked_categories`,
`eligible_categories`) are arguments. Firm policy — the per-category cap and the
search step — is now constructor configuration on the tool and is not advertised
to the model at all.

## Notes and limits

- `reallocation_search` reports blended volatility as an **upper bound**: without
  a correlation matrix it assumes the categories move together. Real blended
  volatility will be lower.
- Category returns are Indian mutual fund categories in INR, because mfapi.in is
  the AMFI archive. The `goal_solver` maths is currency agnostic.
- Projections are nominal and gross of tax and exit loads. There is no inflation
  adjustment: pass a target already stated in future rupees.
- `horizon_filter` separates the hard test (lock-in) from soft ones (exit load,
  suitability). Only lock-in excludes; the rest are advisories, and only
  categories that pass both reach `eligible_categories`.
- Importing the package points `CREWAI_STORAGE_DIR` at `crew/.crewai` and turns
  telemetry off, so a run leaves nothing outside the repository.
- The agent is advisory scaffolding for a demo, not regulated advice.

## Wiring into the Express server

The agent is live behind the API's provider seam. `CrewAgentProvider`
(`server/src/agents/crewProvider.ts`) spawns `python -m meridian_crew --stream`,
reads its newline-delimited JSON, and maps each line onto the `AgentEvent` union
the console already renders:

```bash
cd server && AGENT_PROVIDER=crew npm run dev
curl -N "localhost:4000/api/agent/stream?prompt=Can+we+fund+tuition&years=7"
```

Three details make that boundary work:

**One JSON object per line, flushed immediately.** `stream.py` never writes a
partial line, so the reader can split on newlines with no buffering rules of its
own. Without the flush the whole run arrives at once when the process exits,
which is a file, not a stream.

**Python assigns tool refs; Node assigns ids and timestamps.** A tool result has
to name the call it answers or the console renders two unrelated lines instead of
one row that fills in. CrewAI's events carry no such id, so `trace.py` numbers
each call and the result quotes it back. Timestamps belong to Node, because that
is the process that knows when the browser saw the line.

**Closing the stream kills the child.** The route aborts on `req.close`, which
sends `SIGTERM` to the Python process, and the `finally` block `SIGKILL`s anything
still alive. An abandoned browser tab must not leave an LLM run billing in the
background.

This provider is opt-in via `AGENT_PROVIDER=crew` and `mock` stays the default,
because the Vercel deployment runs Node only and has no Python to spawn. The
hosted demo therefore streams the mock; the real agent runs locally.
