# Como-Anchored Perth Home Model

A scenario-based house-price model and suburb-targeting tool for one specific
buyer: a **family home within reach of Como (6152)**, a **~$1.0M budget** with
low holding costs, patient enough to wait for the 2027 soft patch.

This repo contains the model, the data, the reproducible Python, an interactive
web tool, and a skills folder that lets an AI assistant (Claude) extend the work.

---

## What's in here

```
perth-property-model/
├── README.md            ← you are here (start here)
├── CLAUDE.md            ← single source of truth: buyer, macro, model, rules
├── index.html           ← site front page for GitHub Pages (copy of web/index.html)
├── web/
│   └── index.html       ← the interactive tool (open this in a browser)
├── model/
│   ├── scenario_model.py   ← regenerates the forecast baseline, self-verifies
│   └── scoring.py          ← suburb Buyer-Fit ranking
├── data/
│   ├── baseline.json       ← the forecast outputs = the "Reset" contract
│   ├── suburbs.json        ← suburb dataset + dimension scores
│   ├── perth_ring.json     ← the 143-suburb inner-Perth search ring (N/E/S/W)
│   └── criteria.json       ← the ten criteria + weights
└── .claude/skills/wa-property-expert/
    ├── SKILL.md            ← how the AI should think about WA property
    └── references/         ← methodology, data sources, suburb playbook, variables
```

---

## Open the tool (no install)

Just open `web/index.html` in any modern browser. It's a single self-contained
file - no server, no build step, no dependencies. It works offline.

What it does:
- **Forecast** - a fan chart of bear / base / bull scenarios with a
  probability-weighted expected path. Drag the three scenario weights; they
  rebalance to 100% and the chart redraws. **Reset to baseline** restores the
  model's own 30 / 50 / 20 view.
- **Where to buy** - every suburb scored 0-100 against the ten criteria,
  anchored on Como, shown as a heat map and a live ranking. The
  **proximity-vs-schools slider** reorders everything: drag it toward Como and
  the close suburbs (Wilson, St James) rise; drag it toward schools and the
  Rossmoyne-catchment suburbs (Shelley, Riverton) rise.
- **The ten criteria** and **live saved-search links** to the property portals.

---

## Reproduce the model (Python, no dependencies)

The forecast isn't a black box - the Python regenerates the exact numbers the
web tool shows, and checks itself:

```bash
cd model
python3 scenario_model.py     # prints the timeline and verifies it matches baseline.json -> PASS
python3 scoring.py            # prints the Buyer-Fit suburb ranking
```

Both use only the Python standard library. If you change an assumption, change
it in the data/engine and re-run - don't hand-edit outputs.

---

## Publish it as a live URL (GitHub Pages, ~3 minutes)

So you can send a link instead of a file:

```bash
# from the repo root, one time
git init
git add .
git commit -m "Perth home model"

# create an empty repo on github.com first, then:
git remote add origin https://github.com/<your-username>/perth-home-model.git
git branch -M main
git push -u origin main
```

Then on github.com: **Settings → Pages → Source: Deploy from a branch →
Branch: main → folder: /(root) → Save.**

Pages serves from the repo root, so make the tool the site's front page by
copying it up:

```bash
cp web/index.html index.html
git add index.html && git commit -m "Serve tool at site root" && git push
```

Your live URL will be:
`https://<your-username>.github.io/perth-home-model/`

Share that with anyone. (If you'd rather keep the tool at `/web`, the URL is
just `.../perth-home-model/web/` instead.)

This repo also ships a `.github/workflows/pages.yml` that deploys the site
automatically on every push - so once Pages is enabled for the repo, you never
have to touch the settings again.

---

## The live property feed: how it works

The "Properties that fit (or are a bargain)" section reads `data/listings.json`,
refreshed every day by a scheduled GitHub Action.

**What it searches.** Not just your shortlist. Every residential suburb within
**15km of the Perth CBD**, north, east, south and west: 143 suburbs, listed in
`data/perth_ring.json`. The brief is unchanged (houses, 3+ beds, up to $1.1M,
land favoured); what changed is the map, so a bargain two suburbs outside the
shortlist is no longer invisible.

**What "bargain" means here.** No free public source gives a reliable house
median for 143 suburbs, and inventing one would be worse than useless. So each
listing is priced against **the other comparable houses on the market in its own
suburb right now**: the median ask of that pool, adjusted for how the property
differs on land, bedrooms and bathrooms. A "12% under local asking" figure means
exactly that, and nothing more. It is not a valuation, not a suburb median, and
not a forecast. The logic lives in `model/value.py`, with its reasoning in the
file's docstring.

**What it refuses to call cheap:**

| Case | What happens |
|---|---|
| No published price ("Contact agent") | Never flagged as a bargain. Unknown is not cheap. |
| "From $850,000" | Treated as a floor, not an ask, and compared at a modest uplift. |
| A strata lot ("2/94 Wendouree Rd") | Dropped. A duplex half is cheap for an obvious reason. |
| No land size published | Confidence capped at low, and it scores part marks on land, never full. |
| Fewer than 3 comparables | Falls back to the wider side of the city, at low confidence. |
| A gap over 45% | Flagged as odd pricing and pushed down the ranking, not celebrated. |

**Filtering.** A compass row splits the feed by side of the city, decided by
which bank of the Swan a suburb sits on rather than a bearing from the CBD (so
Victoria Park and Kenwick read south, and Dalkeith reads west). A suburb picker
lists every suburb in the feed, grouped under its direction. If a sweep stops
early on API limits, the page says which sides it never reached, so a direction
showing zero is never mistaken for a direction with no bargains.

**Ranking.** "Best bargains" is 60% discount and 40% fit to the brief (land,
bedrooms, budget, distance from Como), scaled by how much evidence sat behind
the discount. So a cheap house that does not suit the family does not top the
list. Every side of the city is guaranteed a slot, so a quiet week in the north
cannot hand the whole page to the south.

### Turning the feed on

The feed uses the **Realty in AU API** via RapidAPI (a third-party surface for
realestate.com.au data, chosen for this private tool; it is not an official REA
feed).

1. Get a RapidAPI key and subscribe to "Realty in AU".
2. In GitHub: **Settings -> Secrets and variables -> Actions -> New repository
   secret**, add `RAPIDAPI_KEY`.
3. **Actions** tab -> **Refresh live listings (weekly)** -> **Run workflow**.
   After that it runs automatically every Saturday morning Perth time, ahead of
   the weekend home opens.

Without the key the job is a safe no-op: it leaves the committed data in
place, so the page never breaks.

**The sweep runs weekly.** One API call per suburb, so a full sweep of the ring
is 143 calls a run, about 613 a month. That is more than the RapidAPI BASIC plan
appears to allow: a single full sweep exhausted September 2026's quota and the
feed sat frozen for 25 days.

An over-quota sweep is no longer dangerous, though. It stops early, publishes
what it got balanced across north, east, south and west, rotates its starting
point so a different part of the ring is reached next week, and the page states
which sides were not searched. Coverage accumulates across the rolling 21-day
window rather than collapsing onto one direction. To fit a known quota exactly,
set `SUBURB_CAP` to the suburbs per run. Either way, check the cost first:

```bash
python3 scripts/fetch_listings.py --plan      # prints the exact call count
```

`SUBURB_CAP` sets the suburbs per run; the starting point rotates automatically off
the date, so there is no cursor to maintain. Raise it only alongside a bigger
plan, and keep the cycle inside `WINDOW_DAYS` (14) or listings will expire
before they are re-checked, which `python3 tests/test_rotation.py` will fail on.
To change the radius, rebuild the ring:
`python3 scripts/build_perth_ring.py 12`.

After changing anything in `model/value.py`, re-value the committed feed without
spending a single API call:

```bash
python3 scripts/fetch_listings.py --rescore
```

---

## Handing this to Claude Code

Open this folder in Claude Code and tell it what you want changed. It will read
`CLAUDE.md` first - that file carries the entire brief (buyer profile, the live
macro state, the four-layer model, the baseline contract, the suburb dataset,
the signal-vs-noise variable discipline, and the operating rules), so it starts
fully briefed rather than guessing. The `.claude/skills/` folder gives it the
deeper reference material on demand.

Good first jobs for Claude Code:
- Port `model/value.py` to TypeScript so the MCP server ranks bargains the same
  way the page does (it currently serves the committed feed, which is already
  Perth-wide, but its live per-request path still sweeps the shortlist only).
- Move to the official Domain Developer API if you ever want a licensed feed
  (see `CLAUDE.md` and `references/data-sources.md`).
- Refresh the macro block and re-run the model when new RBA / Cotality / iron-ore
  data lands.
- Swap the inline suburb data in `index.html` for a `fetch()` of the JSON files.

---

## Honest limits (read before relying on it)

- **General information only - not financial, legal or tax advice.**
- All figures are approximations as at **mid-2026** and will change.
- **Suburb medians vary 10-20% between sources** - they're shown as ranges, not
  precise values.
- **No public source publishes median block size**, so the **500sqm requirement
  must be confirmed per-listing via Landgate**.
- The forecast is a set of **scenario estimates conditioned on stated
  assumptions** - it will be wrong if those assumptions are wrong (a global
  shock, an iron-ore collapse below ~US$70, or a migration reversal are the
  things that break it).
- The web tool's listing links open **current** portal results, but the static
  page does **not** embed an auto-refreshing feed - that requires the Domain API
  upgrade path above. Anything claiming a static site live-scrapes the portals is
  breaching their terms.

Verify against live REIWA, Landgate, RBA and ABS data, and licensed
professionals, before acting.
