# Como-Anchored Perth Home Model

A scenario-based house-price model and suburb-targeting tool for one specific
buyer: a **family home within reach of Como (6152)**, **$1.0M budget** ($200k
equity + $800k at 0% interest), patient enough to wait for the 2027 soft patch.

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
│   └── criteria.json       ← the ten criteria + weights
└── .claude/skills/wa-property-expert/
    ├── SKILL.md            ← how the AI should think about WA property
    └── references/         ← methodology, data sources, suburb playbook, variables
```

---

## Open the tool (no install)

Just open `web/index.html` in any modern browser. It's a single self-contained
file — no server, no build step, no dependencies. It works offline.

What it does:
- **Forecast** — a fan chart of bear / base / bull scenarios with a
  probability-weighted expected path. Drag the three scenario weights; they
  rebalance to 100% and the chart redraws. **Reset to baseline** restores the
  model's own 30 / 50 / 20 view.
- **Where to buy** — every suburb scored 0–100 against the ten criteria,
  anchored on Como, shown as a heat map and a live ranking. The
  **proximity-vs-schools slider** reorders everything: drag it toward Como and
  the close suburbs (Wilson, St James) rise; drag it toward schools and the
  Rossmoyne-catchment suburbs (Shelley, Riverton) rise.
- **The ten criteria** and **live saved-search links** to the property portals.

---

## Reproduce the model (Python, no dependencies)

The forecast isn't a black box — the Python regenerates the exact numbers the
web tool shows, and checks itself:

```bash
cd model
python3 scenario_model.py     # prints the timeline and verifies it matches baseline.json -> PASS
python3 scoring.py            # prints the Buyer-Fit suburb ranking
```

Both use only the Python standard library. If you change an assumption, change
it in the data/engine and re-run — don't hand-edit outputs.

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
automatically on every push — so once Pages is enabled for the repo, you never
have to touch the settings again.

---

## Handing this to Claude Code

Open this folder in Claude Code and tell it what you want changed. It will read
`CLAUDE.md` first — that file carries the entire brief (buyer profile, the live
macro state, the four-layer model, the baseline contract, the suburb dataset,
the signal-vs-noise variable discipline, and the operating rules), so it starts
fully briefed rather than guessing. The `.claude/skills/` folder gives it the
deeper reference material on demand.

Good first jobs for Claude Code:
- Wire the Domain Developer API into a scheduled GitHub Action to populate
  `data/listings.json` for a genuinely embedded, refreshing feed (see
  `CLAUDE.md` and `references/data-sources.md` for the compliant approach).
- Refresh the macro block and re-run the model when new RBA / Cotality / iron-ore
  data lands.
- Swap the inline suburb data in `index.html` for a `fetch()` of the JSON files.

---

## Honest limits (read before relying on it)

- **General information only — not financial, legal or tax advice.**
- All figures are approximations as at **mid-2026** and will change.
- **Suburb medians vary 10–20% between sources** — they're shown as ranges, not
  precise values.
- **No public source publishes median block size**, so the **450sqm requirement
  must be confirmed per-listing via Landgate**.
- The forecast is a set of **scenario estimates conditioned on stated
  assumptions** — it will be wrong if those assumptions are wrong (a global
  shock, an iron-ore collapse below ~US$70, or a migration reversal are the
  things that break it).
- The web tool's listing links open **current** portal results, but the static
  page does **not** embed an auto-refreshing feed — that requires the Domain API
  upgrade path above. Anything claiming a static site live-scrapes the portals is
  breaching their terms.

Verify against live REIWA, Landgate, RBA and ABS data, and licensed
professionals, before acting.
