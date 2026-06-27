#!/usr/bin/env python3
"""
build.py - the static-first pipeline: profile -> validated -> engine -> bundle.

For each profile it: validates, picks the asset-class strategy via the registry,
asks the strategy for the market inputs, runs the shared timing engine to DERIVE
the scenario weights + buy-window, and writes one self-contained JSON bundle the
front-end fetch()es. A scheduled GitHub Action would run exactly this and commit
the bundles - multi-tenant by config, zero runtime backend.

    python3 platform/build.py                 # build every profile
    python3 platform/build.py como-residential # build one

Stdlib only.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import registry, timing, validate_profile, forecast, scoring  # noqa: E402

PROFILES_DIR = os.path.join(HERE, "profiles")
DIST_DIR = os.path.join(HERE, "dist")
REPO_ROOT = os.path.join(HERE, "..")

# map profile criteria weight keys -> the 6 suburb score dimensions
_KEY_MAP = {"proximity": "prox", "prox": "prox", "growth": "growth", "family": "family",
            "land": "land", "post": "post", "kdr": "kdr"}


def _weights_map(profile):
    w = {}
    for c in profile["criteria"]:
        if c.get("type") == "weight" and c["key"] in _KEY_MAP:
            w[_KEY_MAP[c["key"]]] = c["weight"]
    return w


def _load_json(rel):
    try:
        with open(os.path.join(REPO_ROOT, rel)) as fh:
            return json.load(fh)
    except Exception:
        return None


def build_profile(path):
    profile, ok, errors = validate_profile.load_and_validate(path)
    if not ok:
        print(f"  INVALID {os.path.basename(path)}:")
        for er in errors:
            print("    -", er)
        return None

    strat = registry.get_strategy(profile["asset_class"])
    gap, signal = strat.market_inputs(profile)
    horizon = (profile.get("horizon_years") or {}).get("primary", 3)
    timing_out = timing.derive_timing(gap, signal, horizon)

    # forecast timeline = asset-class anchors blended by the DERIVED weights
    timeline = forecast.derive_timeline(strat.ANCHORS, timing_out["weights"])

    # suburb ranking + listings, where the vertical has a data adapter
    ds = strat.datasets(profile)
    suburbs, listings, data_note = [], [], None
    if ds.get("suburbs"):
        raw = _load_json(ds["suburbs"])
        if raw:
            suburbs = scoring.rank(raw["suburbs"], _weights_map(profile))
    else:
        data_note = "suburb + listing adapter for this asset class is not wired yet"
    if ds.get("listings"):
        raw = _load_json(ds["listings"])
        if raw:
            listings = raw.get("listings", [])

    bundle = {
        "schema_version": 1,
        "profile": {
            "id": profile["id"], "label": profile["label"],
            "asset_class": profile["asset_class"], "currency": profile.get("currency", "AUD"),
            "geography": profile["geography"], "budget_band": profile["budget_band"],
            "horizon_years": profile.get("horizon_years", {}),
        },
        "asset_strategy": strat.MANIFEST,
        "timing": timing_out,
        "forecast": {"timeline": timeline, "weights": timing_out["weights"]},
        "suburbs": suburbs,
        "listings": listings,
        "data_note": data_note,
        "criteria": {
            "filters": [c for c in profile["criteria"] if c["type"] == "filter"],
            "weights": [c for c in profile["criteria"] if c["type"] == "weight"],
            "context": [c for c in profile["criteria"] if c["type"] == "context"],
        },
        "data_sources": profile.get("data_sources", []),
    }

    out_dir = os.path.join(DIST_DIR, profile["id"])
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "bundle.json")
    with open(out_path, "w") as fh:
        json.dump(bundle, fh, indent=2)
        fh.write("\n")

    w = timing_out["weights"]
    assert sum(w.values()) == 100, "weights must sum to 100"
    print(f"  {profile['id']:<18} {profile['asset_class']:<12} "
          f"weights {w['bear']}/{w['base']}/{w['bull']}  "
          f"window={timing_out['buy_window']['label']}  -> dist/{profile['id']}/bundle.json")
    return bundle


def build_index(ids):
    """A small manifest the UI uses to populate its profile switcher."""
    idx = {"profiles": ids}
    with open(os.path.join(DIST_DIR, "index.json"), "w") as fh:
        json.dump(idx, fh, indent=2)
        fh.write("\n")


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    files = sorted(f for f in os.listdir(PROFILES_DIR) if f.endswith(".json"))
    if only:
        files = [f for f in files if f[:-5] == only]
        if not files:
            print(f"no profile named {only}")
            return 1
    print("Building profile bundles:")
    built = []
    for f in files:
        b = build_profile(os.path.join(PROFILES_DIR, f))
        if b:
            built.append(b["profile"]["id"])
    build_index(built)
    print(f"Built {len(built)} profile(s); manifest -> dist/index.json")
    return 0 if built else 1


if __name__ == "__main__":
    raise SystemExit(main())
