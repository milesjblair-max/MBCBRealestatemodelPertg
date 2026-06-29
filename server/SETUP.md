# Environment variables (WA Home Model server)

Set these in Vercel: Project -> Settings -> Environment Variables (Production +
Preview). Names are case-sensitive and must match exactly. Changes only take
effect on a new build, so redeploy after editing them.

| Variable | Required? | What it does |
|---|---|---|
| `MCP_BEARER_TOKEN` | Recommended | Locks the MCP endpoint. Clients must send `Authorization: Bearer <token>`. If unset, the endpoint is open. |
| `RAPIDAPI_KEY` | For live prices | Your RapidAPI key for the "Realty in AU" API. Enables real listings and the live prices that `recommend_areas`, `match_listings` and `search_listings` use. Without it: `recommend_areas` still locates and distance-scores areas but shows no prices; the listing tools fall back to the committed sample. |
| `RAPIDAPI_HOST` | Optional | Defaults to `realty-in-au.p.rapidapi.com` (correct for the current API). Only set this if the host ever changes. |

Common mistake: the key must be spelled `RAPIDAPI_KEY` exactly (R-A-P-I-D-A-P-I),
not `APIDAPI_KEY`. A misspelled name is silently ignored.

Security: treat `RAPIDAPI_KEY` and `MCP_BEARER_TOKEN` as secrets (mark them
Sensitive in Vercel). If a key is ever shown on screen or shared, rotate it in
the provider's console.
