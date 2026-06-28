# MCP Build Log - Phase 1: extract the engine

A running journal of how this MCP build is being put together, written to teach
the pattern. If you are using this to talk through an MCP build in an interview,
the short version is at the bottom ("How to talk about this").

---

## Why we are doing this

The Como tool today is a single `web/index.html` (static, on GitHub Pages) with
the model logic written **twice**: once in Python (`/model`, the reference and
the test harness) and once in JavaScript inlined in the HTML (what actually runs
in the browser). That is fine for a webpage, but an **MCP server** needs the
model as a set of callable **tools** an AI assistant can invoke.

An MCP server is, at its core, three layers:

```
  AI client (Claude)  --MCP protocol-->  [ transport ]  -->  [ tools ]  -->  [ ENGINE ]
                                          HTTP/stdio          schemas         your logic
```

The transport and tool-schema layers are thin and standard. The valuable,
hard-to-fake part is the **engine**. So Phase 1 does the highest-leverage,
lowest-risk piece first: pull the engine out of the HTML into a clean, typed,
independently-tested library that Phase 2 (the server) and the existing HTML can
both import. Nothing in production changes; this is purely additive.

---

## Before -> After

**Before**
```
model/            Python: avm.py, scoring.py, scenario_model.py   (reference)
web/index.html    a second copy of the same logic, inlined in JS  (what runs)
data/*.json       the shared numbers (suburbs, baseline, criteria)
```
Logic lives in two places with no machine-checked link between them.

**After (this phase)**
```
mcp/src/          ONE typed engine: avm.ts, scoring.ts, scenario.ts, assess.ts
mcp/test/         parity.ts: proves the TS engine == the Python model, to the dollar
data/*.json       still the single source of truth (the engine reads it directly)
```
The engine is now a real module with a typed API and a cross-language test. It
imports the same `data/*.json` the Python and the HTML use, so all three agree.

---

## The build, step by step (with the why)

**1. Project scaffold.** `mcp/package.json` (`"type": "module"` for ESM) and a
strict `tsconfig.json`. Strict mode (`strict`, `noUncheckedIndexedAccess`) is
worth it here: the engine is the thing everything else trusts, so we want the
compiler catching nulls and undefined indexes. Dev tools: `typescript` (the
compiler), `tsx` (run `.ts` directly, no build step while developing),
`@types/node` (types for `fs`/`path`).

**2. Types first (`src/types.ts`).** Defining `Suburb`, `Condition`, `Estimate`
up front turns the JSON blobs into a contract. This is also exactly what the MCP
tool schemas will be generated from in Phase 2, so it is not throwaway work.

**3. The data loader (`src/data.ts`).** Deliberately reads `../../data/*.json`
off disk rather than copying the numbers into the package. Rule we are
preserving: **one source of truth per number.** If a suburb median changes, all
three consumers (Python, HTML, MCP) pick it up.

**4. Port the engine (`avm.ts`, `scoring.ts`, `scenario.ts`, `assess.ts`).**
Each is a faithful line-for-line port of the Python (or, for `assess`, of the
JS, which is where that logic originated). The constants and the order of
operations are copied exactly, because...

**5. ...the parity test (`test/parity.ts`) is the point.** It runs
`gen_fixtures.py` (the Python model) to get canonical numbers, then runs the
SAME inputs through the TS engine and asserts every value matches. 179 checks
across estimates, suburb scores at three slider settings, and the full forecast
timeline. If the port ever drifts, this fails. This is what lets you say "the
TypeScript engine provably behaves like the reference model" rather than "I think
I ported it right."

---

## War story: the rounding bug (the genuinely useful lesson)

First parity run: **178 passed, 1 failed.** One suburb scored `73.2` in TS but
`73.3` in Python.

The cause: Python's `round()` uses **round-half-to-even** (banker's rounding),
while JavaScript's `Math.round()` uses **round-half-up**. So I had written a
`pyRound()` to mimic Python. But my first version detected "is this a halfway
value?" with a fuzzy epsilon (`Math.abs(diff - 0.5) < 1e-9`). That snapped
values that were *near* 0.5 to the even side, when Python (looking at the float's
exact value, which was a hair above 0.5) rounded up.

The fix: JS and Python both use IEEE-754 doubles, and the same arithmetic
produces the same bits, so a value is only truly halfway when its fractional part
is **exactly** 0.5. Changing the test from an epsilon to `diff === 0.5` made all
179 fixtures pass.

Lesson worth carrying: when you port numeric logic across languages, **rounding
and float semantics are where parity breaks**, and the fix is to match the
reference's exact behaviour, not to approximate it. A cross-language golden test
is what surfaces this; without it the bug ships silently.

---

## Update: from one hardcoded buyer to any buyer (the dynamic pivot)

Phase 1 shipped the engine, but every number was wired to one person: Como as the
anchor, the buyer's $800k-$1.1M band, his 25/20/15... criteria weights baked into
`criteria.json`. To be an MCP a stranger can plug in, the engine has to take the
buyer as **input**, not as a constant.

**Before -> After (this change):**

| Was hardcoded | Now an input |
|---|---|
| Anchor = Como, distance = a fixed `km` column | `anchor` is any suburb; distance is computed live by haversine from its lat/lng |
| Criteria weights = the buyer's fixed split | `criteria` is 0-5 per dimension, merged over a life-stage preset, normalised to sum 1 |
| Budget band = $800k-$1.1M constant | `budgetBand(profile)` derives it from income (serviceability) and own funds (LVR) |
| "Patience is cheap" = a stated assumption | `buyTiming(profile)` derives posture from the buyer's actual cash position |

**The new modules (each one thing, all stdlib/no deps):**

- `geo.ts` - `haversineKm` + `distanceKm(anchor, suburb)`. The anchor stops being
  Como; "where you want to live" is now a real coordinate. I added `lat`/`lng` to
  all 14 suburbs in `data/suburbs.json` to support it.
- `finance.ts` - the adaptable core. `borrowingCapacity` is a standard annuity PV
  at the APRA-buffered rate; `budgetBand` takes the **min** of two bounds (total
  funds vs LVR-on-own-funds); `buyTiming` scores urgency 0-100 from renting,
  funds-to-budget ratio, a sub-2% credit facility, horizon and age.
- `profile.ts` - `resolveProfile` is the gatekeeper: it enforces **WA-only**
  (region + a known anchor), merges criteria over a life-stage preset, and returns
  the working parameters (`weights`, `budget`, `timing`, `filters`).
- `recommend.ts` - scores suburbs **and** live listings against the resolved
  profile instead of the fixed criteria, so the area suggestions and listing
  matches move with the user.
- `onboarding.ts` - the question set the MCP will ask a new user, versioned with
  the engine, plus a flat-answers -> `BuyerProfile` mapper.

**Why this is the right shape for an MCP.** An MCP tool is only as good as the
contract around its inputs. By making the buyer a typed `BuyerProfile` (with a
JSON Schema in `data/profile.schema.json`) and resolving it through one guarded
function, Phase 2 can expose `set_profile` / `rank_for_me` tools whose schemas
fall straight out of `types.ts` - the same trick as the rest of the engine.

**The brief, made testable.** The spec said a small-deposit renter "should not buy
in the same period" as a cash-rich buyer with a 0% facility. That is now a unit
test, not a claim: `profile.test.ts` asserts the cash-rich Como profile resolves
to `patient-opportunistic` (urgency < 40) and the renting first-home Bayswater
profile to `act-now` (urgency >= 65), and that flipping the 0% facility to 7%
raises urgency. 23 deterministic checks cover the WA guard, budget monotonicity,
the timing contrast, anchor-dependent ranking, and weight normalisation.

**Testing lesson carried forward.** Parity (TS == Python) only covers the
buyer-agnostic engine. This layer is new and TS-only, so it gets its own
self-contained unit suite rather than a golden file. The gate now runs both:
`test:engine = parity + profile`, wired into `tests/run.sh` step 5 so no dynamic
feature can regress unnoticed - which is the standing rule for this repo.

---

## How to run it

```bash
cd mcp
npm install
npm run typecheck   # tsc --noEmit
npm run parity      # TS engine vs Python model, 179 checks
npm run profile     # dynamic profile-layer unit tests, 23 checks
npm run demo        # see two buyers get different budgets, timing and rankings
npm test            # typecheck + parity + profile (this is what the deploy gate runs)
```

---

## Phase 2: the MCP server (built, in `server/`)

The engine was transport-agnostic on purpose. Phase 2 wraps it as a real
Model Context Protocol server and deploys it to Vercel. Layout:

```
server/
  app/api/[transport]/route.ts   the MCP handler: one tool per engine function
  app/page.tsx                   a landing page documenting the endpoint + tools
  lib/schema.ts                  zod schemas (the tool contract; mirror types.ts)
  lib/auth.ts                    bearer-token gate (open if no token set)
  lib/listings-live.ts           TS port of fetch_listings.py (RapidAPI)
  lib/engine/  +  data/          VENDORED copies of mcp/src and data/ (generated)
  scripts/sync-engine.mjs        regenerates the vendored copies from canonical
```

**The shape:** `AI client -> POST /api/mcp -> mcp-handler -> zod tool schemas
-> ENGINE`. The handler is created with `createMcpHandler` over **Streamable
HTTP**, **stateless** (no Redis), so it runs on a single Vercel serverless
function. The route file is `[transport]/route.ts` with `basePath: "/api"`, so
the endpoint is `POST /api/mcp`.

**The eleven tools** (one per engine capability): `estimate_price`,
`assess_property`, `forecast`, `score_suburb`, `rank_suburbs`, `list_suburbs`,
`onboarding_questions`, `resolve_profile`, `rank_suburbs_for_profile`,
`match_listings`, `search_listings`. Each input schema is a zod object in
`lib/schema.ts` that mirrors the engine's `types.ts` - the same types that gave
us the parity-tested engine now define what a client sees.

### Three problems Phase 2 had to solve (the genuinely instructive bits)

1. **Data loading that survives bundling.** The Phase 1 engine read its JSON with
   `readFileSync(join(here, "..", "..", "data", name))`. A serverless bundler
   cannot SEE a computed path, so those files would not ship and the function
   would `ENOENT` at runtime. Fix: switch `data.ts` to **static JSON imports**
   (`import suburbs from "../../data/suburbs.json"`). A bundler can follow a
   static import and include the file; tsx and Next both resolve them natively;
   and the relative path lines up in both trees (repo `data/` from `mcp/src`,
   `server/data/` from the vendored copy). Parity stayed 179/179 - same parsed
   data, different loader.

2. **A self-contained deploy without abandoning single-source-of-truth.** Vercel
   wants one root directory with everything inside it; our engine and data live
   elsewhere in the repo. Rather than import across directories (fragile) or
   copy by hand (drifts), `sync-engine.mjs` **vendors** `mcp/src -> lib/engine`
   and `data -> data` verbatim, runs on `prebuild`, and the deploy gate fails if
   the committed copies drift. Same pattern the HTML already uses for its inline
   data: a generated copy plus a gate that enforces equality.

3. **`.js` specifiers through webpack.** The engine uses NodeNext-style imports
   (`import "./util.js"` meaning `util.ts`). tsx handles that; webpack needs
   `resolve.extensionAlias = { ".js": [".ts", ...] }` in `next.config.mjs`. One
   line, but the build fails cryptically without it.

**Auth and secrets.** A small wrapper checks `Authorization: Bearer <token>`
against `MCP_BEARER_TOKEN`; if the var is unset the endpoint is open, so a fresh
deploy works before the secret is wired. `RAPIDAPI_KEY` powers the live-listings
tool; with no key it returns the committed sample.

**Verified before deploy:** `next build` green; a local `npm start` answered
`initialize`, `tools/list` (all 11), `estimate_price` (Shelley 720sqm = $1.075M,
matching the engine), `rank_suburbs_for_profile` (patient-opportunistic, $2.32M
ceiling, Shelley #1) and the WA guard (`anchor: "Sydney"` -> a clean error).

---

## How to talk about this (interview cheat-sheet)

- "MCP exposes app logic as **typed tools** an AI client calls over a standard
  protocol. The skill is **clean tool design + a trustworthy engine**, not the
  transport."
- "I separated the **engine** from the **server**. The engine is a typed TS
  library with a **cross-language golden test** proving it matches the original
  Python model to the dollar."
- "I hit a real **round-half-even vs round-half-up** parity bug and fixed it by
  matching IEEE-754 exact-halfway semantics - caught only because I had the
  golden test."
- "Phase 2 is a Vercel-hosted **Streamable-HTTP** MCP server: one tool per engine
  function, schemas derived from the types, bearer-token auth, secrets as env
  vars. Stateless, so no Redis needed."
- "Hosting an engine serverless surfaces real bundling constraints: I moved data
  loading from `readFileSync` (invisible to the file tracer) to **static JSON
  imports** so the data actually ships, and **vendored** the engine into the
  deploy root with a sync script the gate enforces - keeping one source of truth
  while staying self-contained."
- "I verified the server end to end before deploying - `initialize`, `tools/list`
  and real tool calls against a local build - not just that it compiled."
