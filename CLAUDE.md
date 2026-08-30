# CLAUDE.md - Como-Anchored Perth Home Model

**This file is the single source of truth.** Read it fully before doing anything
in this repo. It carries the buyer, the live macro state, the four-layer model,
the baseline contract, the suburb dataset, the variable discipline, and the
operating rules. The `.claude/skills/wa-property-expert/` folder holds the
deeper reference material; load it on demand.

If you change a number that appears in more than one place, change it
**everywhere** and re-run `model/scenario_model.py` until it prints `PASS`.

---

## 0. What this project is

A scenario-based house-price model and suburb-targeting tool built for **one
specific buyer**, not a general audience. Everything is anchored to that buyer.
The deliverable is an interactive, shareable web tool (`web/index.html`, served
at the repo root as `index.html`) backed by a reproducible Python model
(`model/`) and a committed data contract (`data/`).

The audience for the live tool is the buyer **and his fiancée and a friend** -
non-analysts. It must be instantly legible: what the market is doing, what it
might do, where to buy, and why. No jargon without a plain-English gloss.

---

## 1. The buyer (the anchor - never drift from this)

| Attribute | Value |
|---|---|
| Goal | Family home, long hold, room to grow |
| Budget band | **$800k-$1.1M** |
| Capital | **$1.0M total** = patient capital, low holding cost |
| Anchor location | **Como 6152** (his family is in the South Perth / Como area) |
| Horizon | **3 years primary, 5-year scenario tail** |
| Posture | **Patient / opportunistic** - low holding costs remove the penalty for waiting |

**The ten criteria** (verbatim from the buyer; `data/criteria.json` is the
machine copy):

1. Land size above **500sqm** - *hard filter*
2. Property between **$800k-$1.1M** - *hard filter*
3. **$1.0M to bring** (low holding costs) - *context, not a filter*
4. **Growth potential (post-dip)** - *weighted 25%*
5. **Family area** - *weighted 15%*
6. **Backyard for the kids** - *weighted 15%*
7. **More than 3 bedrooms** (4+) - *hard filter; a KDR can satisfy it*
8. **Modern, but old is fine if knock-down-rebuild viable** - *weighted 10%*
9. **Near family in South Perth / Como** - *weighted 20%*
10. **Decent suburb, good postcode** - *weighted 15%*

The single most important consequence of criterion 3: **patience is almost free.**
The model's job is therefore not to call a crash but to find the **soft patch**
and the suburbs that hold up best through it and re-accelerate after.

---

## 2. Live macro state (as at mid-2026 - refresh before relying on it)

Verified mid-2026 (sources in `references/data-sources.md`):

| Indicator | Value | Note |
|---|---|---|
| RBA cash rate | **4.35%** | Held 17 Jun 2026 after Feb/Mar/May 2026 hikes; hawkish bias retained |
| Perth median dwelling | **~$1.05M** | +25.8% YoY but monthly growth decelerating |
| Advertised stock | **~40% below** 5-yr avg | Core of the undersupply thesis |
| Rental vacancy | **~0.5-0.7%** | Extremely tight (source-dependent) |
| Days on market | **~9** | Vendor's market, for now |
| CPI | **~4.0%** | Above target - keeps the RBA cautious |
| Iron ore | **~US$100/t**, softening | ~US$95/t 2026 consensus; **Simandou ramp bearish into 2027** |
| WA population growth | **~2.2%/yr** | Fastest state; demand-side floor |
| NG / CGT change | **From 1 Jul 2027** | Established-dwelling negative gearing limited; 50% CGT discount replaced by indexation + 30% min tax. **Owner-occupier buyer: direct impact nil; effect is a softer market = entry opportunity.** Pre-12-May-2026 holdings grandfathered; **new builds keep full concessions** (tilts demand toward family owner-occupier suburbs). |

**Why this isn't 2014-2020.** That downturn (~-14% houses) was oversupply +
population exodus (vacancy ~5%, migration collapse). Today is the inverse:
vacancy <1%, strong migration, undersupply. So a multi-year crash is unlikely -
but a **resources-led soft patch** (iron ore + Simandou + reduced investor
demand from NG/CGT) is the real risk, and it lines up with the buyer's 2027-28
window. That is the opportunity, not a catastrophe.

---

## 3. The model - four layers

A hybrid, because no single method wins at a single-city, suburb-level, ≤5-year
horizon. (Full rationale: `references/methodology.md`.)

| Layer | Method | Lives in | Role |
|---|---|---|---|
| 1 | **City VECM / error-correction spine** | calibrates `ANCHORS` | Anchors price to fundamentals (income, rents, build costs, real cash rate); judges over/under-valuation; sets the scenario anchor paths |
| 2 | **Scenario-weighted Monte Carlo** | `model/scenario_model.py` | The 50/30/20 base/bear/bull fan chart + expected path |
| 3 | **Suburb gradient-boosted panel** | `model/scoring.py` + `data/suburbs.json` | Relative suburb performance → the 0-100 Buyer-Fit score and heat map |
| 4 | **Hedonic property adjustment** | `model/avm.py`, `model/value.py` | Land size, beds, KDR optionality - applied at the individual property. `avm.py` estimates a range from the researched median (shortlist suburbs); `value.py` prices any listing in the ring against its own suburb's current asking market and owns the bargain flag |

**Horizon decision: 3 years primary, 5-year tail.** Forecast error compounds and
rate/policy uncertainty beyond 3 years is large; the buyer asked for ≤5; the
2027 soft patch sits inside 3. So the spine runs to **Mid-29** with the tail as
scenario commentary.

**Scenario weights: bear 30 / base 50 / bull 20.** Slightly more cautious than a
naive prior because of the Simandou ramp and the NG/CGT drag.

### The baseline contract (do not break)

`data/baseline.json` is **the contract**. The web tool's `BASELINE` object and
the Python's `ANCHORS` must produce **identical** numbers. The **Reset button**
in the tool restores exactly this. The rule:

> **Never hand-edit forecast outputs.** Change an assumption in `ANCHORS`
> (and the matching `BASELINE` in `web/index.html`), then run
> `python3 model/scenario_model.py` until it prints `PASS`.

`expected` = round-half-up to the nearest $1,000 of the weighted scenario
average. Headline numbers today: **Expected Mid-29 $1.17M**, **bear trough
$930k (-7%)**, **bull Mid-29 $1.40M**, **cost of waiting $210k**, expected 3yr
CAGR ~5.4%.

---

## 4. Variable discipline - standard, enriched, and signal-vs-noise

The model takes the **stock-standard** macro/suburb inputs and **enriches** them
with leading indicators most analysts ignore. Full catalogue with sources and
ingestion notes: `references/variables.md`. The discipline:

**Tier A - high-signal, genuinely leading (prioritise):**
- **Backyard pool-building-permit rate** per 100 dwellings (family-entrenchment index; LGA BA registers) - *leads medians 6-18 months; almost nobody uses it.*
- **School in-zone rejection events** - the moment a catchment (Rossmoyne/Willetton) starts refusing in-zone kids → premium spills into fringe suburbs (Shelley/Riverton/Bull Creek).
- **Childcare occupancy / waitlist density** (ACECQA national register) - young-family in-migration *before* they buy.
- **Subdivision / green-title pipeline: lodged-vs-registered cadastre ratio** (Landgate SLIP) - developer conviction 12-24 months ahead of completions.
- **Days-on-market velocity & vendor discounting** - turn before medians do.

**Tier B - useful, conditional or slower:**
- **FIFO-share × iron-ore interaction** (ATO postcode occupation × commodity price) - a suburb-level mining-cashflow beta for the 5-yr tail.
- **STRA register de-listing velocity** (WA short-stay register) - rental-supply relief, current.
- **Cafe / specialty-coffee density change** - gentrification nowcast.
- **Building-approval pipeline by suburb** - future supply that caps growth.
- **EV registrations per capita** - affluence/renovation propensity.

**Tier C - corroboration only (never a primary driver):**
- Google Trends suburb search interest; crime stats; tree canopy / urban heat; birth/household-formation rates by SA2 (slow but structurally predictive of family demand).

**The buyer's own hint - "child rates might affect the horizon" - is correct and
is operationalised** via childcare occupancy, pool permits, school-zone pressure
and SA2 family-cohort share. Treat demographic family-formation signals as real
but slow; treat permit/register/roster data as the genuinely leading tells.

---

## 5. The suburb shortlist (the buyer-facing answer)

Premium river suburbs (South Perth ~$2.0M, Applecross ~$2.4M, Mount Pleasant
~$2.1M, Como itself ~$1.5M+) are **out of budget for a house**. Best-fit targets:

- **Primary - Rossmoyne SHS catchment fringe:** **Shelley (~$960k)**, Riverton,
  Bull Creek, Bateman-adjacent. Scarce land + school demand + grandfathered
  owner-occupier status = highest-conviction growth-after-dip hold.
- **Near-in value (City of Canning):** **Wilson, St James, Parkwood, Bentley** -
  sub-$1.0M houses on larger blocks, strong KDR economics, genuinely close to Como.
- **North-of-river land:** **Dianella, Bayswater, Embleton, Balcatta** - 500sqm+
  green-title blocks near $1.0M with KDR upside; the catch is distance from Como.

At the balanced setting the model ranks **Shelley #1, Wilson #2** - consistent
with the thesis. The proximity-vs-schools slider re-orders this live.

---

## 6. The interactive tool - what it must always do

`web/index.html` (mirrored to `/index.html` for Pages). Single self-contained
file, no build step, works offline. Four sections:

1. **Forecast** - bear/base/bull fan chart + weighted expected path; three weight
   sliders that rebalance to 100%; **Reset to baseline** (30/50/20).
2. **Where to buy** - every suburb scored 0-100, heat map + live ranking, with the
   **proximity-vs-schools slider** reordering everywhere.
3. **The ten criteria** - filters vs weighted, in full.
4. **Live listings** - the Perth-wide property feed (with a compass row to filter
   by side of the city) plus pre-filtered saved-search deep-links that always
   open *current* portal results.

**Hard rules for the tool:**
- The **Reset button must restore `BASELINE` exactly.** It is the contract.
- Keep it **a single file with inline data** unless explicitly asked to split -
  it has to work as an emailed file and on GitHub Pages with zero setup.
- **Never claim the static page live-scrapes** realestate.com.au / Domain /
  REIWA. It does not, and doing so breaches their terms. The honest framing
  (already in the tool) is: deep-links open current results; a genuinely
  embedded refreshing feed requires the **Domain Developer API + scheduled job**.

---

## 7. Listings & "live" data

The buyer wants live ads and property suggestions refreshed on a cadence.

**Scope (changed): the feed is Perth-wide, not shortlist-only.** It sweeps every
residential suburb within **15km of the Perth CBD**, north, east, south and
west: `data/perth_ring.json`, 143 suburbs, built by
`scripts/build_perth_ring.py` from the public-domain base layer. The buyer's
brief is unchanged (houses, 3+ beds, up to $1.1M, land favoured, Como anchor);
only the map widened, so a bargain outside the shortlist is no longer invisible.

**Bargains are measured against the local asking market, never an invented
median.** Only the 14 suburbs in `data/suburbs.json` have researched medians.
For the other 129, `model/value.py` prices each listing against the median ask
of comparable houses on the market in the same suburb right now, adjusted for
land, beds and baths. Say "under local asking", never "under the suburb median",
and never present it as a valuation. The guard rails are load-bearing and must
not be loosened without a reason recorded here: no published price is never
cheap; a "from" price is a floor, not an ask; strata lots are dropped; unknown
land caps confidence at low; under 3 comparables falls back to the sector; a gap
over 45% is flagged as odd, not celebrated. `python3 model/value.py` runs the
self-test that pins all of this.

**Owner decision (private tool):** the live Properties feed uses the
**Realty in AU API (apidojo, via RapidAPI)**, which surfaces realestate.com.au
listing data (with photos) through a third party. The owner has explicitly
accepted this for a private tool shared only with his partner, so the earlier
"no third-party REA data" rule is **relaxed for this repo only**. It is not an
official REA feed and is rate-limited, so:
- Keep the **saved-search deep-links** as the always-on, zero-infra fallback.
- The Realty in AU pull lives in `scripts/fetch_listings.py`, run by the
  **scheduled GitHub Action** into `data/listings.json`, which the tool
  `fetch()`es. Auth is a `RAPIDAPI_KEY` repo secret; with no key the script is a
  safe no-op and the committed sample shows.
- A full sweep is **one call per suburb: 143 a run, ~4,300 a month.** The owner
  chose the full daily sweep, which needs a paid RapidAPI plan. To spend less,
  set `SUBURB_CAP` and rotate `SUBURB_OFFSET` on the workflow step rather than
  shrinking the ring. `python3 scripts/fetch_listings.py --plan` prints the
  exact count; `--rescore` re-values the committed feed with zero API calls.
- The official **Domain Developer API** remains the clean upgrade path if the
  owner ever wants a licensed feed (its listings search is approval-gated/paid).

---

## 8. Operating rules for any AI working here

- **HOUSE STYLE - NO DASHES (hard rule).** Never use em dashes (`-`) or en dashes
  (`-`) anywhere - not in the tool, docs, data, commit messages, code comments or
  chat. Use a plain hyphen `-`, or restructure the sentence (comma, colon,
  parentheses, full stop). The buyer considers em/en dashes an AI tell and does
  not want them. Use `-` for numeric ranges too (`$920-980k`, not `$920-980k`).
  Before committing, grep for the em/en/minus characters and replace any with `-`.
- **DISCRETION ON PERSONAL FINANCES.** The page and zip are shared with friends
  and family. Do NOT state the buyer's capital structure explicitly (no "$200k
  equity", no "$800k line of credit", no "0% interest"). Refer only to a
  "~$1.0M budget" and "low holding costs / patience is cheap". The price band
  `$800k-$1.1M` (about the property) is fine to show.
- **Branch:** develop on `claude/repo-connection-mhn1nl`. Never push elsewhere
  without explicit permission. Commit with clear messages; push with
  `git push -u origin <branch>`.
- **Reproducibility:** after any model/data change, run `bash tests/run.sh` and
  get `ALL PASS`. That covers `model/scenario_model.py` (must print `PASS`),
  `model/scoring.py`, `model/avm.py`, `model/value.py`'s self-test, and a
  rebuild check on `data/perth_ring.json`. Stdlib only - never add a runtime
  dependency to the model or the tool.
- **Derived data stays derived.** `data/perth_ring.json` is built, not edited.
  Change `scripts/build_perth_ring.py` and rebuild; the gate fails if the
  committed file does not match a fresh build.
- **One source of truth per number.** `data/*.json` is canonical; the tool's
  inline copy must match. If you touch one, touch the other and verify.
- **Honesty over polish.** Medians are ranges (sources diverge 10-20%); no public
  source has median block size (500sqm confirmed per-listing via Landgate); all
  figures are mid-2026 approximations; forecasts are scenario estimates, not
  predictions. Keep the disclaimer intact.
- **Stay anchored to the buyer.** Como, $1.0M, family, 500sqm+, KDR-capable,
  patient. If a change would help a generic user but blur the buyer's answer,
  don't.
- **This is general information, not financial/legal/tax advice.** Preserve that
  framing in everything user-facing.

---

## 9. Good next jobs (when asked)

- Wire the **Domain API → scheduled Action → `data/listings.json` → `fetch()`** for a real refreshing feed.
- Add Tier-A enriched variables as live data layers (pool permits, childcare occupancy, lodged-cadastre ratio) - each as its own `data/*.json` with a fetch + a documented source.
- Refresh the macro block and re-run the model when new RBA / Cotality / iron-ore prints land.
- Add a "street-level" layer: highlight streets with original 500sqm+ green-title stock inside target catchments (Landgate cadastre + R-codes).
- Split the inline data out of `index.html` into `fetch()` calls once a build/refresh exists.
