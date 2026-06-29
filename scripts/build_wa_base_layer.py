#!/usr/bin/env python3
"""
build_wa_base_layer.py - build data/wa_suburbs.json, the WA-wide suburb base
layer that lets the model anchor ANYWHERE in WA (not just the 14 curated
suburbs).

Source: matthewproctor/australianpostcodes - a community/public-domain database
of Australian postcodes with per-locality geolocation (the Lat_precise /
Long_precise columns are suburb-level, unlike the postcode-centroid lat/long).
Public domain, so safe to vendor.

This produces ONLY the free, factual layer: suburb name, postcode, precise
lat/lng, and the ABS SA2 name (for later demographic joins). Medians, scores and
listings are layered on separately (live listings + Landgate/REIWA), never
invented here.

Run: python3 scripts/build_wa_base_layer.py
Stdlib only. Re-downloads the source; commit the JSON output so the build does
not depend on the network.
"""
import csv
import io
import json
import os
import subprocess
import tempfile

SRC = "https://raw.githubusercontent.com/matthewproctor/australianpostcodes/master/australian_postcodes.csv"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "wa_suburbs.json")


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    # Local override (e.g. WA_CSV=/path/to/australian_postcodes.csv) avoids a
    # re-download; otherwise fetch via curl (urllib truncates through some proxies).
    local = os.environ.get("WA_CSV")
    if local and os.path.exists(local):
        print(f"Reading {local} ...")
        raw = open(local, encoding="utf-8", errors="replace").read()
    else:
        print(f"Downloading {SRC} via curl ...")
        tmp = os.path.join(tempfile.gettempdir(), "australian_postcodes.csv")
        subprocess.run(["curl", "-sS", "-m", "120", "-o", tmp, SRC], check=True)
        raw = open(tmp, encoding="utf-8", errors="replace").read()
    rows = list(csv.DictReader(io.StringIO(raw)))
    print(f"  {len(rows)} rows")

    seen = {}
    for r in rows:
        if (r.get("state") or "").strip().upper() != "WA":
            continue
        if (r.get("type") or "").strip().lower() in ("post office boxes", "lvr"):
            continue
        name = (r.get("locality") or "").strip().title()
        lat = _f(r.get("Lat_precise"))
        lng = _f(r.get("Long_precise"))
        if lat is None or lng is None:  # fall back to postcode centroid
            lat, lng = _f(r.get("lat")), _f(r.get("long"))
        if not name or lat in (None, 0) or lng in (None, 0):
            continue
        if name not in seen:
            seen[name] = {
                "name": name,
                "pc": (r.get("postcode") or "").strip(),
                "lat": round(lat, 5),
                "lng": round(lng, 5),
                "sa2": (r.get("SA2_NAME_2021") or "").strip(),
            }

    suburbs = sorted(seen.values(), key=lambda s: s["name"])
    out = {
        "source": "matthewproctor/australianpostcodes (public domain); ABS SA2 names",
        "note": "Free, factual base layer: name, postcode, precise lat/lng, ABS SA2. "
        "Medians, scores and listings are layered on elsewhere, never invented here.",
        "count": len(suburbs),
        "suburbs": suburbs,
    }
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=0)
        fh.write("\n")
    print(f"Wrote {len(suburbs)} WA suburbs to data/wa_suburbs.json")


if __name__ == "__main__":
    main()
