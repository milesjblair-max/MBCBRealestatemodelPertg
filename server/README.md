# WA Home Model - MCP server (Phase 2)

The Phase 1 engine, exposed as a **Model Context Protocol** server over
**Streamable HTTP**, deployable to **Vercel**. One MCP tool per engine function.

```
AI client  ->  POST /api/mcp  ->  mcp-handler  ->  tool schemas (zod)  ->  ENGINE
```

The engine is the reusable asset; this server is the typed contract around it.
Because the engine is the same parity-tested code as Phase 1 (vendored into
`lib/engine`), the tools inherit its to-the-dollar agreement with the Python
model.

## Endpoint

`POST /api/mcp` - stateless Streamable HTTP (no Redis needed).

- **Auth:** if `MCP_BEARER_TOKEN` is set, send `Authorization: Bearer <token>`.
  If it is unset the endpoint is open (handy for first deploy / local dev).
- **Live listings:** `search_listings` and `match_listings(live:true)` call the
  Realty in AU API and need `RAPIDAPI_KEY` (optional `RAPIDAPI_HOST`). With no
  key they return the committed sample.

## Tools

| Tool | What |
|---|---|
| `estimate_price` | Likely price + range for a WA house |
| `assess_property` | Estimate + buyer-fit pros/cons |
| `forecast` | Bear/base/bull scenario fan to Mid-29 |
| `score_suburb` / `rank_suburbs` | Original Como criteria scoring |
| `list_suburbs` | The dataset, with medians and in-band flag |
| `onboarding_questions` | Questions to ask a new buyer |
| `resolve_profile` | Profile -> budget, timing, weights |
| `rank_suburbs_for_profile` | Suburb ranking for a specific buyer |
| `match_listings` | Listings filtered + ranked for a buyer |
| `search_listings` | Live houses with photos (RapidAPI) |

## Local dev

```bash
cd server
npm install
npm run dev        # predev runs the engine sync first
# open http://localhost:3000  and POST to /api/mcp
```

## How it stays a single source of truth

`lib/engine/` and `data/` are **generated** - verbatim copies of the canonical
`mcp/src/` and `data/` from the repo root, produced by `scripts/sync-engine.mjs`
(run on `predev` / `prebuild`). Edit the canonical sources, not the copies. The
repo's deploy gate (`tests/run.sh`) runs the sync and fails if the committed
copies have drifted, so the copies can never silently diverge.

The vendored copy is what lets the project deploy to Vercel as a single
self-contained root, with no dependency on parent directories at build time.

## Deploy (Vercel)

Root directory: `server`. Framework preset: Next.js (auto-detected). Set
`MCP_BEARER_TOKEN` (and `RAPIDAPI_KEY` if you want live listings) as project
environment variables, then deploy. See `../mcp/BUILD_LOG.md` for the full
build narrative.
