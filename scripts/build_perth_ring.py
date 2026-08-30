#!/usr/bin/env python3
"""
build_perth_ring.py - build data/perth_ring.json, the inner-Perth search ring.

Why this exists: the listings feed used to search only the 8 curated in-budget
suburbs, so a genuine bargain two suburbs over was invisible. This builds the
wider universe the feed now sweeps: every residential suburb within a set
radius of the Perth CBD, tagged north / east / south / west, with its distance
to the CBD and to the buyer's Como anchor.

It invents nothing. Names, postcodes and coordinates come straight from
data/wa_suburbs.json (the public-domain base layer built by
build_wa_base_layer.py). Everything added here is arithmetic on those
coordinates, plus a documented filter that drops postal-delivery entries which
are not real suburbs ("Bentley Dc", "Perth Gpo", "Canning Bridge Applecross").

Medians and scores are NOT added here. Only the 14 curated suburbs in
data/suburbs.json have researched medians; the rest are priced off live
comparable listings at fetch time (see model/value.py).

Run: python3 scripts/build_perth_ring.py [radius_km]
Stdlib only.
"""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
BASE_PATH = os.path.join(DATA, "wa_suburbs.json")
CURATED_PATH = os.path.join(DATA, "suburbs.json")
OUT = os.path.join(DATA, "perth_ring.json")

# Perth GPO. The ring is measured from here, so "close to the city" means the
# same thing in every direction.
CBD = (-31.9523, 115.8613)
BUYER_ANCHOR = "Como"           # the buyer's family anchor, looked up in the
                                # base layer rather than hardcoded, so the
                                # coordinate can never drift from the data
DEFAULT_RADIUS_KM = 15

# ---- Sector boundaries (bearing degrees, clockwise from true north) ---------
# Not plain 45-degree quadrants: Perth's coast runs north-south and the CBD sits
# on the river, so the naive split files Scarborough as "west" and Melville as
# "south west". These bounds are rotated to match how Perth is actually talked
# about: the northern coastal strip reads north, the "western suburbs" run
# Nedlands to Fremantle, and everything across the river to the south east is
# south.
SECTORS = [
    ("N", 300, 30),
    ("E", 30, 130),
    ("S", 130, 215),
    ("W", 215, 300),
]

# ---- Not-a-suburb filter ----------------------------------------------------
# The postcode base layer carries postal delivery areas alongside real
# localities. Each rule below is narrow and reported in the output so the drop
# list is auditable rather than magic.
POSTAL_SUFFIX = re.compile(r"\s(Dc|Bc|Gpo|Lpo|Mc)$", re.I)
POSTAL_WORDS = re.compile(r"\b(Delivery Centre|Business Centre|Po Boxes)\b", re.I)
STREET_TOKEN = re.compile(r"\s(Tce|Rd|Ave|Hwy|Pde|Cnr)\b|\sSt$", re.I)
# "<Suburb> <qualifier>" duplicates of a suburb that already exists on its own
QUALIFIER_SUFFIX = {"north", "south", "east", "west", "central", "forum", "airport"}
# Legitimate localities with effectively no housing stock. Searching them is a
# wasted API call every single day, so they are excluded by name, on purpose.
NON_RESIDENTIAL = {
    "Kings Park", "Karrakatta", "Herdsman", "Dog Swamp", "Perth Airport",
}
# Prefixes that make "<X> <Suburb>" a real suburb rather than a postal alias.
REAL_PREFIX = {"north", "south", "east", "west", "upper", "lower", "mount",
               "mt", "new", "port"}


def haversine_km(a_lat, a_lng, b_lat, b_lng):
    r = 6371.0
    d_lat = math.radians(b_lat - a_lat)
    d_lng = math.radians(b_lng - a_lng)
    s = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat))
         * math.sin(d_lng / 2) ** 2)
    return r * 2 * math.asin(math.sqrt(s))


def bearing_deg(a_lat, a_lng, b_lat, b_lng):
    """Compass bearing from a to b, 0-360, using a local flat approximation
    (fine over 15km, and it keeps the sector edges easy to reason about)."""
    dx = (b_lng - a_lng) * math.cos(math.radians((a_lat + b_lat) / 2))
    dy = b_lat - a_lat
    return (math.degrees(math.atan2(dx, dy)) + 360) % 360


def sector_for(bearing):
    for name, lo, hi in SECTORS:
        if lo > hi:                       # the sector that wraps through 0
            if bearing >= lo or bearing < hi:
                return name
        elif lo <= bearing < hi:
            return name
    return "N"


def reject_reason(name, all_names):
    """Why this base-layer row is not a searchable suburb, or None if it is."""
    if name in NON_RESIDENTIAL:
        return "non-residential locality"
    if POSTAL_SUFFIX.search(name) or POSTAL_WORDS.search(name):
        return "postal delivery area"
    if STREET_TOKEN.search(name):
        return "street-address postal entry"
    parts = name.split()
    if len(parts) >= 2:
        head, tail = " ".join(parts[:-1]), parts[-1].lower()
        if tail in QUALIFIER_SUFFIX and head in all_names:
            return f"postal split of {head}"
        # "<landmark> <Suburb>": Broadway Nedlands, Canning Bridge Applecross.
        # Try every split so a multi-word landmark is caught too.
        for i in range(1, len(parts)):
            lead, rest = parts[i - 1].lower(), " ".join(parts[i:])
            if rest in all_names and lead not in REAL_PREFIX:
                return f"postal alias of {rest}"
    return None


def main():
    radius = float(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RADIUS_KM

    with open(BASE_PATH) as fh:
        base = json.load(fh)["suburbs"]

    anchor = next((s for s in base if s["name"] == BUYER_ANCHOR), None)
    if not anchor:
        raise SystemExit(f"{BUYER_ANCHOR} is missing from the base layer; "
                         "rebuild it with scripts/build_wa_base_layer.py")
    como = (anchor["lat"], anchor["lng"])
    with open(CURATED_PATH) as fh:
        curated = {s["name"] for s in json.load(fh)["suburbs"]}

    all_names = {s["name"] for s in base}

    kept, dropped = [], []
    for s in base:
        km_cbd = haversine_km(CBD[0], CBD[1], s["lat"], s["lng"])
        if km_cbd > radius:
            continue
        why = reject_reason(s["name"], all_names)
        if why:
            dropped.append({"name": s["name"], "why": why})
            continue
        brg = bearing_deg(CBD[0], CBD[1], s["lat"], s["lng"])
        kept.append({
            "name": s["name"],
            "pc": s["pc"],
            "lat": s["lat"],
            "lng": s["lng"],
            "sa2": s["sa2"],
            "kmCbd": round(km_cbd, 1),
            "kmComo": round(haversine_km(como[0], como[1], s["lat"], s["lng"]), 1),
            "sector": sector_for(brg),
            "curated": s["name"] in curated,
        })

    kept.sort(key=lambda x: (x["sector"], x["kmCbd"]))
    by_sector = {}
    for s in kept:
        by_sector[s["sector"]] = by_sector.get(s["sector"], 0) + 1

    out = {
        "meta": {
            "built_from": "data/wa_suburbs.json (public-domain postcode base layer)",
            "anchor_cbd": {"lat": CBD[0], "lng": CBD[1], "label": "Perth GPO"},
            "anchor_buyer": {"lat": como[0], "lng": como[1],
                             "label": f"{BUYER_ANCHOR} {anchor['pc']}"},
            "radius_km": radius,
            "km_note": "kmCbd and kmComo are straight-line distances between "
                       "suburb centre points. By road they are further; the "
                       "curated km field in data/suburbs.json is a road-style "
                       "figure and will not match.",
            "sectors": {name: f"bearing {lo} to {hi} degrees from the CBD"
                        for name, lo, hi in SECTORS},
            "sector_note": "Bounds are rotated off true quadrants to match how "
                           "Perth is actually described: the coastal strip north "
                           "of the CBD reads north, the western suburbs run "
                           "Nedlands to Fremantle, and across the river reads south.",
            "note": "Geography only. No medians, scores or prices are set here; "
                    "only the 14 suburbs in data/suburbs.json carry researched "
                    "medians, and everything else is valued off live comparable "
                    "listings at fetch time.",
            "count": len(kept),
            "by_sector": by_sector,
            "curated_in_ring": sum(1 for s in kept if s["curated"]),
            "dropped": dropped,
        },
        "suburbs": kept,
    }
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)
        fh.write("\n")

    print(f"Perth ring, {radius:g}km from the CBD: {len(kept)} suburbs "
          f"({len(dropped)} postal/non-residential rows dropped)")
    for name, _, _ in SECTORS:
        names = [s["name"] for s in kept if s["sector"] == name]
        print(f"  {name}: {len(names):>3}  {', '.join(names[:8])}"
              + (" ..." if len(names) > 8 else ""))
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
