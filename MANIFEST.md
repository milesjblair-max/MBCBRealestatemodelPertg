# WA Home Model - Project Manifest

*A design and intent document, written for an external technical reviewer. It
covers what this is, why it exists, how it was built, how it works, and the
honest record of what went wrong and got fixed along the way.*

*Note on figures: this document describes the engine's capabilities and the
market model, not the owner's personal finances. Budget is referred to only as a
"~$1.0M budget with low holding costs." The property price band ($800k-$1.1M) is
a property constraint, not a personal one.*

---

## 1. The origin: why this exists

This started as a personal problem, not a software project.

The buyer is looking for a **family home in Perth, Western Australia** - a long
hold, room for kids to grow, anchored near family in the **South Perth / Como**
area. The constraints were specific and personal:

- A budget band of **$800k-$1.1M** for the property.
- A **~$1.0M budget with low holding costs**, which is the single most important
  fact in the whole model: it means **patience is almost free**. There is no
  monthly penalty for waiting for the right moment or the right house.
- Ten concrete criteria (land above 500sqm, 4+ bedrooms or a knock-down-rebuild
  that gets there, a backyard, proximity to family, a good school catchment, a
  decent postcode, growth potential after any dip).
- A **3-year primary horizon** with a 5-year tail.

The market context at the time made this interesting rather than simple. Perth
in mid-2026 is a vendor's market (median ~$1.05M, stock ~40% below the five-year
average, rental vacancy under 1%, ~9 days on market). But there is a credible
**resources-led soft patch** on the horizon (iron ore softening, the Simandou
mine ramping into 2027, negative-gearing/CGT changes from mid-2027 cooling
investor demand). That soft patch lines up almost exactly with the buyer's
purchase window.

So the core insight that motivated the whole thing:

> The job is **not to call a crash**. It is to find the **soft patch** and the
> suburbs that hold up best through it and re-accelerate after - because for a
> patient buyer with low holding costs, timing the entry is the highest-leverage
> decision available.

That reframing - from "predict prices" to "find the window and the resilient
suburbs for *this specific buyer*" - is what made it tractable and what every
design decision since has served.

---

## 2. What it is today (the latest view)

Three things that share one brain:

1. **A reproducible price-and-suburb model** (`model/` in Python, mirrored
   exactly in `mcp/src/` in TypeScript). Four layers, parity-tested to the
   dollar across the two languages.

2. **An interactive, shareable web tool** (`index.html`) - a single
   self-contained file, no build step, works offline and over email, hosted on
   GitHub Pages. The non-technical front door for the buyer, his fiancee, and a
   friend.

3. **A Model Context Protocol (MCP) server** (`server/`, deployed on Vercel) -
   the same engine exposed as typed tools so it can be driven conversationally
   from inside Claude. This is the newest and most ambitious layer: it turns a
   fixed single-buyer model into a **dynamic, profile-driven, statewide**
   advisor that any household can point at any WA location.

The evolution in one line: **a single-buyer spreadsheet-replacement became a
general WA home-buying engine you can talk to.**

---

## 3. Functional design - what it does for a user

### 3.1 The four questions it answers

1. **What is the market going to do?** A bear/base/bull scenario fan to mid-2029
   with a weighted expected path. Headline today: expected mid-29 ~$1.17M, a
   bear trough around $930k (-7%), a bull case ~$1.40M, and an expected 3-year
   CAGR of ~5.4%. The "cost of waiting" is surfaced explicitly (~$210k expected),
   which for a patient buyer is the number that actually matters.

2. **Where should I buy?** Every suburb scored 0-100 for *this* buyer, as a heat
   map and a live ranking. A proximity-vs-schools slider re-orders everything in
   real time. At the balanced setting the curated model ranks Shelley #1,
   Wilson #2 - consistent with the underlying thesis (scarce land inside the
   Rossmoyne school catchment, grandfathered owner-occupier status).

3. **Does this specific house stack up?** A hedonic price estimate plus a
   buyer-fit read (pros and cons) for an individual listing.

4. **What is actually for sale right now?** Live listings with photos, filtered
   to the buyer's criteria, refreshed on a daily cadence.

### 3.2 The dynamic, profile-driven layer (the big shift)

The original model was hard-wired to one buyer anchored on Como. The current
system takes a **profile** - region, anchor suburb, income, deposit/cash, any
borrowed funds, life stage, weighted criteria, hard filters - and resolves it
into:

- a **budget band** (floor / ceiling / borrowing capacity), where genuine cash
  and **borrowed funds are modelled differently**: borrowed money still helps
  cover the price but carries a monthly servicing cost that reduces borrowing
  capacity, while interest-free funds do not. (So a buyer with a small deposit
  and one with cash-plus-an-interest-free-facility do **not** get the same
  budget - which was a specific, deliberate requirement.)
- a **buy-timing posture** (act-now / balanced / patient-opportunistic) with the
  reasoning.
- an **affordability read**: can you actually reach your own anchor suburb, and
  if not, by how much (computed from the suburb's median-low, not guessed).
- a **ranked shortlist** with the count of genuinely viable suburbs.

Every input moves the output. That was the explicit design mandate: *no input
should be decorative.*

### 3.3 Anchor anywhere in WA

The model originally knew **14 curated middle-ring Perth suburbs**. It now sits
on a **statewide base layer of ~1,800 WA suburbs** (precise per-suburb
coordinates, ABS SA2 names). You can anchor on Mandurah, Albany, Geraldton -
anywhere - and get the real nearest suburbs and, where listings exist,
fit-ranked areas with live prices.

This created an honest **two-tier coverage** model that the tool states plainly:

- **Tier 1 (the 14 curated suburbs):** full fit-scoring on every criterion -
  budget, proximity, land, schools, growth, family, knock-down-rebuild economics.
- **Tier 2 (all ~1,800 WA suburbs):** anchor anywhere; scored on proximity +
  land + budget against **live listing prices**. Schools / growth / family are
  not yet scored off-panel (that is the next data layer, and the tool says so
  rather than pretending).

### 3.4 The conversational surface (MCP)

Thirteen tools and four guided prompts. The tools, grouped by job:

**Orientation**
- `capabilities` - what this is, the two-tier coverage, how to start.
- `onboarding_questions` - the questions to ask a new buyer.

**The forecast**
- `forecast` - bear/base/bull fan + headline metrics.

**Profile and suburbs**
- `resolve_profile` - profile to budget band, timing, weights, affordability.
- `rank_suburbs_for_profile` - rank the curated set for this buyer.
- `list_suburbs` - the curated dataset with medians and in-band flags.
- `nearby_suburbs` - locate the nearest real suburbs to ANY WA anchor.
- `recommend_areas` - the anchor-anywhere recommender: any WA anchor + profile
  to fit-ranked nearby suburbs with live prices.

**Individual property**
- `estimate_price` - likely price + range for a specific house.
- `assess_property` - estimate plus a buyer-fit read.

**Listings**
- `match_listings` - match listings to a profile's filters, ranked by fit, with
  a live, null-safe "meets your criteria" verdict.
- `search_listings` - browse the curated in-budget suburbs (raw feed).
- `find_listings` - individual live houses for ANY WA suburb with hard
  land/beds/price filters (e.g. "Mandurah houses over 700sqm").

**Guided prompts** (form-driven front doors): `find_a_home`, `see_listings`,
`estimate_a_listing`, `about_this_tool`.

The MCP also returns a server-rendered **dashboard URL** for any profile, so the
result can be opened as a real web page (inline SVG fan chart, metric cards,
suburb heat table) rather than depending on the chat client to render charts.

---

## 4. Technical design

### 4.1 The four-layer model (the intellectual core)

No single forecasting method wins at a single-city, suburb-level, sub-5-year
horizon, so the model is a deliberate hybrid:

| Layer | Method | Role |
|---|---|---|
| 1 | City VECM / error-correction spine | Anchors price to fundamentals (income, rents, build costs, real cash rate); sets the scenario anchor paths. |
| 2 | Scenario-weighted Monte Carlo | The 50/30/20 base/bear/bull fan and the expected path. |
| 3 | Suburb gradient-boosted panel | Relative suburb performance, producing the 0-100 buyer-fit score and heat map. |
| 4 | Hedonic property adjustment | Land size, beds, knock-down-rebuild optionality, applied per listing. |

Scenario weights are **bear 30 / base 50 / bull 20** - slightly more cautious
than a naive prior, because of the Simandou ramp and the negative-gearing/CGT
drag. The horizon runs to **mid-2029** with the 5-year tail as commentary.

### 4.2 The contract: one source of truth per number

`data/baseline.json` is the binding contract. The web tool's inline `BASELINE`
object and the Python's `ANCHORS` must produce **identical** numbers, and the
web tool's "Reset" button restores exactly this. The hard rule: **never
hand-edit a forecast output** - change an assumption and re-run the model until
it prints `PASS`. A pre-deploy gate enforces it.

### 4.3 Cross-language parity (the quality backbone)

The model exists twice: Python (`model/`) as the reference, and TypeScript
(`mcp/src/`) as the engine the live tools call. A **parity test** runs **179
cases** asserting the TypeScript output matches the Python output **to the
dollar** (including a subtle banker's-vs-half-up rounding reconciliation). This
is what lets the MCP server inherit the model's correctness rather than
re-deriving it: the conversational layer is "schema -> call engine -> return,"
and the engine is the parity-tested code.

### 4.4 The stack

- **Web tool:** a single self-contained `index.html` with inline data and inline
  SVG/Canvas charts. No build step, no dependencies, works offline. This is a
  hard constraint - it has to survive being emailed and opened on a phone.
- **Engine:** TypeScript, standard-library only, no runtime dependencies.
- **MCP server:** Next.js 15 (App Router), `mcp-handler` over Streamable HTTP,
  the official MCP SDK, and `zod` for typed tool contracts. Deployed on Vercel
  with **Fluid Compute** enabled and a 300s max duration so a streaming tool turn
  with several live-listing fetches is never cut off.
- **Auth:** a bearer token gates the MCP endpoint.

### 4.5 Engine vendoring and the drift gate

The canonical engine lives in `mcp/src` and the canonical data in `data/`. A
sync script (`server/scripts/sync-engine.mjs`) vendors copies into
`server/lib/engine` and `server/data` at build time, and also publishes the web
tool to `server/public/tool.html`. The pre-deploy gate fails the build if the
vendored copies drift from the canonical source - so the single-source-of-truth
rule is **enforced, not hoped for**.

### 4.6 Data sources (all free or owner-accepted)

- **Statewide base layer:** the public-domain `matthewproctor/australianpostcodes`
  dataset - per-suburb precise coordinates and ABS SA2 names, 1,804 WA suburbs.
- **Live listings:** the "Realty in AU" API (apidojo, via RapidAPI), which
  surfaces realestate.com.au listing data with photos. The owner explicitly
  accepted this third-party feed for a private tool shared only with family. It
  is rate-limited, so the design keeps calls modest (cap suburbs, once daily) and
  always falls back to a committed sample when the key is absent.
- **Saved-search deep-links** are the always-on, zero-infrastructure fallback:
  they open current portal results without claiming to scrape them.
- Medians, school/growth/demographic layers are sourced (or are sourceable for
  free) from Landgate, REIWA/CoreLogic, ABS Census, and ACARA - documented in
  `references/`.

### 4.7 Listings pipeline

A scheduled GitHub Action runs `scripts/fetch_listings.py` daily into
`data/listings.json`, which the tool `fetch()`es. With no API key, it is a safe
no-op leaving the committed data in place.

**Scope: the inner-Perth ring, not the shortlist.** The sweep covers every
residential suburb within 15km of the Perth CBD in all four directions, listed
in `data/perth_ring.json` (143 suburbs, built by
`scripts/build_perth_ring.py` from `data/wa_suburbs.json`, with postal-delivery
rows filtered out and each drop recorded in the file's meta). One API call per
suburb, so a full sweep is 143 calls; `--plan` prints the count and
`SUBURB_CAP` / `SUBURB_OFFSET` support a rotating sweep on a smaller quota.

**Valuation: `model/value.py`.** Only 14 suburbs carry researched medians, so
every listing is instead priced against the median ask of comparable houses on
the market in its own suburb, hedonically adjusted for land, beds and baths
(coefficients imported from `avm.py`, so there is one source of truth). It
publishes a fair value, a discount, a confidence, a buyer-fit and a rank per
listing, and it is deliberately conservative about what it will call a bargain:
no published price, a "from" price, a strata lot, unknown land, thin
comparables and implausible gaps are each handled explicitly. `python3
model/value.py` runs a 15-check self-test over exactly those cases.

The MCP server has a TypeScript port of the older fetch
(`server/lib/listings-live.ts`) that pulls live per request; it serves the
Perth-wide committed feed, but its own live path still sweeps the curated
shortlist and does not yet run the value engine. The live path logs `api-rows`
vs `kept` per suburb so the runtime logs are diagnosable.

### 4.8 Testing surface

- Engine (TypeScript == Python): **parity 179**, profile 34, base layer 18,
  match-listings 11.
- Server: links 15, dashboard 14, area-recommend 19, find-listings 9.
- Web: a headless-browser regression suite, 53 checks.
- Value engine: `model/value.py` self-test, 15 checks.
- A single pre-deploy gate (`tests/run.sh`) runs the Python model, the web
  regression, the sync/drift check, both test suites, and a house-style lint -
  and prints `ALL PASS` or refuses to deploy.

---

## 5. How we got here - the evolution

1. **The single-buyer model.** A Python scenario model and a self-contained HTML
   tool, hard-wired to the Como-anchored buyer and 14 curated suburbs. Honest,
   reproducible, shareable.

2. **Phase 1 - the engine.** The Python model was extracted into a typed
   TypeScript library with cross-language parity tests. This was the
   foundation: prove the two languages agree to the dollar, then everything
   built on top inherits that correctness.

3. **Phase 2 - the MCP server.** The engine exposed as MCP tools on Vercel, so
   the model could be driven conversationally. Added guided prompts, a
   server-rendered dashboard, and visible scope.

4. **The multi-user pivot.** The breakthrough request: *every input should alter
   the output.* The model was generalised from one fixed buyer to a
   profile-driven engine - budget that distinguishes cash from borrowed funds,
   life-stage criteria presets, dynamic weights, an affordability read.

5. **M1 - statewide base layer.** The 14-suburb ceiling was removed. A
   public-domain dataset gave ~1,800 WA suburbs with real coordinates, so you can
   anchor anywhere (Mandurah, Albany), not just the curated metro set.

6. **M2 - anchor-anywhere recommendations.** `recommend_areas`: any WA anchor +
   profile to fit-ranked nearby suburbs, with budget gated on **real live listing
   prices** rather than invented numbers.

7. **The rename.** "Como home model" became **WA Home Model** - the product is no
   longer about one suburb, even though Como remains a valid anchor.

8. **Hardening from live use.** Driving the live tool surfaced a cluster of
   real defects (below) that were fixed at the source, logged, and regression-
   tested. The most recent addition, `find_listings`, closed the last gap:
   individual live listings for any off-metro suburb with hard filters, so the
   assistant never has to fall back to scraping property portals.

---

## 6. Insights worth your friend's attention

### 6.1 Product / market insights

- **For a patient, low-holding-cost buyer, the entry-timing decision dominates.**
  The model is built around finding the soft patch, not predicting a crash.
- **This is not 2014-2020.** That Perth downturn was oversupply plus a population
  exodus. Today is the inverse - sub-1% vacancy, strong migration, undersupply -
  so a multi-year crash is unlikely, but a resources-led soft patch is the real
  (and useful) risk.
- **The high-signal variables are the unglamorous ones.** The model deliberately
  enriches standard inputs with leading indicators most analysts ignore:
  backyard pool-building-permit rates (a family-entrenchment index that leads
  medians 6-18 months), school in-zone rejection events, childcare
  occupancy/waitlists, the lodged-vs-registered subdivision ratio, and
  days-on-market velocity. The buyer's own hunch - that child/family-formation
  rates affect the horizon - is correct and is operationalised.

### 6.2 Engineering insights

- **Parity testing as the trust anchor.** Two implementations that must agree to
  the dollar is a strong, cheap correctness guarantee, and it is what made it
  safe to put the model behind a conversational interface.
- **One source of truth, enforced by a gate.** Numbers live in `data/*.json`;
  every other copy is generated or checked. Drift fails the build.
- **Honest degradation everywhere.** No API key, no listings, an off-panel
  suburb - every path has a defined, truthful fallback rather than a guess or a
  crash.

### 6.3 The most important insight: tests proved numbers, review proved honesty

The golden tests verified that the **numbers were correct**. They could not
verify that the **claims were honest** or that the **tool was hard to misuse**.
Almost every serious defect was caught by the buyer *using* the live tool, not
by the test suite. That gap - correctness vs honesty-and-ergonomics - is the
single most transferable lesson in this project, and it is why there is a
standing rule to surface limitations plainly rather than let a confident-looking
answer paper over them.

---

## 7. The defect record (caught in review, and how)

These are logged deliberately in `CHANGELOG.md`. They were found by the buyer in
review, because the tests asserted that numbers were right, not that claims were
honest. A representative selection:

- **Overclaimed coverage** - the tool implied it ranked "every suburb" when it
  knew 14. Fixed with honest two-tier wording, the statewide base layer, and an
  overclaim lint.
- **Stale-answer footgun** - legacy fixed-Como scoring tools sat next to the
  dynamic ones and returned stale answers after re-anchoring. Removed; one
  ranking path now.
- **Improvised affordability gap** - the dashboard once guessed the gap to the
  anchor (~$163k) when the real figure was far larger. The engine now computes
  it from the suburb median-low and the prompt uses it verbatim.
- **The "meets criteria" flag was a baked lie** - a listing with no published
  land size was marked as meeting a 700sqm rule, and the flag ignored bedrooms.
  Now computed live from the actual profile filters, null-safe, with plain-English
  reasons; the same null-land bug was fixed in the Python fetch and the committed
  sample.
- **Off-panel anchor reported as "cannot be scored"** - Mandurah was sent down
  the curated-only path. Fixed with explicit anchor-routing to `recommend_areas`.
- **No way to get individual off-metro listings with a hard land filter** - the
  assistant fell back to scraping portals for "Mandurah houses over 700sqm." The
  engine had the data all along; `find_listings` now exposes it with honest
  reporting of how many listings were dropped for an unknown (not small) land
  size.
- **Honesty corrections on data availability** - claims that free median /
  school / demographic data did not exist were challenged by the buyer and
  corrected after research (Landgate, REIWA, ABS, ACARA all publish usable free
  data).

---

## 8. What is solid, and what is next

**Solid and verified:**
- The four-layer model and the baseline contract (Python model prints `PASS`).
- Cross-language parity to the dollar (179 cases).
- The MCP server, all 13 tools, the prompts, the server-rendered dashboard.
- The statewide base layer and anchor-anywhere recommendations.
- Live listings via RapidAPI, verified end-to-end in the runtime logs.

**Next (honestly pending):**
- Score schools / growth / family for arbitrary off-metro suburbs (ABS
  demographics + Landgate growth - both free, the data layer is the work).
- Wire the Tier-A enriched leading indicators (pool permits, childcare
  occupancy, the lodged-vs-registered cadastre ratio) as live data layers.
- An optional licensed feed (the Domain Developer API) as a clean upgrade path
  from the rate-limited RapidAPI source.

---

## 9. Standing principles (the rules the system holds itself to)

- **Stay anchored to the real buyer.** If a change helps a generic user but
  blurs this buyer's answer, it is not made.
- **Honesty over polish.** Medians are ranges; forecasts are scenario estimates,
  not predictions; limitations are stated, not hidden. This is general
  information, not financial, legal, or tax advice - and the tool says so.
- **Discretion on personal finances.** The shared tool refers only to a "~$1.0M
  budget" and "low holding costs," never the underlying capital structure.
- **Reproducibility.** Any model or data change re-runs the Python model (must
  print `PASS`) and the full gate before it ships.

*End of manifest.*
