# Changelog and build guide: Phase 1 and Phase 2

This file exists so you can understand, in plain English, everything that was
built across Phase 1 and Phase 2: what changed, what it means, and where it
lives. It is written to be read top to bottom.

Two companion documents go deeper where useful:
- `mcp/BUILD_LOG.md` is the teaching journal for the MCP build (the how and why,
  with interview-ready talking points).
- The live tool has an in-page "Build log" in its Model construction tab, written
  for non-technical readers (your partner and friend).

Every entry below follows the same shape:

> **What changed** what was actually added or altered.
> **What it means** why it matters, in everyday terms.
> **Where it lives** the files involved.

A full glossary sits at the bottom. If a word is unfamiliar (MCP, parity,
serverless, Fluid Compute), jump there first.

---

## Where we started (before any of this)

The project was three things that had to agree with each other by hand:

1. `web/index.html` (mirrored to `index.html`) the single-file interactive tool.
2. `model/*.py` Python that computes the price estimate, the suburb scores and
   the forecast.
3. `data/*.json` the shared numbers (suburbs, baseline forecast, criteria).

The maths lived in two places at once: the Python, and a re-typed copy inside the
HTML's JavaScript. They were kept in step by discipline and tests. That is the
starting point Phase 1 set out to improve.

---

# Phase 1: the engine, extracted and proven

**Goal:** take the model maths out of the page and the Python, put it in one
reusable, strongly typed library, and *prove* it still produces the same numbers
to the dollar. That library is the asset everything else is built on.

## 1.1 A new engine library (`mcp/`)

> **What changed** A new TypeScript library under `mcp/src/` that contains the
> model logic as plain functions: `estimate` (price), `scoreSuburb` / `rank`
> (suburb fit), `buildTimeline` / `metrics` (the forecast), and `assessProperty`
> (estimate plus pros and cons). It reads the same `data/*.json` the Python and
> the page read, so there is still one set of numbers.
>
> **What it means** The maths now lives in exactly one place that any program can
> call: the website, a test, or (in Phase 2) an AI assistant. "Strongly typed"
> means the editor and compiler catch mistakes (passing text where a number is
> expected) before the code ever runs. This is the difference between a script
> and a dependable component.
>
> **Where it lives** `mcp/src/avm.ts`, `scoring.ts`, `scenario.ts`, `assess.ts`,
> `data.ts`, `types.ts`, `util.ts`, `index.ts`.

## 1.2 A cross-language parity test (the headline of Phase 1)

> **What changed** A test (`mcp/test/parity.ts`) that runs the original Python
> model and the new TypeScript engine over the same inputs and checks that every
> single number matches: 179 checks. A small Python helper
> (`mcp/test/gen_fixtures.py`) emits the canonical numbers; the test compares.
>
> **What it means** This is how you *trust* a rewrite. Instead of hoping the new
> code matches the old, a machine proves it on every change, down to the last
> dollar. It is wired into the deploy gate, so the website and the model can never
> silently drift apart. In industry this is called a "golden" or "parity" test,
> and having one is a strong signal of engineering maturity.
>
> **Where it lives** `mcp/test/parity.ts`, `mcp/test/gen_fixtures.py`,
> `tests/run.sh` (step 5).

## 1.3 The rounding bug (a genuinely useful lesson)

> **What changed** The parity test failed on one number (73.2 vs 73.3). The cause:
> Python's `round()` uses "round half to even" (banker's rounding, so 0.5 rounds
> to 0 and 1.5 to 2), while JavaScript's `Math.round()` uses "round half up".
> Fixed by reimplementing Python's exact rule in `pyRound`, using an exact
> halfway test rather than a fuzzy one.
>
> **What it means** Two languages can disagree on something as basic as rounding,
> and that disagreement only surfaced because the golden test existed. The fix and
> the story are written up in `BUILD_LOG.md` as a teaching example: tiny numeric
> details matter, and tests are how you catch them.
>
> **Where it lives** `mcp/src/util.ts` (`pyRound`), the war-story section of
> `mcp/BUILD_LOG.md`.

---

# Dynamic profiles: one model, any buyer (Western Australia)

**Goal:** the model was hard-wired to one buyer (Como, a fixed budget, fixed
criteria). Make the buyer an *input* so anyone in WA can use it, and make the
answer adapt to their money and their priorities. Price estimation was left
unchanged on purpose.

## 2.1 The buyer became a typed input

> **What changed** A `BuyerProfile` type and a JSON Schema describing it: region,
> the suburb you want to live near (the "anchor"), age, income, finances
> (deposit, spare cash, any credit facility and its rate, whether you rent),
> life stage, how much you care about each criterion (0 to 5), and hard filters
> (minimum beds, land, distance). Two worked examples are committed.
>
> **What it means** Instead of the model assuming one person, it now asks who you
> are and tailors everything to you. The schema is a contract: it spells out
> exactly what the model expects, which is also what makes it safe to expose as a
> tool later.
>
> **Where it lives** `mcp/src/types.ts`, `data/profile.schema.json`,
> `data/profiles/como-family-patient.json`,
> `data/profiles/first-home-small-deposit.json`.

## 2.2 Location became real distance, not a fixed column

> **What changed** Latitude and longitude were added to all 14 suburbs, and a
> `geo.ts` module computes the real great-circle distance (the "haversine"
> formula) from your chosen anchor to every suburb.
>
> **What it means** Before, "distance" was a single number baked in for Como. Now
> the map recentres on wherever *you* want to live, and the proximity score is
> computed live. Choose Dianella and the rankings re-sort around the north of the
> river; choose Como and they re-sort around the south.
>
> **Where it lives** `data/suburbs.json` (lat/lng), `mcp/src/geo.ts`.

## 2.3 Budget and buy-timing that adapt to your money

> **What changed** A `finance.ts` module turns income and cash position into two
> things: a realistic price band (from borrowing capacity plus your own funds,
> bounded by a sensible deposit rule), and a "buy-timing posture" scored 0 to 100
> with plain-English reasons. The posture comes out as *act now*, *balanced*, or
> *patient and opportunistic*.
>
> **What it means** This is the heart of the brief: the same market should look
> different to different people. A renter with a thin deposit is told to buy when
> serviceable rather than try to time a dip (act now). Someone with a strong cash
> position and a low-cost facility is told they can afford to wait for the better
> entry (patient). The model now *says* that, with the reasons.
>
> **Where it lives** `mcp/src/finance.ts`, `mcp/src/profile.ts` (resolves a raw
> profile into budget, timing and weights).

## 2.4 Suburb and listing recommendations that follow your priorities

> **What changed** A `recommend.ts` module scores suburbs and live listings
> against *your* resolved profile (your anchor for distance, your 0 to 5 criteria
> turned into weights, your budget penalising over-budget areas), and an
> `onboarding.ts` module defines the exact questions to ask a new user.
>
> **What it means** The "where to buy" answer and the listing matches now move
> with your preferences. Lean toward schools and the school-zone suburbs rise;
> lean toward proximity and the close-in suburbs rise. The onboarding questions
> are the script an assistant follows to set you up.
>
> **Where it lives** `mcp/src/recommend.ts`, `mcp/src/onboarding.ts`.

## 2.5 Tests that lock in the behaviour

> **What changed** A unit test (`mcp/test/profile.test.ts`, 23 checks) asserts the
> rules: WA-only guard, budget rises with income, the renter-vs-cash-rich timing
> contrast, the ranking changing with the anchor, and the weights always summing
> to 1.
>
> **What it means** The brief's headline requirement ("a small-deposit renter
> should not buy in the same window as a cash-rich buyer with a 0% facility") is
> now a test, not a claim. If a future change broke it, the gate would catch it.
>
> **Where it lives** `mcp/test/profile.test.ts`, `mcp/package.json`
> (`test:engine = parity + profile`), `tests/run.sh`.

---

# Phase 2: the model as an MCP server, live on Vercel

**Goal:** put the engine on the internet as a set of tools an AI assistant can
call directly, hosted on Vercel.

## 3.1 What MCP is (one paragraph)

MCP (Model Context Protocol) is a standard way to expose your app's functions as
"tools" that an AI assistant can call. You describe each tool (its name, what it
does, and the shape of its inputs); the assistant can then call it and use the
result. The skill is clean tool design plus a trustworthy engine behind them. The
transport here is "Streamable HTTP": the assistant talks to your server over plain
web requests.

## 3.2 The server app (`server/`)

> **What changed** A self-contained Next.js app under `server/` that hosts the MCP
> endpoint at `POST /api/mcp`. It uses the `mcp-handler` library over Streamable
> HTTP in "stateless" mode (each request stands alone, so no database or Redis is
> needed). A small landing page documents the endpoint and tools.
>
> **What it means** This is the public face of the engine: a single URL an
> assistant connects to. "Stateless" keeps it cheap and simple, it runs as one
> serverless function with nothing to maintain between calls.
>
> **Where it lives** `server/app/api/[transport]/route.ts`, `server/app/page.tsx`,
> `server/app/layout.tsx`, `server/package.json`, `server/next.config.mjs`,
> `server/tsconfig.json`.

## 3.3 The eleven tools

> **What changed** Each engine capability is exposed as one MCP tool, with its
> inputs described as a `zod` schema that mirrors the engine types:
>
> | Tool | What it does |
> |---|---|
> | `estimate_price` | Likely price and range for a WA house |
> | `assess_property` | Estimate plus a buyer-fit read with pros and cons |
> | `forecast` | Bear/base/bull scenario fan to Mid-29 plus headline metrics |
> | `score_suburb` / `rank_suburbs` | Scoring against the original Como criteria |
> | `list_suburbs` | The dataset, with medians and the in-band flag |
> | `onboarding_questions` | The questions to ask a new buyer |
> | `resolve_profile` | A profile turned into budget, timing and weights |
> | `rank_suburbs_for_profile` | Suburb ranking for a specific buyer |
> | `match_listings` | Listings filtered and ranked for a buyer |
> | `search_listings` | Live for-sale houses with photos (RapidAPI) |
>
> **What it means** An assistant can now do real work: "what is this house worth",
> "rank suburbs for me leaning toward schools", "find listings that fit". Each tool
> is a thin wrapper: validate inputs, call the parity-tested engine, return the
> result. The hard correctness work was already done in Phase 1.
>
> **Where it lives** `server/app/api/[transport]/route.ts`, `server/lib/schema.ts`.

## 3.4 Three real problems hosting an engine serverless surfaced

> **What changed**
> 1. **Data loading that survives bundling.** The engine read its JSON with
>    `readFileSync` and a computed path. A serverless build cannot see a computed
>    path, so the data would not ship and the function would fail at runtime. Fix:
>    load the JSON with static `import` statements instead. Parity stayed 179/179.
> 2. **A self-contained deploy without duplicating the source of truth.** Vercel
>    wants one folder with everything inside it. A sync script copies the engine
>    and data into `server/` automatically, and the deploy gate fails if the copy
>    drifts from the original.
> 3. **`.js` import resolution.** The engine imports `"./util.js"` to mean
>    `util.ts` (a Node convention); one line in `next.config.mjs` teaches the
>    bundler to follow that.
>
> **What it means** Running code "in the cloud" is not the same as running it on
> your laptop; the build tooling has rules you have to satisfy. These three fixes
> are exactly the kind of practical knowledge that separates "it works locally"
> from "it is deployed". All three are written up in `BUILD_LOG.md`.
>
> **Where it lives** `mcp/src/data.ts` (static imports),
> `server/scripts/sync-engine.mjs`, `server/next.config.mjs`, `tests/run.sh`
> (steps 6 and 7).

## 3.5 Access control and secrets

> **What changed** A bearer-token gate: if `MCP_BEARER_TOKEN` is set, every request
> must send `Authorization: Bearer <token>` or it gets a 401; if it is unset the
> endpoint is open (handy before the secret is wired). The live-listings tool uses
> `RAPIDAPI_KEY`; with no key it returns the committed sample.
>
> **What it means** Your server is private by a shared secret, and the secret lives
> in Vercel, never in the code. We verified the live endpoint returns exactly this
> 401 when called without the token, which proves both the function and the gate
> work.
>
> **Where it lives** `server/lib/auth.ts`, `server/lib/listings-live.ts`.

## 3.6 Deployed to Vercel, with Fluid Compute and a longer timeout

> **What changed** The project is deployed via Vercel's GitHub integration (root
> directory `server`). `server/vercel.json` turns on **Fluid Compute** and sets the
> function **maxDuration to 300 seconds**; the route mirrors that limit.
>
> **What it means** "Fluid Compute" lets one warm instance serve several calls and
> hold a streaming response open, which suits MCP (a tool turn can stream results
> back). Raising maxDuration from the default to 300s means a longer turn, for
> example several live-listing fetches, will not be cut off. Both are set in code
> (`vercel.json`), so the infrastructure is reproducible rather than clicked-in.
>
> **Where it lives** `server/vercel.json`, `server/app/api/[transport]/route.ts`,
> `server/DEPLOY.md` (the import-and-configure steps).

## 3.7 Connecting an AI client

> **What changed** The server is reachable at
> `https://mbcb-realestatemodel-pertg.vercel.app/api/mcp` and works with any MCP
> client (Claude Code, Claude Desktop) by pointing it at that URL with the bearer
> header.
>
> **What it means** Once connected, you can say things like "rank suburbs leaning
> toward schools" or "estimate 12 Example St, Shelley, 4 bed 720sqm" and the
> assistant calls your tools and answers from the live model.
>
> **Where it lives** `server/README.md`, `server/DEPLOY.md`.

---

## Post-launch refinements

### Usability: guided prompts and visible scope

> **What changed** Added MCP **prompts** (`/find_a_home`, `/estimate_a_listing`,
> `/about_this_tool`) that the client shows as labelled fill-in forms; every tool
> result is prefixed "Como home model - Western Australia (Perth) only"; the
> guided flow refuses to invent financial figures and asks instead.
>
> **What it means** The server stopped being an open chat where you had to know
> what to type. You pick a prompt from the "/" menu, fill the fields, and it runs
> the engine correctly within the WA-only scope.
>
> **Where it lives** `server/lib/prompts.ts`, `server/app/api/[transport]/route.ts`.

### Correctness: equity is borrowed money, not cash

> **What changed** The budget model now separates genuine **cash** (deposit +
> buffer, servicing-free) from **borrowed funds** (a credit facility, or equity
> released from a property you already own). Borrowed funds still help cover the
> price, but they carry a monthly carrying cost at their rate that reduces how
> much you can safely borrow for the new home. Interest-free money carries no
> cost, so it still behaves like cash. You can give the equity amount directly, or
> a property's value and mortgage and the model computes usable equity at 80% LVR.
> The budget result now reports the cash vs borrowed split and the monthly
> servicing.
>
> **What it means** The old model treated a credit line or released equity as if
> it were cash, which overstated the safe budget for anyone whose facility was not
> interest-free. Now a dollar of borrowed equity at, say, 6% buys less house than a
> dollar of cash, which is the truth. (An interest-free family facility is
> unchanged.)
>
> **Where it lives** `mcp/src/finance.ts` (`budgetBand`, `carryingCost`),
> `mcp/src/types.ts`, `data/profile.schema.json`, `mcp/test/profile.test.ts`
> (6 new checks).

## Glossary

- **Engine vs server.** The *engine* is the maths as reusable functions
  (`mcp/src`). The *server* (`server/`) is the thin web layer that exposes the
  engine over the internet. Separating them is what let us test the maths in
  isolation and reuse it unchanged.
- **MCP (Model Context Protocol).** A standard for exposing app functions as
  tools an AI assistant can call.
- **Tool.** One callable function exposed over MCP, with a described input shape.
- **Parity / golden test.** A test that proves new code matches a trusted
  reference exactly (here, TypeScript matches the original Python to the dollar).
- **Type / strongly typed.** Declaring what shape data has (number, text, a
  specific object) so mistakes are caught while writing code, not at runtime.
- **zod.** A library for describing and validating input shapes at runtime; used
  to define each tool's inputs.
- **AVM (Automated Valuation Model).** The price estimator: it starts from the
  suburb median and adjusts for land, beds, baths and condition.
- **Hedonic adjustment.** Pricing individual features (an extra 100sqm of land, a
  fourth bedroom) rather than just the whole property.
- **Serverless function.** Code that runs on demand in the cloud with no server to
  manage; it spins up for a request and goes away after.
- **Streamable HTTP.** The web transport MCP uses here; supports streaming the
  response back as it is produced.
- **Stateless.** Each request is self-contained; the server keeps nothing between
  calls, so it needs no database or Redis.
- **Fluid Compute.** A Vercel mode that keeps a warm instance, serves several
  calls on it, and supports long streaming responses; cheaper and better suited to
  this workload.
- **maxDuration.** The longest a single function call may run before the platform
  stops it. Raised to 300s here.
- **Bearer token.** A shared secret sent in the `Authorization` header to prove a
  request is allowed.
- **Vendoring.** Committing a copy of code or data into a project so it is
  self-contained; here a sync script keeps the copy identical to the original and
  the gate enforces it.
- **Haversine.** The formula for distance between two points on a sphere (used for
  suburb distances from your anchor).
- **Serviceability / borrowing capacity.** How much a lender will advance based on
  income, assessed at a buffered interest rate.

---

## Verify everything yourself

```bash
# Phase 1 + dynamic profiles: the engine, parity and unit tests
cd mcp && npm install && npm test     # typecheck + parity (179) + profile (23)
npm run demo                          # two buyers, two different answers

# The whole project's deploy gate (model, page, sync, dashes)
bash tests/run.sh                     # expect: ALL PASS

# Phase 2: build the server locally
cd server && npm install && npm run build
npm start                             # then POST to http://localhost:3000/api/mcp
```
