# STATUTE — engineering handoff

Build target: working demo on a laptop, 9 Aug 2026. Live judge interaction, 7-minute demo.
Non-negotiable: **no number in the UI may originate from an LLM.**

---

## 0 · What this is and why it is shaped this way

Read this section before writing code. Several decisions below look like over-engineering
until you know what they are defending against.

### 0.1 The product in one paragraph

Meridian is a boutique Indian wealth manager entering the emerging-affluent segment
(₹50L–₹2Cr investable). A separate acquisition engine decides which leads are worth
spending money on, using declared data from an intake form. STATUTE picks up **after**
that spend, once the client's actual holdings are visible, and answers a different
question: given what this person really owns, is their stated financial goal reachable,
and what does reaching it cost after tax and distributor drag?

Four software agents with conflicting objectives argue about it. The system never issues
advice. It prices consequences and, when the goal cannot be met, reprices the goal.

### 0.2 The competition constraints this is built against

| Constraint | Consequence for the build |
|---|---|
| Judges change inputs live and expect real-time response | Every lever must re-run the full engine synchronously |
| No hallucinated, assumed, or made-up data | Every figure traces to a source, a statute, or a badged assumption |
| Must make decisions at each step, not follow a script | Agents branch on computed state and can override each other |
| 7-minute demo, hostile network, single laptop | Zero runtime network dependency in the critical path |

The last one drives more of this spec than anything else. Assume the venue wifi fails.

### 0.3 The central architectural decision

**Positions are computed. Conversation is generated.**

Every number a judge sees comes from deterministic TypeScript. The LLM receives those
numbers already computed and writes only the sentences around them. It is never asked to
calculate, infer, round, or fill a gap.

Three things fall out of this, and all three matter more than they look:

1. **It cannot hallucinate a figure**, because it is never asked for one. This is the
   direct answer to the no-made-up-data rule, and it is the answer to give if challenged.
2. **It survives a dead API.** Numbers recompute regardless; prose falls back to cache.
   The demo still visibly responds to a judge's slider with the network unplugged.
3. **It is still genuinely agentic.** Each agent holds its own objective function, its own
   tools, and can condition on or contradict the previous agent's output. The sequence
   branches on computed state. Arbitration does not require an LLM in the loop.

If you are tempted to let the model compute something "just this once", don't. That single
call is the thing the whole architecture exists to prevent.

### 0.4 Why these four agents

Each earns its seat by having a distinct objective that can genuinely lose an argument.

| Agent | Objective | Fights with | Why it exists |
|---|---|---|---|
| Feasibility | Close the gap without breaking the deadline | everyone | Proposes; without it nothing to argue about |
| Statute | Minimise realised tax on the proposal | Feasibility | Tax is the only cost a wealth manager can price with certainty |
| Channel | Eliminate ongoing distributor drag | Statute | Carries the firm's core commercial thesis, that distribution margin is the client's loss |
| Reframe | Make the goal reachable | Feasibility | Moves the goal instead of the money when nothing else works |

The sharpest conflict is Statute versus Channel: escaping drag requires exiting, and
exiting realises gains. **Both agents are correct simultaneously.** That is the moment the
demo is built around, so do not smooth it over in the ledger or the verdict.

A fifth agent (Liquidity) was cut because at allocation level it had nothing to say on most
inputs, and an agent that reports "no concerns" makes the whole committee look decorative.
Its one real job, horizon versus lock-in, folded into Feasibility as a constraint the agent
announces aloud.

An Economics agent that refused unprofitable clients was also cut. The upstream acquisition
engine already qualifies leads before spend, so refusing them post-conversion saves nothing
and duplicates another system's logic. Reframe replaced it.

### 0.5 The flow, and what each screen is for

```
S1 Handoff     → shows what the upstream engine BELIEVED (declared data)
S2 Position    → captures what is ACTUALLY held (observed data)
S3 Goal        → the client states the target
S4 Eligibility → SEBI ladder, deterministic, no AI
S5 Committee   → the four agents deliberate            ← the demo
S6 Verdict     → ranked paths, or repriced goals
S7 Reshuffle   → any lever re-runs the whole thing     ← the interactivity proof
```

Two screens exist for reasons that are not obvious from their content:

**S1 exists to set up a disagreement.** The acquisition engine ranked this lead on declared
income. STATUTE will often reach a different conclusion from observed position. That gap is
the point, not a bug, and S1 plants it so S5 can pay it off.

**S4 exists to prove regulation drives segmentation before any AI runs.** It is the first
screen that visibly changes when a judge moves the wealth slider, which establishes
responsiveness early and cheaply, before the expensive committee screen has to carry it.

### 0.6 Data honesty rules

Three badge tiers, applied to every figure without exception:

- `live` — pulled from a real source, shown with source and date
- `statute` — a rule from law, shown with its section number
- `assumption` — our model, shown with a value and a range

Where data does not exist, **the responsible agent says so out loud** rather than the system
quietly filling the gap. Three known gaps, each deliberately surfaced:

- Real estate has no sourceable per-client valuation → held as non-growing, non-liquid corpus
- Direct equity holdings are unknown → projected at a Nifty 50 index proxy, disclosed as a proxy
- Bank-RM versus MFD cost differential is not published → Channel prices plan-type spread only

This is not defensiveness. An agent that names the limit of its own evidence is more
credible than one that covers more ground, and a judge who finds an unsourced number you
did not flag will discount everything else on the screen.

---

## 1 · Stack

```
Vite + React 18 + TypeScript
Tailwind (tokens below)
Recharts (allocation ribbon only)
Express proxy, single route, for the one Anthropic call
No state library. useReducer in one store file.
No routing library. A `screen` enum in state.
```

Run: `npm run dev` on 5173, proxy on 8787. Offline flag `VITE_OFFLINE=1` skips the LLM entirely and uses cached prose.

**Why so little.** No Redux, no router, no agent framework. The control flow is a fixed
four-step sequence with one conditional branch, which is a loop and an `if`. LangGraph or
similar buys nothing here and costs an evening debugging someone else's abstraction on
submission day. If asked whether it is "really" agentic, the answer is the objective
functions and the branching, not the dependency list.

The Express proxy exists only to keep the API key off the client. It is one route and
about twenty lines. If it becomes a problem, run with `VITE_OFFLINE=1` and ship cached
prose — the demo is fully functional without it.

---

## 2 · File tree

```
src/
  data/reference.json        ← pre-fetched, committed, never fetched at runtime
  data/personas.json
  data/cachedProse.json      ← LLM fallback, one entry per agent per scenario
  engine/
    projection.ts            Feasibility maths
    tax.ts                   Statute rules
    drag.ts                  Channel maths
    reframe.ts               Reframe maths
    eligibility.ts           SEBI ladder
    committee.ts             orchestrator, returns AgentPosition[]
    ledger.ts
  prose/
    buildPrompt.ts
    callClaude.ts
  screens/  S1Handoff S2Position S3Goal S4Eligibility S5Committee S6Verdict
  store.ts
server/proxy.ts
scripts/prefetch.mjs
```

---

## 3 · Pre-fetch script — run this first

**Why pre-fetch rather than call live.** The data is equally real either way, and a live
call adds a venue-wifi dependency to the critical path for zero credibility gain. The
timestamp is shown in the UI footer, so this reads as engineering judgement rather than
evasion. A refresh button may re-pull if the network happens to be up; it is allowed to
fail silently.

**Why fund NAVs stand in for four asset classes.** mfapi.in covers equity, debt, gold and
broad-market equity through funds that track them. One free source, no auth, four
categories. The direct-equity proxy is the compromise: actual stock holdings are unknown
and must not be invented, so an index return is applied and **disclosed as a proxy** in the
agent's own words.

`scripts/prefetch.mjs`, run once, writes `src/data/reference.json`.

Pull from `https://api.mfapi.in/mf/{code}` for a fixed basket. Compute CAGR and annualised
stdev from 5 years of NAV history.

| Category | Basket | Used as |
|---|---|---|
| `equity_mf` | 3 large/flexi-cap direct growth schemes | Equity MF return |
| `debt_mf` | 3 short-duration / corporate bond schemes | Debt MF return |
| `direct_equity` | 1 Nifty 50 index fund | **Index proxy** for direct equity |
| `gold` | 1 gold fund or gold ETF FoF | Gold return |

Hand-enter with source and date beside each: FD rate, TER spreads.

```jsonc
{
  "generated_at": "2026-08-09T18:40:00+05:30",
  "categories": {
    "equity_mf":     { "cagr": 0.142, "vol": 0.171, "source": "mfapi.in", "schemes": [118834, 120503, 122639], "proxy": false },
    "debt_mf":       { "cagr": 0.071, "vol": 0.021, "source": "mfapi.in", "schemes": [...], "proxy": false },
    "direct_equity": { "cagr": 0.131, "vol": 0.158, "source": "mfapi.in", "schemes": [120716], "proxy": true,
                       "proxy_note": "Nifty 50 index fund used as broad-market proxy. Actual holdings unknown." },
    "gold":          { "cagr": 0.118, "vol": 0.142, "source": "mfapi.in", "schemes": [...], "proxy": false },
    "fd_cash":       { "cagr": 0.067, "vol": 0.0, "source": "SBI retail FD card, 08 Aug 2026", "proxy": false },
    "real_estate":   { "cagr": 0.0,   "vol": 0.0, "source": null, "excluded": true,
                       "exclusion_note": "No sourceable per-client valuation. Held as non-growing, non-liquid corpus." }
  },
  "ter_spread": {
    "equity_mf": 0.0075, "debt_mf": 0.0040,
    "source": "AMFI scheme TER disclosures, 08 Aug 2026",
    "scope_note": "Plan-type spread exists only for mutual funds."
  },
  "sebi_minimums": { "pms": 5000000, "aif": 10000000, "uhni": 20000000 },
  "aif_lockin_years": 7
}
```

**If a scheme code 404s, the script must fail loudly, not silently write a default.**

---

## 4 · State shape

```ts
type Position = {
  totalWealth: number;
  alloc: { equity_mf:number; debt_mf:number; fd_cash:number; direct_equity:number; gold:number; real_estate:number }; // fractions, sum 1
  channel: { direct:number; distributor:number }; // sum 1
  unrealisedGainPct: number; // default 0.25, ASSUMPTION badge, exposed as advanced input
};
type Goal = { amount:number; year:number; purpose:string; note:string };
type Handoff = { persona:string; priorityTier:number; declaredIncomeBand:string;
                 channelUsed:string; pursueDecision:'PURSUE'|'DEFER';
                 futureEvents:{label:string; year:number}[]; acquisitionCost:number };
```

---

## 5 · Engine

### 5.1 projection.ts

```
n = goal.year - 2026
blendedReturn = Σ alloc[c] × reference.categories[c].cagr      // real_estate contributes 0
projected     = totalWealth × (1 + blendedReturn)^n
gap           = goal.amount - projected
requiredReturn= (goal.amount / totalWealth)^(1/n) - 1
```

Reallocation search: shift from `fd_cash` → `equity_mf` in ₹1L steps until `projected ≥ goal.amount`.
Hard cap total equity exposure (equity_mf + direct_equity) at 0.85. If capped and still short,
`feasible = false` and Reframe fires.

Horizon filter: if `n < reference.aif_lockin_years` and wealth ≥ AIF minimum, mark AIF
`ruledOut` with reason. Feasibility must state this aloud even though it is a non-event.

### 5.2 tax.ts — four rules only

**Why so narrow.** The scope is deliberately four rules, not a tax engine. A wealth manager
prices the consequence of a decision; a CA files a return. Set-off, carry-forward, rollover
exemptions and residency rules are all out of scope because none of them are needed to
answer "what does this switch cost", and each one added is a new surface for a judge to
find an error in. Every rule that survives carries its section number as a badge.

`unrealisedGainPct` is the one figure with no source: nobody publishes how much of a given
client's holding is embedded gain. It is defaulted to 25%, badged as an assumption, and
**exposed as an adjustable input** so a judge can change it rather than discover it.

```
switchAmount = rupees moved out of a sleeve
embeddedGain = switchAmount × unrealisedGainPct        // ASSUMPTION badge

equity sleeves (equity_mf, direct_equity):
  LTCG §112A: max(0, gain - 125000) × 0.125
  STCG §111A: gain × 0.20                              // only if holding < 12m; default LTCG
debt_mf / fd_cash:
  slab rate from declaredIncomeBand → marginal { '<50L':0.30, '50L-1Cr':0.30, '1Cr-2Cr':0.30 }
gold: LTCG 12.5% after 24 months

surcharge: band by income, CAPPED AT 15% for 111A/112A gains
cess: 4% on (tax + surcharge)
```

`fyStager()`: splitting a switch across FY26-27 and FY27-28 uses the ₹1.25L exemption twice.
`saving = min(gain - 125000, 125000) × 0.125`. Returns null if gain ≤ ₹1.25L.

Every returned object carries `{ amount, section, label }`. Section string renders as the badge.

### 5.3 drag.ts

```
mfValue           = (alloc.equity_mf + alloc.debt_mf) × totalWealth
distributorHeld   = mfValue × channel.distributor
annualDrag        = (alloc.equity_mf × totalWealth × channel.distributor × spread.equity_mf)
                  + (alloc.debt_mf   × totalWealth × channel.distributor × spread.debt_mf)
outOfScopeValue   = totalWealth - mfValue
```

**Channel must always return `outOfScopeValue` and state it.** If `annualDrag === 0`, the agent
says so plainly — do not synthesise a figure. This is the correct behaviour on a 90% direct-equity
Persona 5.

### 5.4 reframe.ts — closed form, no dependency

```ts
const r = blendedReturn;
// slip: how many years until current path reaches the target
slipYears   = Math.log(goal.amount / totalWealth) / Math.log(1 + r);
slipMonths  = Math.round((slipYears - n) * 12);
// shrink: what is reachable by the stated year
reachable   = totalWealth * Math.pow(1 + r, n);
// top-up: monthly contribution to hold both target and date  (PMT, annuity-due = end)
const rm = Math.pow(1 + r, 1/12) - 1, nm = n * 12;
monthly     = (goal.amount - totalWealth * Math.pow(1 + rm, nm)) * rm / (Math.pow(1 + rm, nm) - 1);
```

Each of the three options is re-run through `tax.ts` and `drag.ts`. The slip and shrink options
usually require no switching, so tax cost is ₹0 — tag that option `NO PORTFOLIO CHANGE REQUIRED`.

If going Python instead, `numpy-financial` gives `nper`, `fv`, `pmt` directly. In JS the three
lines above are equivalent and avoid the dependency.

### 5.5 committee.ts

```ts
function runCommittee(position, goal, handoff): { positions: AgentPosition[]; ledger: LedgerRow[]; verdict: Verdict }
```

Fixed sequence with one conditional branch. Not a graph.

```
1. Feasibility  → PROPOSES | CONDITIONS
2. Statute      → OBJECTS if taxCost > 0.02 × totalWealth, else CONDITIONS
3. Channel      → OBJECTS if annualDrag > 0, else CONCEDES
4. Reframe      → only if feasible === false
```

```ts
type AgentPosition = {
  agent: 'feasibility'|'statute'|'channel'|'reframe';
  stance: 'PROPOSES'|'OBJECTS'|'CONDITIONS'|'CONCEDES';
  figures: { key:string; value:number; badge:{ tier:'live'|'statute'|'assumption'; label:string } }[];
  referencesAgent: string | null;   // drives the ochre connector
  scopeLimits: string[];            // what this agent could not price
};
```

**Determinism guarantee: `runCommittee` is pure, synchronous, and never touches the network.**

---

## 6 · The single LLM call

One call per run. Numbers go in, prose comes out. Never ask the model to compute.

`prose/buildPrompt.ts` serialises `AgentPosition[]` and requests:

```
Return ONLY a JSON array of 3 or 4 objects, no markdown, no preamble:
[{ "agent": "...", "claim": "<one sentence, max 25 words>",
   "opening": "<opens by naming the previous agent's claim, max 20 words, null for the first>" }]

You are writing the voice of each agent in a wealth planning committee.
Every figure is supplied. Do not compute, infer, round, or introduce any number
that is not in the input. Do not give advice. State positions.
```

`callClaude.ts`:
- model `claude-sonnet-4-6`, `max_tokens: 1000`
- 6-second timeout → fall back
- strip ``` fences, `JSON.parse` in try/catch → fall back
- validate every returned object has a known agent name → fall back
- fallback source: `data/cachedProse.json`, keyed by agent + stance

**On fallback, render normally and show a small Slate strip: `REASONING CACHED`. Numbers are
unaffected because they never came from the model.**

---

## 7 · Re-run behaviour

**Why numbers must update before prose.** This ordering is the single most important
runtime behaviour in the build. When a judge moves a slider, the ledger and every figure
change instantly because they are pure synchronous computation. The prose catches up a
second or two later. If the API is slow, dead, or rate-limited, the judge still sees the
system respond immediately to their input — which is the thing being assessed. Reverse the
order and a network hiccup looks like a frozen product.

Any lever change:
1. `runCommittee` re-runs synchronously. Ledger and all figures update **immediately**.
2. Stance chips update immediately.
3. Prose call fires; cards re-stream as it returns.

Numbers always lead words. If the API is dead the demo still visibly responds to the judge —
this is the whole reason for the split.

Debounce lever input at 300ms. `Reshuffle` re-runs with identical inputs to show stability.

---

## 8 · Tailwind tokens

```js
colors: { paper:'#F7F5EF', ink:'#14231C', deep:'#17473A', ochre:'#B07A17', slate:'#6B7B74', rule:'#D9D4C7' }
fontFamily: { display:['Newsreader','serif'], body:['Public Sans','sans-serif'], mono:['JetBrains Mono','monospace'] }
borderRadius: { DEFAULT:'2px' }
```

Rupee formatter: `Intl.NumberFormat('en-IN', { style:'currency', currency:'INR', maximumFractionDigits:0 })`.

---

## 9 · Edge cases that must not crash

**Why this table matters more than usual.** Judges are explicitly expected to change inputs
on the spot, and the interesting thing to try is always an extreme. Every row below is a
configuration a curious judge might build in ten seconds. Note that several of them are not
errors at all — 100% real estate producing a huge shortfall, or Channel reporting zero
drag on an all-direct portfolio, are **correct outputs that demonstrate the model's
honesty**. Let them run. Only genuinely invalid states are blocked.

| Input | Required behaviour |
|---|---|
| `goal.year <= 2026` | Block at S3, inline message, no crash |
| Real estate 100% | Blended return 0, gap enormous, Reframe leads. Correct, let it run |
| Direct equity 90%, MF 0% | Channel returns drag ₹0 and says so |
| Wealth ₹10L | Ladder fully greyed, all paths still compute |
| Goal already met | Feasibility CONCEDES, Statute ₹0, verdict shows "no change required" |
| Allocation sums to 99% | Normalise silently on blur |
| Gain below ₹1.25L | Statute returns ₹0 and cites the exemption. Never negative |

---

## 10 · Build order

**Why engine before UI.** Steps 1 and 2 produce no visible progress, which is
psychologically hard under deadline, but debugging financial maths through a browser is
the slowest possible loop. A Node test script hitting the seven edge cases takes twenty
minutes to write and saves hours. Do not skip to the screens.

**Why S5 before every other screen.** It is the only screen the demo genuinely needs. The
rest are context. Building it third means that from that point onward you always have
something to show, and the screen recording taken at that moment is the insurance policy
against everything that comes after.

1. `scripts/prefetch.mjs` → `reference.json`. **Do this first, everything depends on it.**
2. `engine/*` with a Node test script hitting all seven edge cases above. No UI yet.
3. S5 committee screen against hardcoded state. **Screen-record it the moment it works.**
4. S2, S3, S4 wired to the store.
5. S6 both states.
6. S1 handoff, cached prose, failure strip.
7. Mobile landing route with the recording.

Step 3's recording is the insurance policy. If the build stalls at 11pm there is still
something to submit and something to show.
