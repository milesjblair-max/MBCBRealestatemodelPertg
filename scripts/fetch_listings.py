#!/usr/bin/env python3
"""
fetch_listings.py - refresh data/listings.json with the best-value for-sale
houses across the inner-Perth ring, WITH photos, via the "Realty in AU" API
(apidojo) on RapidAPI.

WHAT CHANGED: this used to search only the 8 curated in-budget suburbs, so a
genuine bargain two suburbs over was invisible. It now sweeps every residential
suburb within 15km of the Perth CBD (north, east, south and west: see
data/perth_ring.json, built by scripts/build_perth_ring.py) and ranks what it
finds by how far under the local asking market each listing is priced.

The brief is unchanged: houses, 3+ beds, up to $1.1M, land favoured. What
changed is the map, not the buyer. Every listing still carries its distance to
the Como anchor, and buyer-fit still counts for part of the ranking, so "best
bargain" means a bargain that suits this family, not just a cheap house.

Valuation is done by model/value.py against comparable CURRENT listings in the
same suburb, never against an invented median. Read that file's docstring for
what the discount does and does not claim.

Run by .github/workflows/refresh-listings.yml daily.

DATA SOURCE NOTE: "Realty in AU" surfaces realestate.com.au listing data through
a third-party RapidAPI endpoint. The owner has chosen this for a private,
personal tool shared only with their partner. It is not an official REA feed.

Credentials (repo secret):
    RAPIDAPI_KEY        (required - your RapidAPI key)
    RAPIDAPI_HOST       (optional - defaults to realty-in-au.p.rapidapi.com)

Tuning (all optional environment variables):
    RING_RADIUS_KM      informational; rebuild the ring to actually change it
    SUBURB_CAP          search only the first N ring suburbs (0 = all, default)
    SUBURB_OFFSET       start the sweep N suburbs in, for a rotating sweep
    TOTAL_CAP           how many listings to publish (default 72)

With NO key present the script exits 0 WITHOUT touching the committed data, so
the page keeps showing the last good pull. Standard library only.

    python3 scripts/fetch_listings.py             # live sweep (needs a key)
    python3 scripts/fetch_listings.py --rescore   # re-value the committed feed,
                                                  # no API calls, no new listings
    python3 scripts/fetch_listings.py --plan      # print the sweep plan and exit
"""
import datetime
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
sys.path.insert(0, os.path.join(HERE, "..", "model"))
import value as V  # noqa: E402

RING_PATH = os.path.join(DATA, "perth_ring.json")
SUBURBS_PATH = os.path.join(DATA, "suburbs.json")
OUT_PATH = os.path.join(DATA, "listings.json")

MAX_PRICE = 1_100_000
MIN_BEDS = 3
MIN_LAND = 500
PER_SUBURB = 4                                   # cap so no one suburb floods the page
TOTAL_CAP = int(os.environ.get("TOTAL_CAP", 72))
PER_SECTOR_FLOOR = 10                            # keep all four directions visible
PAGE_SIZE = 30                                   # bigger page = better benchmark
THROTTLE_S = 0.25                                # be polite across ~140 calls
IMG_SIZE = "640x480"                             # fills the {size} slot in reastatic URLs

HOST = os.environ.get("RAPIDAPI_HOST", "realty-in-au.p.rapidapi.com")
LIST_URL = f"https://{HOST}/properties/list"


def _get(url, headers, retries=2):
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            # 429 is the quota talking; back off once rather than hammering it
            if e.code == 429 and attempt < retries:
                time.sleep(2 ** (attempt + 1))
                continue
            raise
    raise RuntimeError("unreachable")


def _dig(obj, *paths, default=None):
    """Return the first present value among dotted paths (a.b.c)."""
    for path in paths:
        cur = obj
        ok = True
        for key in path.split("."):
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok and cur not in (None, ""):
            return cur
    return default


def _flatten_results(payload):
    """Pull listing dicts out of the response, whatever the wrapper shape."""
    out = []
    tiers = payload.get("tieredResults") or payload.get("results") or []
    if isinstance(tiers, list):
        for t in tiers:
            if isinstance(t, dict) and isinstance(t.get("results"), list):
                out.extend(t["results"])
            elif isinstance(t, dict) and ("address" in t or "bedrooms" in t):
                out.append(t)
    emb = _dig(payload, "_embedded.listings", "data.results")
    if isinstance(emb, list):
        out.extend(emb)
    return out


_IMG_EXT = re.compile(r"\.(jpe?g|png|webp)(\?|$)", re.I)


def _img_from(obj):
    """Recursively find a usable reastatic photo URL anywhere in the object."""
    if isinstance(obj, dict):
        # a {server, uri/url} pair is REA's common image shape
        server = obj.get("server")
        uri = obj.get("uri") or obj.get("url") or obj.get("templatedUrl")
        if isinstance(server, str) and isinstance(uri, str):
            joined = server.rstrip("/") + "/" + uri.lstrip("/")
            if "{size}" in joined:
                return joined.replace("{size}", IMG_SIZE)
            if "reastatic" in joined:
                return joined
        for v in obj.values():
            r = _img_from(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _img_from(v)
            if r:
                return r
    elif isinstance(obj, str):
        if "reastatic" in obj and ("{size}" in obj or _IMG_EXT.search(obj)):
            return obj.replace("{size}", IMG_SIZE)
    return None


def _fix_reastatic(url):
    """reastatic URLs need a size segment (e.g. 640x480) after the domain."""
    if not url:
        return None
    m = re.match(r"(https://[^/]*reastatic\.net)/(.+)", url, re.I)
    if not m:
        return url
    domain, rest = m.group(1), m.group(2)
    if re.match(r"\d+x\d+$", rest.split("/")[0]):
        return url
    return f"{domain}/{IMG_SIZE}/{rest}"


def _image(listing):
    """Best-effort main photo URL, sized so it actually loads."""
    tmpl = _dig(listing, "mainPhoto.templatedUrl", "mainPhoto.url", "image.templatedUrl")
    found = (tmpl.replace("{size}", IMG_SIZE) if isinstance(tmpl, str) and "reastatic" in tmpl
             else (_img_from(listing.get("mainPhoto"))
                   or _img_from(listing.get("images"))
                   or _img_from(listing.get("media"))
                   or _img_from(listing)))
    return _fix_reastatic(found)


def _int(v):
    try:
        return int(str(v).strip())
    except Exception:
        return None


def _parse_price(text):
    """Pull a dollar figure out of REA free-text price; None if there isn't one."""
    if not text:
        return None
    m = re.search(r"\$\s*([\d][\d,.]*)\s*([kKmM])?", str(text))
    if not m:
        return None
    try:
        n = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    s = (m.group(2) or "").lower()
    if s == "k":
        n *= 1e3
    elif s == "m":
        n *= 1e6
    elif n < 100:
        n *= 1e6
    return int(round(n)) if n >= 50000 else None


PT_DENY = ("unit", "apartment", "flat", "studio", "block of units",
           "retirement", "new apartments")
UO_TEXT = ("u/o", "under offer", "under contract", "deposit taken", "sold",
           "leased", "now settled", "on hold", "withdrawn", "off market",
           "not available")
# A street number like "2/94 Wendouree Rd" is a strata lot: a duplex half, villa
# or townhouse listed under propertyType "house". These are the single biggest
# source of fake bargains, because they sit well under the suburb's asking
# market for the obvious reason that they are half a block, and they almost
# never publish a land size to give the game away.
STRATA_ADDR = re.compile(r"^\s*(unit\s*)?\d+\s*/")
# "From $X", "Offers above $X" and friends are a FLOOR, not an ask. Treated as
# such in model/value.py so a marketing tactic does not read as a discount.
GUIDE_TEXT = ("from ", "offers above", "offers over", "offers from", "starting",
              "above $", "over $", "oio", "from$")


def normalise(items, sub):
    """Raw API rows -> the brief-fitting listings for one suburb.

    Returns the WHOLE surviving pool, not a display slice: model/value.py needs
    every comparable it can get to benchmark the suburb honestly. The per-suburb
    display cut happens after scoring.
    """
    out = []
    suburb, pc = sub["name"], sub["pc"]
    for L in items:
        if not isinstance(L, dict):
            continue
        addr_raw = _dig(L, "address.streetAddress", "address.displayAddress", "title")
        price_txt = _dig(L, "price.display", "priceText", "price.label", default="Contact agent")
        price_n = _int(_dig(L, "price.value", "price.from", "priceDetails.price")) or _parse_price(price_txt)
        beds = _int(_dig(L, "bedrooms", "features.general.bedrooms", "general.bedrooms"))
        baths = _int(_dig(L, "bathrooms", "features.general.bathrooms"))
        cars = _int(_dig(L, "carspaces", "carSpaces", "features.general.carspaces",
                         "features.general.parkingSpaces"))
        land = _int(_dig(L, "landSize.value", "landSize.displayValue", "propertySizes.land.displayValue"))
        ptype = str(_dig(L, "propertyType", default="")).lower()
        if any(d in ptype for d in PT_DENY):
            continue                                   # skip units/apartments; we want houses
        if any(u in (price_txt or "").lower() for u in UO_TEXT):
            continue                                   # skip under-offer / sold
        if land is not None and land < 450:
            continue                                   # below the 500sqm brief (small tolerance)
        if STRATA_ADDR.match(str(addr_raw or "")):
            continue                                   # duplex half / villa, not a 500sqm house
        if price_n and price_n > MAX_PRICE:
            continue
        if beds is not None and beds < MIN_BEDS:
            continue
        slug = _dig(L, "prettyUrl", "_links.canonical.href", "listingUrl", "url")
        if isinstance(slug, str) and slug.startswith("http"):
            url = slug
        elif isinstance(slug, str):
            url = "https://www.realestate.com.au" + ("" if slug.startswith("/") else "/") + slug
        else:
            url = f"https://www.realestate.com.au/buy/in-{suburb.lower().replace(' ', '+')}%2c+wa+{pc}/list-1"
        addr = addr_raw or f"{suburb} {pc}"
        guide = any(g in (price_txt or "").lower() for g in GUIDE_TEXT)
        # 'meets' requires KNOWN values that satisfy each hard filter. Unknown is
        # NOT a pass: null land does not meet a land minimum, it is just unknown.
        meets = bool(beds is not None and beds >= MIN_BEDS
                     and land is not None and land >= MIN_LAND
                     and price_n is not None and price_n <= MAX_PRICE)
        out.append({
            "suburb": suburb, "pc": pc, "price": price_n, "priceText": price_txt,
            "beds": beds, "baths": baths, "cars": cars, "land": land,
            "address": addr, "image": _image(L), "url": url, "direct": True,
            "meets": meets, "guide": guide,
            "sector": sub["sector"], "kmCbd": sub["kmCbd"], "kmComo": sub["kmComo"],
            "curated": sub["curated"],
        })
    return out


def search_suburb(key, suburb, pc):
    loc = f"{suburb}, WA {pc}"
    params = {
        "channel": "buy", "page": "1", "pageSize": str(PAGE_SIZE),
        "searchLocation": loc, "search": loc, "surroundingSuburbs": "false",
        "sortType": "relevance", "maximumPrice": str(MAX_PRICE),
        "minimumBedrooms": str(MIN_BEDS), "propertyTypes": "house",
    }
    url = LIST_URL + "?" + urllib.parse.urlencode(params)
    headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": HOST}
    return _get(url, headers)


# ---------------------------------------------------------------------------


def load_ring():
    with open(RING_PATH) as fh:
        ring = json.load(fh)
    targets = ring["suburbs"]
    offset = int(os.environ.get("SUBURB_OFFSET", 0))
    cap = int(os.environ.get("SUBURB_CAP", 0))
    if offset:
        targets = targets[offset:] + targets[:offset]
    if cap > 0:
        targets = targets[:cap]
    return ring, targets


def curated_medians():
    """The researched medians for the 14 curated suburbs, used only as a
    secondary cross-check ("also under the researched suburb median"), never as
    the primary benchmark: a whole-market median is not comparable with the
    capped, 3-bed-plus asking pool this feed measures."""
    with open(SUBURBS_PATH) as fh:
        return {s["name"]: s for s in json.load(fh)["suburbs"] if s.get("mlo")}


def score_pools(pools, ring_by_name, med):
    """Benchmark every suburb, then value every listing in it."""
    benches = {name: V.suburb_benchmark(pool) for name, pool in pools.items()}
    sectors = V.sector_benchmark(pools, ring_by_name)
    scored = []
    for name, pool in pools.items():
        sub = ring_by_name.get(name, {})
        fb = sectors.get(sub.get("sector"))
        for p in pool:
            V.score_listing(p, benches[name], fb, sub.get("kmComo"))
            c = med.get(name)
            # a curated suburb gives us a second, independent check
            p["underMedian"] = bool(c and p.get("price")
                                    and p["price"] <= c["mlo"] * 1000)
            p["reason"] = V.explain(p, name, sub.get("kmComo"))
            scored.append(p)
    return scored, benches


def select(scored):
    """Publish the best-ranked listings, with every sector represented.

    A pure top-N by rank can hand the whole page to one side of the city on a
    quiet week. This takes each sector's best PER_SECTOR_FLOOR first, then fills
    the remainder on rank, so north, east, south and west are all visible.
    """
    for p in scored:
        p.setdefault("rank", 0)
    by_sector = {}
    for p in scored:
        by_sector.setdefault(p.get("sector", "?"), []).append(p)

    chosen, seen = [], set()
    for sec in sorted(by_sector):
        picks = sorted(by_sector[sec], key=lambda x: -x["rank"])
        per_sub = {}
        for p in picks:
            if len(per_sub.get(p["suburb"], [])) >= PER_SUBURB:
                continue
            per_sub.setdefault(p["suburb"], []).append(p)
            chosen.append(p)
            seen.add(p["url"])
            if sum(1 for c in chosen if c.get("sector") == sec) >= PER_SECTOR_FLOOR:
                break

    rest = sorted((p for p in scored if p["url"] not in seen),
                  key=lambda x: -x["rank"])
    per_sub = {}
    for p in chosen:
        per_sub[p["suburb"]] = per_sub.get(p["suburb"], 0) + 1
    for p in rest:
        if len(chosen) >= TOTAL_CAP:
            break
        if per_sub.get(p["suburb"], 0) >= PER_SUBURB:
            continue
        per_sub[p["suburb"]] = per_sub.get(p["suburb"], 0) + 1
        chosen.append(p)

    chosen.sort(key=lambda x: -x["rank"])
    return chosen[:TOTAL_CAP]


def mark_new(listings):
    """Flag listings that were not in yesterday's file, keyed on property URL."""
    prev = set()
    try:
        with open(OUT_PATH) as fh:
            for x in json.load(fh).get("listings", []):
                if x.get("url"):
                    prev.add(x["url"])
    except (OSError, ValueError):
        pass
    for x in listings:
        x["new"] = bool(x.get("url") and x["url"] not in prev)
    return sum(1 for x in listings if x["new"])


def write(listings, ring, searched, benches):
    priced = [b for b in benches.values() if b.get("price")]
    out = {
        "meta": {
            "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
            "source": "realty-in-au",
            "scope": "perth-ring",
            "valued": "local-asking",
            "radius_km": ring["meta"]["radius_km"],
            "suburbs_searched": searched,
            "suburbs_in_ring": ring["meta"]["count"],
            "note": "Best-value houses across the inner-Perth ring (every "
                    "residential suburb within "
                    f"{ring['meta']['radius_km']:g}km of the CBD, north, east, "
                    "south and west). Brief unchanged: houses, 3+ beds, up to "
                    "$1.1M, land favoured. Ranked by how far under comparable "
                    "CURRENT listings in the same suburb each one is priced, "
                    "blended with fit to the buyer's brief. Refreshed daily.",
            "value_note": "A discount is measured against the median ask of "
                          "comparable listings on the market now in that suburb, "
                          "not against a suburb median and not against a "
                          "valuation. Listings with no published price are never "
                          "treated as cheap. General information, not advice.",
            "criteria": {"max_price": MAX_PRICE, "min_land": MIN_LAND,
                         "min_beds": MIN_BEDS, "types": ["House"]},
            "benchmarks": {"suburbs_priced": len(priced)},
        },
        "listings": listings,
    }
    with open(OUT_PATH, "w") as fh:
        json.dump(out, fh, indent=2)
        fh.write("\n")


def rescore():
    """Re-value the committed feed with no API calls.

    Used after a change to model/value.py so the page reflects the new logic
    immediately instead of waiting for tomorrow's sweep. It adds no listings and
    invents nothing: it re-derives the value fields from data already committed.
    """
    with open(OUT_PATH) as fh:
        doc = json.load(fh)
    with open(RING_PATH) as fh:
        ring = json.load(fh)
    ring_by_name = {s["name"]: s for s in ring["suburbs"]}
    med = curated_medians()

    pools, dropped = {}, 0
    for p in doc.get("listings", []):
        # apply the same quality filters a live sweep applies, so a re-score
        # cleans out strata lots the older, looser pull let through
        if STRATA_ADDR.match(str(p.get("address") or "")):
            dropped += 1
            continue
        if p.get("guide") is None:
            p["guide"] = any(g in (p.get("priceText") or "").lower() for g in GUIDE_TEXT)
        sub = ring_by_name.get(p["suburb"])
        if sub:
            p["sector"], p["kmCbd"] = sub["sector"], sub["kmCbd"]
            p["kmComo"], p["curated"] = sub["kmComo"], sub["curated"]
        pools.setdefault(p["suburb"], []).append(p)

    scored, benches = score_pools(pools, ring_by_name, med)
    scored.sort(key=lambda x: -x["rank"])
    doc["listings"] = scored
    # The valuation fields are now present even though the geography of this
    # pull predates the ring sweep, so mark the two facts separately: the page
    # keys its display off `valued`, and only claims a Perth-wide search when
    # `scope` says the sweep actually was one.
    doc["meta"]["valued"] = "local-asking"
    doc["meta"]["rescored"] = datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%d")
    with open(OUT_PATH, "w") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    outside = sum(1 for p in scored if not p.get("curated"))
    print(f"Re-scored {len(scored)} committed listings across "
          f"{len(pools)} suburbs ({outside} outside the curated 14); "
          f"dropped {dropped} strata lots.")
    print(f"  {sum(1 for p in scored if p.get('bargain'))} flagged as bargains, "
          f"{sum(1 for p in scored if p.get('odd'))} flagged as odd pricing.")
    return 0


def plan():
    ring, targets = load_ring()
    by_sector = {}
    for s in targets:
        by_sector[s["sector"]] = by_sector.get(s["sector"], 0) + 1
    print(f"Ring radius {ring['meta']['radius_km']:g}km, "
          f"{ring['meta']['count']} suburbs in the ring.")
    print(f"This sweep would search {len(targets)} suburbs = "
          f"{len(targets)} API calls per run.")
    print(f"  daily: ~{len(targets) * 30} calls/month")
    for sec in sorted(by_sector):
        print(f"  {sec}: {by_sector[sec]}")
    return 0


def main(argv):
    if "--plan" in argv:
        return plan()
    if "--rescore" in argv:
        return rescore()

    key = os.environ.get("RAPIDAPI_KEY")
    if not key:
        print("No RAPIDAPI_KEY secret. Leaving the committed data untouched.")
        return 0

    ring, targets = load_ring()
    ring_by_name = {s["name"]: s for s in ring["suburbs"]}
    med = curated_medians()
    print(f"Realty in AU via {HOST}: sweeping {len(targets)} suburbs within "
          f"{ring['meta']['radius_km']:g}km of the Perth CBD "
          f"(N/E/S/W), {PAGE_SIZE} results each.")

    pools, logged_shape, failures = {}, False, 0
    for i, s in enumerate(targets, 1):
        try:
            payload = search_suburb(key, s["name"], s["pc"])
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="ignore")[:200]
            print(f"  warn: {s['name']} HTTP {e.code}: {detail}", file=sys.stderr)
            failures += 1
            if e.code in (401, 403) or (e.code == 429 and failures > 5):
                print("  stopping the sweep: the API is refusing calls "
                      "(bad key or quota exhausted).", file=sys.stderr)
                break
            continue
        except Exception as e:
            print(f"  warn: {s['name']} failed: {e}", file=sys.stderr)
            failures += 1
            continue
        items = _flatten_results(payload)
        if not logged_shape and items:
            print(f"  [shape] top-level keys: {list(payload.keys())[:12]}")
            print(f"  [shape] first listing keys: {list(items[0].keys())[:25]}")
            print(f"  [shape] first image resolved to: {_image(items[0])}")
            logged_shape = True
        got = normalise(items, s)
        if got:
            pools[s["name"]] = got
        if i % 20 == 0 or got:
            print(f"  [{i}/{len(targets)}] {s['sector']} {s['name']} {s['pc']}: "
                  f"{len(items)} raw, {len(got)} in brief")
        time.sleep(THROTTLE_S)

    searched = len(targets) - failures
    if not pools:
        print("No live listings parsed. Keeping the committed data so the page "
              "does not go blank. Check the [shape] logs above and adjust field "
              "paths in normalise()/_image() if needed.")
        return 0

    scored, benches = score_pools(pools, ring_by_name, med)
    listings = select(scored)
    new_count = mark_new(listings)

    sec_counts = {}
    for p in listings:
        sec_counts[p["sector"]] = sec_counts.get(p["sector"], 0) + 1
    print(f"\n{len(scored)} listings in brief across {len(pools)} suburbs; "
          f"publishing {len(listings)}.")
    print(f"  by sector: " + ", ".join(f"{k}={v}" for k, v in sorted(sec_counts.items())))
    print(f"  {sum(1 for p in listings if p['bargain'])} bargains, "
          f"{new_count} new since the last refresh, "
          f"{sum(1 for p in listings if not p['curated'])} outside the curated 14.")

    write(listings, ring, searched, benches)
    print(f"Wrote {len(listings)} listings to data/listings.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
