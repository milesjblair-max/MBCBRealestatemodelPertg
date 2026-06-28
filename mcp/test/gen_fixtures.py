#!/usr/bin/env python3
"""
gen_fixtures.py - emit the canonical numbers from the Python model as JSON.

The TypeScript parity test runs the SAME inputs through the TS engine and asserts
it matches this output to the dollar. This is how we prove the port is faithful
across two languages. Stdlib only.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "model"))
import avm        # noqa: E402
import scoring    # noqa: E402

out = []

# --- estimate() fixtures: a spread of suburbs, sizes, conditions --------------
EST_CASES = [
    {"suburb": "Como", "land": 1100, "beds": 4, "baths": 3, "condition": "good"},
    {"suburb": "Shelley", "land": 696, "beds": 3, "baths": 1, "condition": "original"},
    {"suburb": "Wilson", "land": 683, "beds": 4, "baths": 2, "condition": "renovated"},
    {"suburb": "Nollamara", "land": 760, "beds": 3, "baths": 1, "condition": "original"},
    {"suburb": "Riverton", "land": 705, "beds": 4, "baths": 2, "condition": "good"},
    {"suburb": "Dianella", "land": 950, "beds": 5, "baths": 2, "condition": "new"},
    {"suburb": "Bentley", "land": 400, "beds": 2, "baths": 1, "condition": "dated"},
    {"suburb": "Shelley"},  # suburb only - widest band
    {"suburb": "Bayswater", "land": 1000, "beds": 6, "baths": 3, "condition": "renovated"},
]
for c in EST_CASES:
    r = avm.estimate(c["suburb"], c.get("land"), c.get("beds"),
                     c.get("baths"), c.get("condition"))
    out.append({
        "tool": "estimate",
        "input": c,
        "expected": {k: r[k] for k in
                     ("likely", "low", "high", "guide_floor",
                      "spread_pct", "confidence", "in_band")},
    })

# --- score_suburb() fixtures: every suburb at three priors --------------------
for prior in (0, 50, 100):
    for s in scoring.SUBURBS:
        score, over = scoring.score_suburb(s, prior)
        out.append({
            "tool": "score",
            "input": {"suburb": s["name"], "prior": prior},
            "expected": {"score": score, "over": over},
        })

print(json.dumps(out))
