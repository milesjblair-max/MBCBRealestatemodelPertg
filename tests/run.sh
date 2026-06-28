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

echo
if [ "$fail" -eq 0 ]; then echo "ALL PASS - safe to deploy"; else echo "FAILURES above - do NOT deploy"; fi
exit $fail
