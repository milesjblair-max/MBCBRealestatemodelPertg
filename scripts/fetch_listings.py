#!/usr/bin/env python3
"""
fetch_listings.py - refresh data/listings.json with real for-sale listings,
WITH photos, via the "Realty in AU" API (apidojo) on RapidAPI.

Run daily by .github/workflows/refresh-listings.yml. It searches the in-budget
target suburbs (from data/suburbs.json) for houses 3+ beds up to $1.1M, flags
bargains (below the suburb median), grabs the main photo, and writes
data/listings.json, which the tool fetch()es.

DATA SOURCE NOTE: "Realty in AU" surfaces realestate.com.au listing data through
a third-party RapidAPI endpoint. The owner has chosen this for a private,
personal tool shared only with their partner. It is not an official REA feed.

Credentials (repo secret):
    RAPIDAPI_KEY        (required - your RapidAPI key)
    RAPIDAPI_HOST       (optional - defaults to realty-in-au.p.rapidapi.com)

With NO key present the script exits 0 WITHOUT touching the committed sample, so
the page keeps showing the illustrative examples. Standard library only.

Because the exact response shape can vary, this script parses DEFENSIVELY and
logs what it found, so the first real run tells us if any field path needs a
tweak (check the workflow logs).
"""
import datetime
import json
import os
import re
import sys
import urllib.request
import urllib.parse
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
SUBURBS_PATH = os.path.join(DATA, "suburbs.json")
OUT_PATH = os.path.join(DATA, "listings.json")

MAX_PRICE = 1_100_000
MIN_BEDS = 3
MIN_LAND = 500
PER_SUBURB = 6
TOTAL_CAP = 40
SUBURB_CAP = 8           # keep API calls low to stay inside the free quota
IMG_SIZE = "640x480"     # fills the {size} slot in reastatic templated URLs

HOST = os.environ.get("RAPIDAPI_HOST", "realty-in-au.p.rapidapi.com")
LIST_URL = f"https://{HOST}/properties/list"


def _get(url, headers):
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode())


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


def normalise(items, suburb, pc, median_low_k):
    out = []
    for L in items:
        if not isinstance(L, dict):
            continue
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
        addr = _dig(L, "address.streetAddress", "address.displayAddress", "title", default=f"{suburb} {pc}")
        bargain = bool(price_n and median_low_k and price_n <= median_low_k * 1000 * 0.97)
        # 'meets' requires KNOWN values that satisfy each hard filter. Unknown is
        # NOT a pass: null land does not meet a land minimum, it is just unknown.
        # (Matches the MCP's live matchListings logic.)
        meets = bool(beds is not None and beds >= MIN_BEDS
                     and land is not None and land >= MIN_LAND
                     and price_n is not None and price_n <= MAX_PRICE)
        out.append({
            "suburb": suburb, "pc": pc, "price": price_n, "priceText": price_txt,
            "beds": beds, "baths": baths, "cars": cars, "land": land,
            "address": addr, "image": _image(L), "url": url, "direct": True,
            "bargain": bargain, "meets": meets,
            "reason": _reason(beds, land, price_n, median_low_k, bargain),
        })
        if len(out) >= PER_SUBURB:
            break
    return out


def _reason(beds, land, price, median_low_k, bargain):
    bits = []
    if beds:
        bits.append(f"{beds}-bed")
    if land:
        bits.append(f"{land}sqm")
    if price:
        bits.append(f"${price:,}")
    head = ", ".join(bits) if bits else "fits the brief"
    if bargain and median_low_k:
        return f"{head} - priced below the ~${median_low_k}k suburb median; potential bargain."
    return f"{head} - meets beds/land/budget criteria."


def search_suburb(key, suburb, pc):
    loc = f"{suburb}, WA {pc}"
    params = {
        "channel": "buy", "page": "1", "pageSize": "20",
        "searchLocation": loc, "search": loc, "surroundingSuburbs": "false",
        "sortType": "relevance", "maximumPrice": str(MAX_PRICE),
        "minimumBedrooms": str(MIN_BEDS), "propertyTypes": "house",
    }
    url = LIST_URL + "?" + urllib.parse.urlencode(params)
    headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": HOST}
    return _get(url, headers)


def main():
    key = os.environ.get("RAPIDAPI_KEY")
    if not key:
        print("No RAPIDAPI_KEY secret. Leaving the committed sample untouched.")
        return 0
    print(f"Using Realty in AU via {HOST}; searching target suburbs...")

    with open(SUBURBS_PATH) as fh:
        suburbs = json.load(fh)["suburbs"]
    targets = [s for s in suburbs if s.get("band")][:SUBURB_CAP]

    listings = []
    logged_shape = False
    for s in targets:
        try:
            payload = search_suburb(key, s["name"], s["pc"])
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="ignore")[:200]
            print(f"  warn: {s['name']} HTTP {e.code}: {detail}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"  warn: {s['name']} failed: {e}", file=sys.stderr)
            continue
        items = _flatten_results(payload)
        if not logged_shape:
            print(f"  [shape] top-level keys: {list(payload.keys())[:12]}")
            if items:
                print(f"  [shape] first listing keys: {list(items[0].keys())[:25]}")
                print(f"  [shape] propertyType={items[0].get('propertyType')!r}")
                print(f"  [shape] images repr: {repr(items[0].get('images'))[:320]}")
                print(f"  [shape] first image resolved to: {_image(items[0])}")
            logged_shape = True
        got = normalise(items, s["name"], s["pc"], s.get("mlo"))
        print(f"  {s['name']} {s['pc']}: {len(items)} raw, {len(got)} kept")
        listings.extend(got)

    listings.sort(key=lambda x: (not x["bargain"], x["price"] or 9_9_9_9_9_9_9))
    listings = listings[:TOTAL_CAP]

    # flag listings that are new since the previous refresh (yesterday's file),
    # keyed on the property URL (which carries the unique listing id)
    prev_urls = set()
    try:
        with open(OUT_PATH) as fh:
            for x in json.load(fh).get("listings", []):
                if x.get("url"):
                    prev_urls.add(x["url"])
    except (OSError, ValueError):
        pass
    for x in listings:
        x["new"] = bool(x.get("url") and x["url"] not in prev_urls)
    print(f"  {sum(1 for x in listings if x['new'])} new since last refresh")

    if not listings:
        print("No live listings parsed. Keeping the committed sample so the page "
              "does not go blank. Check the [shape] logs above and adjust field "
              "paths in normalise()/_image() if needed.")
        return 0

    out = {
        "meta": {
            "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
            "source": "realty-in-au",
            "note": "Live houses with photos from the Realty in AU API (RapidAPI) "
                    "matching the brief (3+ beds, <=$1.1M, in-budget suburbs). "
                    "Bargains = below the suburb median. Refreshed daily.",
            "criteria": {"max_price": MAX_PRICE, "min_land": MIN_LAND,
                         "min_beds": MIN_BEDS, "types": ["House"]},
        },
        "listings": listings,
    }
    with open(OUT_PATH, "w") as fh:
        json.dump(out, fh, indent=2)
        fh.write("\n")
    print(f"Wrote {len(listings)} listings (with photos) to data/listings.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
