#!/usr/bin/env bash
# run.sh - the pre-deploy gate. Run this and get ALL PASS before every push.
#   bash tests/run.sh
# It checks the model, the web tool, the web/root sync, and the no-dashes rule.
# Live portal link checks run separately in CI (this sandbox can't reach them).
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0

echo "== 1. Python model =="
if python3 model/scenario_model.py | grep -q "PASS"; then echo "  scenario_model.py PASS"; else echo "  scenario_model.py FAILED"; fail=1; fi
python3 model/scoring.py >/dev/null 2>&1 && echo "  scoring.py ok" || { echo "  scoring.py FAILED"; fail=1; }
python3 model/avm.py >/dev/null 2>&1 && echo "  avm.py ok" || { echo "  avm.py FAILED"; fail=1; }

echo "== 2. web == root copy (deploy serves /index.html) =="
if diff -q web/index.html index.html >/dev/null; then echo "  in sync"; else echo "  OUT OF SYNC: cp web/index.html index.html"; fail=1; fi

echo "== 3. no em/en/minus dashes (house style) =="
if grep -rlP "[\x{2013}\x{2014}\x{2212}]" web/index.html index.html >/dev/null 2>&1; then echo "  DASH FOUND"; fail=1; else echo "  clean"; fi

echo "== 4. web regression (headless browser) =="
export PW_EXECUTABLE="${PW_EXECUTABLE:-$(ls /opt/pw-browsers/chromium-*/chrome-linux/chrome 2>/dev/null | head -1)}"
# ESM imports resolve only from a local node_modules; link the bundled
# playwright-core (CI installs it instead, so this no-ops there).
if [ ! -e node_modules/playwright-core ]; then
  mkdir -p node_modules
  pwc="$(find /opt/node22/lib/node_modules -maxdepth 3 -type d -name playwright-core 2>/dev/null | head -1)"
  [ -n "$pwc" ] && ln -s "$pwc" node_modules/playwright-core 2>/dev/null || true
fi
if node tests/regression.mjs; then echo "  regression ok"; else echo "  regression FAILED"; fail=1; fi

echo "== 5. MCP engine tests (TS == Python parity + dynamic-profile units) =="
if [ -d mcp ]; then
  ( cd mcp && [ -d node_modules ] || npm install --silent >/dev/null 2>&1
    npm run --silent test:engine >/tmp/mcp_engine.log 2>&1 )
  if [ $? -eq 0 ]; then
    echo "  $(grep -o 'parity: .*' /tmp/mcp_engine.log | tail -1)"
    echo "  $(grep -o 'profile: .*' /tmp/mcp_engine.log | tail -1)"
  else
    echo "  MCP engine tests FAILED"; tail -8 /tmp/mcp_engine.log; fail=1
  fi
else
  echo "  (mcp/ not present, skipped)"
fi

echo "== 6. Phase 2 server: vendored engine/data in sync with canonical =="
if [ -d server ]; then
  node server/scripts/sync-engine.mjs >/dev/null 2>&1
  # listings.json is a volatile daily-refreshed fallback, so exclude it; the
  # live tool fetches fresh anyway. Everything else must match exactly.
  drift="$(git status --porcelain -- server/lib server/data | grep -v 'server/data/listings.json')"
  if [ -z "$drift" ]; then
    echo "  server/lib/engine and server/data match mcp/src and data/"
  else
    echo "  OUT OF SYNC: run 'node server/scripts/sync-engine.mjs' and commit"; echo "$drift"; fail=1
  fi
else
  echo "  (server/ not present, skipped)"
fi

echo "== 7. no em/en/minus dashes in Phase 1/2 sources =="
if grep -rlP "[\x{2013}\x{2014}\x{2212}]" mcp/src mcp/test mcp/*.md server/app server/lib server/scripts server/*.md data/profile.schema.json data/profiles 2>/dev/null; then
  echo "  DASH FOUND ^^^"; fail=1
else
  echo "  clean"
fi

echo
if [ "$fail" -eq 0 ]; then echo "ALL PASS - safe to deploy"; else echo "FAILURES above - do NOT deploy"; fi
exit $fail
