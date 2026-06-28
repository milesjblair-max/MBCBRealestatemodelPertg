# Como MCP engine (Phase 1)

The Como model logic, extracted from the HTML tool into a **typed TypeScript
library** with a **cross-language parity test** against the Python reference.
This is the foundation the MCP server (Phase 2) is built on.

See **[BUILD_LOG.md](./BUILD_LOG.md)** for the full how-and-why (written to teach
the MCP build pattern).

## Run it

```bash
cd mcp
npm install
npm test        # typecheck + parity (TS engine == Python model, 179 checks)
npm run demo    # estimate, suburb ranking, forecast, assessment
```

## Layout

| Path | What |
|---|---|
| `src/types.ts` | Shared types (also the basis for the MCP tool schemas) |
| `src/data.ts` | Loads the shared `data/*.json` (one source of truth) |
| `src/avm.ts` | Price estimator (port of `model/avm.py`) |
| `src/scoring.ts` | Suburb Buyer-Fit (port of `model/scoring.py`) |
| `src/scenario.ts` | Forecast spine (port of `model/scenario_model.py`) |
| `src/assess.ts` | Property pros/cons + fit (port of the tool's JS) |
| `src/index.ts` | Public API + a runnable demo |
| `test/gen_fixtures.py` | Emits canonical numbers from the Python model |
| `test/parity.ts` | Asserts the TS engine matches them to the dollar |

## Status

Phase 1 (this): engine extracted, typed, parity-tested. **Done.**
Phase 2 (next): wrap each function as an MCP tool, host on Vercel.
