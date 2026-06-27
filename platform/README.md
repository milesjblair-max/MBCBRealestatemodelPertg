# platform/ - productisation work (Phase 0)

This folder is the **development chain**, isolated from production. It lives on the
`develop` branch only and is never served by the live GitHub Pages site (which
deploys from `claude/repo-connection-mhn1nl`, the root `index.html`). You can see
everything here without any risk to what is live.

## The idea

Separate **what a user wants** (declarative config) from **how the market is
judged** (a computed engine):

```
profiles/<id>.json   user-owned PREFERENCES  (budget, criteria, weights, asset class)
        |  validated against
schema/profile.schema.json   the contract
        |  fed into
engine/   shared core + per-asset-class strategy (registry pattern)
        |  which DERIVES
engine/timing.py   the buy-timing call (weights + window), not hand-set
        |  written by
build.py   ->  dist/<id>/bundle.json   one self-contained bundle per profile
        |  fetched by
web/index.html   config-driven UI (a Phase-0 proof shell)
```

Adding a user or a whole asset class = adding a JSON file (and, for a new
vertical, one small strategy module). No core edits. That is the scalability seam.

## Run it

```bash
python3 platform/engine/validate_profile.py platform/profiles/como-residential.json
python3 platform/build.py                 # builds every profile bundle into dist/
# preview the config-driven UI (fetch needs http, not file://):
cd platform && python3 -m http.server 8099   # then open http://localhost:8099/
```

Switch the profile dropdown to watch the **same engine** produce a different
asset class, valuation basis and a **derived** timing call:
- **como-residential** -> 30/50/20, "soft patch" (the live model's baseline, now computed not hand-set)
- **perth-commercial** -> 17/50/33, "rising market" (cap-rate / NOI / WALE basis)

## What is here

| Path | Role |
|---|---|
| `schema/profile.schema.json` | The profile contract (source of truth for both sides later) |
| `profiles/*.json` | Per-user / per-vertical preferences (declarative) |
| `engine/validate_profile.py` | Stdlib validator (Phase 1 -> Pydantic v2 + Zod sharing this schema) |
| `engine/registry.py` | Strategy registry: `asset_class -> module` |
| `engine/assets/residential.py`, `commercial.py` | Per-vertical feature packs (valuation basis, inputs, signals) |
| `engine/timing.py` | Computes scenario weights + buy-window from valuation gap + leading signals |
| `build.py` | profile -> validate -> engine -> `dist/<id>/bundle.json` (+ `index.json` manifest) |
| `index.html` | Config-driven app: forecast, ranking, listings, two-tier switcher |
| `dist/` | Generated bundles (a scheduled Action would build + commit these) |

## Why this stays static-first

A scheduled GitHub Action runs `build.py` and commits the bundles; the page
`fetch()`es the active one (multi-tenant by config, zero backend). Graduate to a
backend (Cloudflare Pages + Workers, or Supabase) only when one of these appears:
**auth / private profiles or hidden API keys**, **write-back / persisted user
state**, or **real-time per-request compute**.

## House rules still apply

Stdlib only, no build step, no em/en dashes, discretion on personal finances.
See the repo `CLAUDE.md`.
