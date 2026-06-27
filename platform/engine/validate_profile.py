"""
Phase-0 profile validator (stdlib only, no dependencies).

Validates a profile against the contract in schema/profile.schema.json. This is a
focused hand-rolled validator deliberately - CLAUDE.md mandates stdlib + no build
step for now. Phase 1 swaps this for Pydantic v2 (Python) + Zod (TS) sharing the
SAME exported JSON Schema, so the browser and the engine validate identically.
The JSON Schema file is already the source of truth; this just enforces it today.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(HERE, "..", "schema", "profile.schema.json")
KNOWN_ASSET_CLASSES = ["residential", "commercial"]


def validate(profile):
    """Return (ok, errors). errors is a list of human-readable strings."""
    e = []
    req = ["id", "label", "asset_class", "geography", "budget_band", "criteria"]
    for k in req:
        if k not in profile:
            e.append(f"missing required key: {k}")

    if "id" in profile and not _is_slug(profile["id"]):
        e.append("id must be a lowercase slug [a-z0-9-]")

    ac = profile.get("asset_class")
    if ac and ac not in KNOWN_ASSET_CLASSES:
        e.append(f"asset_class '{ac}' not in {KNOWN_ASSET_CLASSES}")

    bb = profile.get("budget_band")
    if bb is not None:
        if not (isinstance(bb, list) and len(bb) == 2):
            e.append("budget_band must be [min, max]")
        elif bb[0] > bb[1]:
            e.append("budget_band min must be <= max")

    crit = profile.get("criteria")
    if not isinstance(crit, list) or not crit:
        e.append("criteria must be a non-empty array")
    else:
        wsum = 0.0
        for i, c in enumerate(crit):
            if "key" not in c or "type" not in c:
                e.append(f"criteria[{i}] needs key and type")
                continue
            if c["type"] not in ("filter", "weight", "context"):
                e.append(f"criteria[{i}].type invalid: {c['type']}")
            if c["type"] == "weight":
                w = c.get("weight")
                if not isinstance(w, (int, float)):
                    e.append(f"criteria[{i}] (weight) needs a numeric weight")
                else:
                    wsum += w
        if abs(wsum - 1.0) > 0.001 and any(c.get("type") == "weight" for c in crit):
            e.append(f"weight-type criteria must sum to 1.0 (got {wsum:.3f})")

    return (len(e) == 0, e)


def _is_slug(s):
    return isinstance(s, str) and s and all(ch.islower() or ch.isdigit() or ch == "-" for ch in s)


def load_and_validate(path):
    with open(path) as fh:
        profile = json.load(fh)
    ok, errors = validate(profile)
    return profile, ok, errors


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "profiles", "como-residential.json")
    profile, ok, errors = load_and_validate(p)
    print(f"{os.path.basename(p)} -> {'VALID' if ok else 'INVALID'}")
    for er in errors:
        print("  -", er)
    raise SystemExit(0 if ok else 1)
