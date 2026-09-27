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

# ---- Which side of the city is this suburb on? ------------------------------
# Bearing from the CBD alone gets this wrong, and did: it filed Victoria Park,
# Carlisle, Queens Park, East Cannington and Kenwick as "east" when every Perth
# local calls them south of the river, and it put Dalkeith in the south when it
# is a western suburb. The reason is that Perth is not organised around a
# compass rose, it is organised around the Swan. So the split is done the way
# the city actually reads:
#
#   1. South of the Swan     -> "S", unless it is far enough east to be the
#                               Belmont / airport / foothills run, which is "E".
#   2. North of the Swan     -> bearing from the CBD decides: the coastal and
#                               inland strip above the city is "N", the
#                               Bayswater to Guildford run is "E", and the
#                               western suburbs from Subiaco out to North
#                               Fremantle are "W".
#
# SWAN is the river's main stem, west (Fremantle mouth) to east (Midland), as
# (lng, lat) points. Only the Swan is traced, not the Canning: the Canning
# separates southern suburbs from other southern suburbs, so it changes no
# answer here. The line is coarse on purpose, a few hundred metres is plenty to
# separate suburb centre points, and the self-test pins the suburbs that sit
# closest to it (Dalkeith and Attadale face each other across Point Resolution;
# Mosman Park and East Fremantle across the same reach).
SWAN = [
    (115.735, -32.050), (115.745, -32.045), (115.760, -32.038),
    (115.766, -32.028), (115.780, -32.015), (115.790, -32.010),
    (115.799, -32.005), (115.811, -31.995), (115.825, -31.986),
    (115.839, -31.975), (115.850, -31.966), (115.862, -31.958),
    (115.880, -31.958), (115.900, -31.962), (115.920, -31.950),
    (115.940, -31.930), (115.960, -31.910), (115.990, -31.900),
    (116.030, -31.890),
]
# South of the river, a bearing under this reads as the eastern run (Belmont,
# Kewdale, Forrestfield, High Wycombe) rather than as southern suburbs.
SOUTH_BANK_EAST_MAX = 115.0
# North of the river, the bearing bands.
NORTH_BANK = [("N", 300, 30), ("E", 30, 130), ("W", 130, 300)]

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


def river_lat(lng):
    """Latitude of the Swan at this longitude, by linear interpolation."""
    if lng <= SWAN[0][0]:
        return SWAN[0][1]
    if lng >= SWAN[-1][0]:
        return SWAN[-1][1]
    for (x1, y1), (x2, y2) in zip(SWAN, SWAN[1:]):
        if x1 <= lng <= x2:
            return y1 + (lng - x1) / (x2 - x1) * (y2 - y1)
    return SWAN[-1][1]


def south_of_river(lat, lng):
    """True when the suburb centre sits south of the Swan (more negative)."""
    return lat < river_lat(lng)


def sector_for(lat, lng, bearing):
    if south_of_river(lat, lng):
        return "E" if bearing < SOUTH_BANK_EAST_MAX else "S"
    for name, lo, hi in NORTH_BANK:
        if lo > hi:                       # the band that wraps through 0
            if bearing >= lo or bearing < hi:
                return name
        elif lo <= bearing < hi:
            return name
    return "W"


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


# Every suburb here was filed in the wrong direction by the old compass-quadrant
# rule, or sits close enough to the river that a sloppy line would move it.
# A Perth local reading the page decides what is correct, so these are pinned.
SECTOR_EXPECTED = {
    # south of the river, and read that way, though east-ish of the CBD
    "Victoria Park": "S", "East Victoria Park": "S", "Carlisle": "S",
    "Queens Park": "S", "East Cannington": "S", "Kenwick": "S",
    "Welshpool": "S", "Thornlie": "S", "Como": "S", "South Perth": "S",
    "Bentley": "S", "Shelley": "S", "Willetton": "S",
    # the eastern run: south of the Swan, but nobody calls these southern
    "Belmont": "E", "Kewdale": "E", "Redcliffe": "E", "Cloverdale": "E",
    "Forrestfield": "E", "High Wycombe": "E",
    # north of the river, east of the city
    "Bayswater": "E", "Morley": "E", "Bassendean": "E", "Guildford": "E",
    "Maylands": "E",
    # the western suburbs, several of them across the water from southern ones
    "Dalkeith": "W", "Nedlands": "W", "Claremont": "W", "Cottesloe": "W",
    "Mosman Park": "W", "North Fremantle": "W", "Peppermint Grove": "W",
    "Subiaco": "W", "City Beach": "W",
    # the south bank facing those, across Point Resolution and the harbour
    "Attadale": "S", "Bicton": "S", "East Fremantle": "S", "Fremantle": "S",
    "Applecross": "S", "Melville": "S", "Mount Pleasant": "S",
    # north, including the coastal strip a plain quadrant called west
    "Scarborough": "N", "Innaloo": "N", "Dianella": "N", "Mount Lawley": "N",
    "Balcatta": "N", "North Beach": "N", "Trigg": "N",
}


def selftest(kept):
    """Fail the build if a suburb lands on the wrong side of the city."""
    by_name = {s["name"]: s for s in kept}
    bad, missing = [], []
    for name, want in SECTOR_EXPECTED.items():
        s = by_name.get(name)
        if not s:
            missing.append(name)
        elif s["sector"] != want:
            bad.append(f"{name}: got {s['sector']}, expected {want}")
    if missing:
        print(f"  warn: not in the ring, so unchecked: {', '.join(missing)}")
    if bad:
        print("  SECTOR SELF-TEST FAILED:")
        for b in bad:
            print(f"    {b}")
        return False
    print(f"  sector self-test: {len(SECTOR_EXPECTED) - len(missing)} suburbs "
          f"land on the expected side of the city")
    return True


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
        sec = sector_for(s["lat"], s["lng"], brg)
        kept.append({
            "name": s["name"],
            "pc": s["pc"],
            "lat": s["lat"],
            "lng": s["lng"],
            "sa2": s["sa2"],
            "kmCbd": round(km_cbd, 1),
            "kmComo": round(haversine_km(como[0], como[1], s["lat"], s["lng"]), 1),
            "sector": sec,
            "bank": "south" if south_of_river(s["lat"], s["lng"]) else "north",
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
            "sector_rule": "The Swan decides first, then the bearing from the "
                           "CBD. South of the river is S, except the eastern run "
                           "(Belmont, Kewdale, Forrestfield, High Wycombe) which "
                           "is E. North of the river splits N / E / W by bearing. "
                           "This is why Victoria Park and Kenwick read south, and "
                           "Dalkeith reads west, where a plain compass quadrant "
                           "got all four wrong.",
            "sectors": {"N": "north of the river, above the city",
                        "E": "the Bayswater to Guildford run, plus the "
                             "Belmont / airport / foothills run south of the Swan",
                        "S": "south of the river",
                        "W": "the western suburbs, Subiaco out to North Fremantle"},
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
    for name in ("N", "E", "S", "W"):
        names = [s["name"] for s in kept if s["sector"] == name]
        print(f"  {name}: {len(names):>3}  {', '.join(names[:8])}"
              + (" ..." if len(names) > 8 else ""))
    print(f"Wrote {OUT}")
    return 0 if selftest(kept) else 1


if __name__ == "__main__":
    raise SystemExit(main())
