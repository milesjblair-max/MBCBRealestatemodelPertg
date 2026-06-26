#!/usr/bin/env python3
"""
scoring.py - Como-Anchored Perth Home Model, suburb Buyer-Fit ranking (Layer 3).

Mirrors the scoreSuburb() function in web/index.html exactly, so the Python and
the web tool agree at the baseline prior (50 = balanced between Como-proximity
and top-school-catchment). Reads data/suburbs.json and data/criteria.json.

    python3 scoring.py            # print the Buyer-Fit ranking at prior=50
    python3 scoring.py 0          # all weight on Como proximity
    python3 scoring.py 100        # all weight on school catchment

Standard library only - no dependencies.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

with open(os.path.join(DATA, "suburbs.json")) as fh:
    SUBURBS = json.load(fh)["suburbs"]
with open(os.path.join(DATA, "criteria.json")) as fh:
    BASE_W = json.load(fh)["weighted_dimensions"]


def score_suburb(s, prior):
    """prior 0..100: 0 = all Como-proximity, 100 = all school. 50 = balanced."""
    swing = 0.20
    t = (prior - 50) / 50.0          # -1..+1
    w = dict(BASE_W)
    w["prox"] = max(0.0, BASE_W["prox"] - swing * t * 0.5)
    w["post"] = max(0.0, BASE_W["post"] + swing * t * 0.5)

    sc = s["scores"]
    composite = (sc["growth"] * w["growth"]
                 + sc["family"] * w["family"]
                 + sc["land"] * w["land"]
                 + sc["kdr"] * w["kdr"]
                 + sc["prox"] * w["prox"])
    # postcode dimension blends static postcode score with school catchment,
    # weighted by the slider
    post_blend = sc["post"] * (1 - (prior / 100) * 0.5) + s["school"] * ((prior / 100) * 0.5)
    composite += post_blend * w["post"]

    score = composite * 10
    over = False
    if not s["band"]:
        mid = (s["mlo"] + s["mhi"]) / 2
        if mid > 1000:
            score *= 0.55
            over = True
        else:
            score *= 0.85
    return round(score * 10) / 10, over


def main():
    prior = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    ranked = []
    for s in SUBURBS:
        score, over = score_suburb(s, prior)
        ranked.append((score, over, s))
    ranked.sort(key=lambda r: -r[0])

    label = {0: "Como first", 50: "Balanced", 100: "Schools first"}.get(prior, f"prior={prior}")
    print("=" * 60)
    print(f" Buyer-Fit ranking - anchor Como 6152 - {label}")
    print("=" * 60)
    print(f"{'#':>3}  {'Suburb':<14}{'PC':>6}{'Reg':>5}{'km':>5}{'Fit':>7}")
    print("-" * 60)
    for i, (score, over, s) in enumerate(ranked, 1):
        flag = "  over-budget" if over else ""
        print(f"{i:>3}  {s['name']:<14}{s['pc']:>6}{s['reg']:>5}"
              f"{s['km']:>5}{score:>7}{flag}")
    print("=" * 60)
    print(" Filters (land>500sqm, 4+ beds) confirmed per-listing via Landgate.")


if __name__ == "__main__":
    main()
