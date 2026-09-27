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
# A rotating sweep refreshes a slice of the ring each day, so the page is built
# from a rolling window rather than from one run. Anything not re-confirmed
# inside this many days is dropped: with the default slice the whole ring cycles
# in about nine days, so fourteen leaves headroom for a missed run without ever
# showing a listing that has not been checked in a fortnight.
WINDOW_DAYS = int(os.environ.get("WINDOW_DAYS", 14))
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


def interleave_by_sector(suburbs):
    """Round-robin the sweep across north, east, south and west.

    This is not cosmetic. The ring file is grouped by sector for humans to read,
    and sweeping it in that order means any early stop, a rate limit, a timeout,
    a cancelled job, silently amputates whole directions: the 2026-09-02 run hit
    its API limit partway through and published 67 eastern listings, 5 northern
    and nothing at all from the south or west, having never searched Como,
    Bentley or Fremantle. Taking one suburb from each sector in turn, nearest
    the CBD first, means a sweep that covers only half the ring still covers all
    four sides of the city, and the meta records what was missed.
    """
    lanes = {}
    for s in suburbs:
        lanes.setdefault(s["sector"], []).append(s)
    if not lanes:
        return []
    for lane in lanes.values():
        lane.sort(key=lambda x: x["kmCbd"])

    # Plain round-robin looks right and is not: the lanes are different lengths
    # (54 southern suburbs against 21 western), so once the short lanes run out
    # the tail of the list is pure south, and a daily slice landing there covers
    # one direction. Instead each suburb is placed at its FRACTIONAL position
    # within its own lane, and the lanes are merged on that fraction. Every lane
    # is then spread evenly over the whole order, so any run of consecutive
    # suburbs mirrors the ring's real composition and, just as importantly,
    # every lane finishes in the same number of days.
    spread = []
    for sec in sorted(lanes):
        lane = lanes[sec]
        for i, s in enumerate(lane):
            spread.append(((i + 0.5) / len(lane), sec, s))
    spread.sort(key=lambda t: (t[0], t[1]))
    return [t[2] for t in spread]


def rotation_offset(cap, total):
    """Where today's slice starts, derived from the date.

    A rotating sweep needs to start somewhere different each day, and GitHub
    Actions keeps no state between runs. Deriving it from the day number means
    no cursor to store and no drift if a run is skipped: consecutive days
    advance by one slice, and the whole ring is covered in total/cap days.
    """
    if cap <= 0 or total <= 0:
        return 0
    day = datetime.date.today().toordinal()
    return (day * cap) % total


def load_ring():
    with open(RING_PATH) as fh:
        ring = json.load(fh)
    # Interleave FIRST, so every slice taken out of this list is already
    # balanced across north, east, south and west.
    targets = interleave_by_sector(ring["suburbs"])
    cap = int(os.environ.get("SUBURB_CAP", 0))
    env_offset = os.environ.get("SUBURB_OFFSET")
    offset = int(env_offset) if env_offset else rotation_offset(cap, len(targets))
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


def carry_over(fresh_suburbs, today):
    """Listings from previous runs that this run did not re-check.

    A rotating sweep only refreshes a slice of the ring each day, so publishing
    just today's results would shrink the page from the whole of inner Perth to
    sixteen suburbs. Instead the feed is a rolling window: anything from a
    suburb searched today is replaced by today's answer, anything older than
    WINDOW_DAYS is dropped as too stale to show, and the rest is carried.

    Carried listings keep the value fields computed when they were last seen,
    because those were measured against that suburb's asking market at the time
    and re-deriving them against a pool we did not refresh would be inventing.
    """
    try:
        with open(OUT_PATH) as fh:
            prev = json.load(fh).get("listings", [])
    except (OSError, ValueError):
        return [], 0, 0

    kept, superseded, expired = [], 0, 0
    for p in prev:
        if p.get("suburb") in fresh_suburbs:
            superseded += 1
            continue
        checked = p.get("checked")
        age = None
        if checked:
            try:
                age = (today - datetime.date.fromisoformat(checked)).days
            except ValueError:
                age = None
        if age is None or age > WINDOW_DAYS:
            expired += 1
            continue
        kept.append(p)
    return kept, superseded, expired


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


def write(listings, ring, attempted, coverage, stopped, failures, benches):
    priced = [b for b in benches.values() if b.get("price")]
    # "complete" means this run finished the slice it set out to search. On a
    # rotating sweep a slice IS the intended run, so a healthy rotation must not
    # trip the page's unfinished-sweep warning; only an early stop should.
    complete = not stopped
    cap = int(os.environ.get("SUBURB_CAP", 0))
    rotating = cap > 0 and cap < ring["meta"]["count"]
    window_subs = sorted({p["suburb"] for p in listings})
    out = {
        "meta": {
            "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
            "source": "realty-in-au",
            "scope": "perth-ring",
            "valued": "local-asking",
            "radius_km": ring["meta"]["radius_km"],
            "suburbs_searched": attempted,
            "suburbs_in_ring": ring["meta"]["count"],
            "suburbs_failed": failures,
            "sweep_complete": complete,
            "stopped_early": stopped,
            "coverage": coverage,
            "rotating": rotating,
            "slice_size": cap or ring["meta"]["count"],
            "window_days": WINDOW_DAYS if rotating else None,
            "cycle_days": (ring["meta"]["count"] + cap - 1) // cap if rotating else 1,
            "suburbs_in_window": len(window_subs),
            "note": "Best-value houses across the inner-Perth ring (every "
                    "residential suburb within "
                    f"{ring['meta']['radius_km']:g}km of the CBD, north, east, "
                    "south and west). Brief unchanged: houses, 3+ beds, up to "
                    "$1.1M, land favoured. Ranked by how far under comparable "
                    "CURRENT listings in the same suburb each one is priced, "
                    "blended with fit to the buyer's brief."
                    + (f" A slice of {cap} suburbs is refreshed each day, so the "
                       f"whole ring cycles about every "
                       f"{(ring['meta']['count'] + cap - 1) // cap} days and the "
                       f"page shows a rolling {WINDOW_DAYS}-day window; each "
                       f"listing carries the date it was last checked."
                       if rotating else " Refreshed daily."),
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

    # Stamp the date these listings were actually checked, so the rolling window
    # can age them correctly. A pull with no date on it is treated as being as
    # old as the file says it is, never as fresh.
    stamp = doc.get("meta", {}).get("generated")
    pools, dropped = {}, 0
    for p in doc.get("listings", []):
        p.setdefault("checked", stamp)
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

    # A feed pulled before the coverage fields existed carries a
    # suburbs_searched that was computed as (ring size - failures), so a sweep
    # that died after 41 suburbs still claimed 137. We cannot recover the true
    # figure here, but a whole sector with zero listings out of dozens of
    # suburbs is not a quiet market, it is a sector that was never searched. Flag
    # it rather than leave a number that flatters the pull.
    if "sweep_complete" not in doc["meta"]:
        present = {p.get("sector") for p in scored}
        empty = [k for k in ("N", "E", "S", "W") if k not in present]
        doc["meta"]["suburbs_searched"] = None
        doc["meta"]["sweep_complete"] = not empty
        if empty:
            doc["meta"]["stopped_early"] = (
                "this pull predates coverage tracking and returned nothing at "
                "all from " + "/".join(empty) + ", so it did not finish the ring")
            print(f"  flagged as an incomplete sweep: no listings from "
                  f"{'/'.join(empty)}")
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
    total = ring["meta"]["count"]
    if len(targets) < total:
        cycle = (total + len(targets) - 1) // len(targets)
        print(f"  rotating: the whole ring is covered every {cycle} days; the "
              f"page shows a rolling {WINDOW_DAYS}-day window, so every suburb "
              f"is re-checked well inside it")
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

    # Count what was actually ATTEMPTED, per sector. The old code reported
    # len(targets) - failures, which claimed 137 of 143 suburbs searched on a run
    # that stopped after 41 and never touched the south or west at all. A number
    # that flatters a broken sweep is worse than no number.
    total_by_sector = {}
    for s in ring["suburbs"]:
        total_by_sector[s["sector"]] = total_by_sector.get(s["sector"], 0) + 1
    tried_by_sector = {k: 0 for k in total_by_sector}

    pools, logged_shape, failures, stopped = {}, False, 0, None
    for i, s in enumerate(targets, 1):
        tried_by_sector[s["sector"]] = tried_by_sector.get(s["sector"], 0) + 1
        try:
            payload = search_suburb(key, s["name"], s["pc"])
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="ignore")[:200]
            print(f"  warn: {s['name']} HTTP {e.code}: {detail}", file=sys.stderr)
            failures += 1
            if e.code in (401, 403) or (e.code == 429 and failures > 5):
                stopped = ("the API refused further calls (HTTP "
                           f"{e.code}: bad key, or the plan's quota is spent)")
                print(f"  STOPPING the sweep after {i} of {len(targets)} "
                      f"suburbs: {stopped}", file=sys.stderr)
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

    attempted = sum(tried_by_sector.values())
    coverage = {k: {"searched": tried_by_sector.get(k, 0), "in_ring": v}
                for k, v in sorted(total_by_sector.items())}
    if stopped:
        print(f"  coverage after the stop: "
              + ", ".join(f"{k} {c['searched']}/{c['in_ring']}"
                          for k, c in coverage.items()), file=sys.stderr)
    if not pools:
        # A green tick on a job that published nothing is how the feed sat
        # untouched for 25 days while the page still looked live. Exit 0 so the
        # committed data stays put, but annotate the run so the Actions tab
        # shows a warning instead of a clean pass.
        why = stopped or ("the API returned no matching houses, so a response "
                          "shape may have changed")
        print(f"::warning title=Listings not refreshed::No listings published: "
              f"{why}. The page is still serving data from the last good run.")
        print("No live listings parsed. Keeping the committed data so the page "
              "does not go blank. Check the [shape] logs above and adjust field "
              "paths in normalise()/_image() if needed.")
        return 0

    scored, benches = score_pools(pools, ring_by_name, med)
    today = datetime.date.today()
    for p in scored:
        p["checked"] = today.isoformat()

    carried, superseded, expired = carry_over(set(pools), today)
    if carried or superseded or expired:
        print(f"  rolling window: {len(carried)} carried from earlier runs, "
              f"{superseded} replaced by today's search, {expired} dropped as "
              f"older than {WINDOW_DAYS} days")
    listings = select(scored + carried)
    new_count = mark_new(listings)

    sec_counts = {}
    for p in listings:
        sec_counts[p["sector"]] = sec_counts.get(p["sector"], 0) + 1
    print(f"\n{len(scored)} listings in brief across {len(pools)} suburbs; "
          f"publishing {len(listings)}.")
    print("  by sector (published / suburbs searched / suburbs in ring): "
          + ", ".join(f"{k}={sec_counts.get(k, 0)}/{coverage[k]['searched']}"
                      f"/{coverage[k]['in_ring']}" for k in sorted(coverage)))
    if stopped:
        print(f"  WARNING: incomplete sweep, {stopped}. The page will say so.")
    print(f"  {sum(1 for p in listings if p['bargain'])} bargains, "
          f"{new_count} new since the last refresh, "
          f"{sum(1 for p in listings if not p['curated'])} outside the curated 14.")

    write(listings, ring, attempted, coverage, stopped, failures, benches)
    print(f"Wrote {len(listings)} listings to data/listings.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
