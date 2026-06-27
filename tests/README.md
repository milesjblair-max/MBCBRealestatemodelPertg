# Regression tests

The deal: **run `bash tests/run.sh` and get `ALL PASS` before every push to
production.** When we add a feature or fix a bug, we add a check here so it can
never silently break again.

## What runs

| File | Checks | Where |
|---|---|---|
| `run.sh` | The pre-deploy gate: runs everything below and the no-dashes + web/root-sync rules. | Local + CI |
| `regression.mjs` | Renders `web/index.html` in headless Chromium and asserts: tabs, section order (A/B/C), collapsible headers, **portal URL formats** (REA / Domain / REIWA), inline listing URLs, the AVM estimate + scorecard + lookups, the map (Como appears once, 13 bubbles, legend key), and the reset-to-baseline contract. No console errors. | Local + CI |
| `check_links_live.mjs` | Actually GETs the real REA / Domain / REIWA URLs and fails on 404/410 (a dead path). Needs outbound network, so it runs in **CI only** (the dev sandbox is firewalled off the portals). | CI |
| `model/scenario_model.py` | The model self-verifies against `data/baseline.json` and prints `PASS`. | Local + CI |

## Run it

```bash
bash tests/run.sh                 # the gate; must print ALL PASS
node tests/check_links_live.mjs   # live link check (needs internet)
```

`run.sh` auto-finds the sandbox Chromium. Elsewhere, set `PW_EXECUTABLE` to a
Chromium binary, or `npx playwright install chromium` first.

## When you change something

- New portal/link format -> update the regex in `regression.mjs` AND add it to `check_links_live.mjs`.
- New section or tab -> update the order/caret assertions.
- New AVM behaviour -> update the expected numbers (they are pinned, e.g. Shelley 3/1/696 original = $915k).
- New model numbers -> `scenario_model.py` must still print `PASS`.
