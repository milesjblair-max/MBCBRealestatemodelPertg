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

## How to run it

```bash
cd mcp
npm install
npm run typecheck   # tsc --noEmit
npm run parity      # TS engine vs Python model, 179 checks
npm run demo        # see the engine produce an estimate, ranking, forecast
npm test            # typecheck + parity (this is what the deploy gate runs)
```

---

## What Phase 2 (the actual MCP server) will add

This engine is transport-agnostic on purpose. Phase 2 wraps it:

- `app/api/mcp/route.ts` using `@modelcontextprotocol/sdk` + the `mcp-handler`
  adapter, over **Streamable HTTP** (stateless, so it runs on Vercel serverless
  with no Redis).
- One MCP `tool` per engine function: `estimate_price`, `score_suburb`,
  `rank_suburbs`, `forecast`, `assess_property`, `search_listings`. Each tool's
  input schema comes straight from the types in `src/types.ts`.
- A bearer-token check on the route, `RAPIDAPI_KEY` as a Vercel env var for the
  live listings tool, and deploy via Git-connect to Vercel.

Because the engine is already typed and parity-tested, Phase 2 is mostly
plumbing: schema -> call engine -> return. The hard correctness work is done.

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
