#!/usr/bin/env python3
"""
avm.py - Tier 2 AVM-lite: estimate a price RANGE for a property the portals
won't show a price for.

The problem: realestate.com.au / Domain / REIWA often hide the price ("Contact
agent", "offers above", blank) but still show the suburb, land size, bedrooms
and bathrooms. This estimates the seller's likely range from exactly those
visible attributes, with NO paid API and NO scraping. It anchors on the suburb
median in data/suburbs.json (the value of a typical home there) and adjusts up
or down for how the specific property differs.

It deliberately returns a RANGE with a confidence label, never a single number.
Automated valuations run +/-10-15%, and worse on original / KDR stock in the
thin-volume school-zone suburbs this buyer is shopping, so false precision would
be dishonest. The estimate is general information, not a valuation or advice.

Usage:
    python3 model/avm.py                      # run the demo table
    python3 model/avm.py "Shelley" 696 3 1 original
    python3 model/avm.py "Wilson" 683 4 2 renovated

Stdlib only.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUBURBS_PATH = os.path.join(HERE, "..", "data", "suburbs.json")

# ---- Hedonic coefficients (documented, deliberately conservative) -----------
# A "reference home" is a 4-bed, 2-bath house on a typical block for its side of
# the river. The suburb median is treated as the value of that reference home.
# We then adjust for the differences. All money is in $000s to match the data.
REF_BEDS = 4
REF_BATHS = 2
REF_LAND = {"S": 600, "N": 650}      # typical established block by river side

# Marginal land value inside a HOME price is far below the raw land rate: an
# owner-occupier pays for utility (a bigger yard), not subdividable land value,
# until the block is genuinely big. So a moderate rate, tapering on large blocks.
LAND_RATE = 0.45                     # $000 per sqm of difference from reference
LAND_TAPER_OVER = 250                # sqm above reference where marginal rate halves

BED_VALUE = 25                       # $000 per bedroom vs reference
BATH_VALUE = 15                      # $000 per bathroom vs reference

# Condition scales the dwelling. Original is only lightly discounted because in
# these KDR-target suburbs original stock is bought for the land, not the house.
CONDITION = {
    "original": 0.96, "dated": 0.98, "good": 1.00,
    "renovated": 1.06, "new": 1.13,
}
CONDITION_HELP = "original | dated | good | renovated | new"

# ---- Range / confidence -----------------------------------------------------
BASE_SPREAD = 0.12                   # +/- band with no attributes beyond suburb
MIN_SPREAD = 0.07
MAX_SPREAD = 0.20


def _load_suburbs():
    with open(SUBURBS_PATH) as fh:
        return {s["name"].lower(): s for s in json.load(fh)["suburbs"]}


def _round5(x):
    """Round to the nearest $5k - a guide figure, not false precision."""
    return int(round(x / 5.0) * 5)


def estimate(suburb, land=None, beds=None, baths=None, condition=None,
             _suburbs=None):
    """Estimate a price range for one property. Returns a dict, all $ in $000s.

    Only `suburb` is required. The more of land / beds / baths / condition you
    give it, the narrower and more confident the range.
    """
    subs = _suburbs if _suburbs is not None else _load_suburbs()
    s = subs.get(suburb.strip().lower())
    if not s:
        raise ValueError(f"Unknown suburb '{suburb}'. Known: "
                         + ", ".join(sorted(x.title() for x in subs)))

    mlo, mhi = s["mlo"], s["mhi"]
    mid = (mlo + mhi) / 2.0
    ref_land = REF_LAND.get(s.get("reg", "S"), 600)

    notes = []
    value = mid

    # Land: linear, tapering above +250sqm over the reference block.
    if land is not None:
        diff = land - ref_land
        if diff > LAND_TAPER_OVER:
            adj = LAND_TAPER_OVER * LAND_RATE + (diff - LAND_TAPER_OVER) * LAND_RATE * 0.5
        elif diff < -LAND_TAPER_OVER:
            adj = -LAND_TAPER_OVER * LAND_RATE + (diff + LAND_TAPER_OVER) * LAND_RATE * 0.5
        else:
            adj = diff * LAND_RATE
        value += adj
        notes.append(f"land {land}sqm vs ~{ref_land}sqm typical: {adj:+.0f}k")

    # Bedrooms / bathrooms vs the reference home.
    if beds is not None:
        adj = (beds - REF_BEDS) * BED_VALUE
        value += adj
        notes.append(f"{beds} bed vs {REF_BEDS}: {adj:+.0f}k")
    if baths is not None:
        adj = (baths - REF_BATHS) * BATH_VALUE
        value += adj
        notes.append(f"{baths} bath vs {REF_BATHS}: {adj:+.0f}k")

    # Condition multiplies the whole dwelling.
    if condition is not None:
        key = condition.strip().lower()
        if key not in CONDITION:
            raise ValueError(f"condition must be one of: {CONDITION_HELP}")
        factor = CONDITION[key]
        before = value
        value *= factor
        notes.append(f"{key} condition x{factor:.2f}: {value - before:+.0f}k")

    # ---- Range width: start wide, narrow with more inputs, widen on noise ----
    supplied = sum(x is not None for x in (land, beds, baths, condition))
    spread = BASE_SPREAD - 0.01 * min(supplied, 4)          # up to -0.04

    band_rel = (mhi - mlo) / mid                            # how wide the median itself is
    if band_rel > 0.08:
        spread += (band_rel - 0.08) * 0.5                   # wide median -> wider estimate

    if land is not None and abs(land - ref_land) > LAND_TAPER_OVER:
        spread += 0.02                                      # extrapolating on land
    if beds is not None and (beds <= 2 or beds >= 6):
        spread += 0.02                                      # unusual config

    spread = max(MIN_SPREAD, min(MAX_SPREAD, spread))

    likely = value
    low = likely * (1 - spread)
    high = likely * (1 + spread)

    if spread < 0.09:
        confidence = "High"
    elif spread < 0.135:
        confidence = "Medium"
    else:
        confidence = "Low"

    # Seller framing: an advertised "offers above" / "from" figure is usually a
    # FLOOR set a touch under the likely value to draw enquiry.
    guide_floor = likely * 0.95

    return {
        "suburb": s["name"], "pc": s["pc"],
        "median_range": [mlo, mhi],
        "likely": _round5(likely),
        "low": _round5(low), "high": _round5(high),
        "guide_floor": _round5(guide_floor),
        "spread_pct": round(spread * 100, 1),
        "confidence": confidence,
        "inputs": {"land": land, "beds": beds, "baths": baths,
                   "condition": condition},
        "adjustments": notes,
        "school": s.get("school"),
        "in_band": bool(s.get("band")),
    }


def _fmt(v):
    return f"${v:,}k" if v < 1000 else f"${v/1000:.2f}M"


def _print_one(r):
    rng = f"{_fmt(r['low'])} to {_fmt(r['high'])}"
    print(f"  {r['suburb']} {r['pc']}  ({r['confidence']} confidence, "
          f"+/-{r['spread_pct']}%)")
    print(f"    median of a typical home: ${r['median_range'][0]}k-"
          f"${r['median_range'][1]}k")
    print(f"    likely value : {_fmt(r['likely'])}")
    print(f"    range        : {rng}")
    print(f"    advertised 'offers above' is usually near {_fmt(r['guide_floor'])}")
    if r["adjustments"]:
        print("    why          : " + "; ".join(r["adjustments"]))


def _demo():
    subs = _load_suburbs()
    print("Tier 2 AVM-lite - sample estimates from visible listing attributes")
    print("(suburb, land sqm, beds, baths, condition). All ranges, not prices.\n")
    samples = [
        ("Shelley", 696, 3, 1, "original"),
        ("Wilson", 683, 4, 2, "renovated"),
        ("St James", 706, 3, 1, "original"),
        ("Bentley", 728, 4, 1, "dated"),
        ("Riverton", 705, 4, 2, "good"),
        ("Dianella", 683, 4, 2, "good"),
        ("Parkwood", 712, 4, 2, "good"),
        ("Nollamara", 760, 3, 1, "original"),
    ]
    for name, land, beds, baths, cond in samples:
        _print_one(estimate(name, land, beds, baths, cond, _suburbs=subs))
        print()
    print("Same Shelley block, suburb only (no attributes) - wider, lower confidence:")
    _print_one(estimate("Shelley", _suburbs=subs))


def main(argv):
    if len(argv) <= 1:
        _demo()
        return 0
    name = argv[1]
    land = int(argv[2]) if len(argv) > 2 else None
    beds = int(argv[3]) if len(argv) > 3 else None
    baths = int(argv[4]) if len(argv) > 4 else None
    cond = argv[5] if len(argv) > 5 else None
    _print_one(estimate(name, land, beds, baths, cond))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
