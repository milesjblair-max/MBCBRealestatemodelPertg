# Deploying the MCP server to Vercel (git integration)

The server lives in `server/` and deploys as a standard Next.js project. Vercel's
GitHub integration is the cleanest path: connect once, then every push deploys.

## One-time setup

1. Go to <https://vercel.com/new> and import
   `milesjblair-max/mbcbrealestatemodelpertg`.
2. **Root Directory:** set it to **`server`** (click "Edit" next to Root
   Directory and choose the `server` folder). This is the only non-default
   setting that matters.
3. **Framework Preset:** Next.js (auto-detected). Leave Build and Install
   commands on their defaults.
4. **Environment Variables** (Project Settings -> Environment Variables):
   | Name | Needed? | Value |
   |---|---|---|
   | `MCP_BEARER_TOKEN` | Recommended | A long random string. Clients must then send `Authorization: Bearer <that string>`. Leave unset to keep the endpoint open. |
   | `RAPIDAPI_KEY` | Optional | Your RapidAPI key, to enable the live `search_listings` tool. Without it, that tool returns the committed sample. |
   | `RAPIDAPI_HOST` | Optional | Defaults to `realty-in-au.p.rapidapi.com`. |
5. Deploy.

## The one gotcha: the production branch

This work is on the branch **`claude/repo-connection-mhn1nl`**, not your default
branch. Vercel builds *production* from the default branch and *previews* from
others. So either:

- **Settings -> Git -> Production Branch** = `claude/repo-connection-mhn1nl`, or
- merge `claude/repo-connection-mhn1nl` into your default branch first.

Otherwise the production URL will not include Phase 2 until you merge.

## Verify after deploy

The endpoint is `https://<your-project>.vercel.app/api/mcp`. Quick check:

```bash
curl -s -X POST https://<your-project>.vercel.app/api/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Authorization: Bearer <MCP_BEARER_TOKEN>' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

You should get the 11 tools back. (Drop the Authorization header if you left
`MCP_BEARER_TOKEN` unset.)

## Connect a client

```json
{
  "mcpServers": {
    "como-home-model": {
      "url": "https://<your-project>.vercel.app/api/mcp",
      "headers": { "Authorization": "Bearer <MCP_BEARER_TOKEN>" }
    }
  }
}
```

## Notes

- The build runs `scripts/sync-engine.mjs` on `prebuild`. With the full repo
  cloned it refreshes the vendored engine/data from `../mcp/src` and `../data`;
  the committed copies make the deploy work even if those are ever absent.
- Stateless Streamable HTTP, so no Redis or other backing store is required.
