#!/usr/bin/env python3
"""
fetch_listings.py - refresh data/listings.json with real property listings.

Run by .github/workflows/refresh-listings.yml on a daily schedule. It pulls
houses that fit the buyer's brief (3+ beds, <=$1.1M, in the in-budget target
suburbs from data/suburbs.json), flags bargains (priced below the suburb median)
and writes data/listings.json. The interactive tool fetch()es that file.

COMPLIANCE: this uses the official Domain Developer API - it does NOT scrape
realestate.com.au / Domain / REIWA (which their terms forbid). Provide Domain
OAuth client credentials as repo secrets:

    DOMAIN_CLIENT_ID, DOMAIN_CLIENT_SECRET   (preferred - client-credentials flow)
  or
    DOMAIN_ACCESS_TOKEN                       (a pre-minted bearer token)

With NO credentials present the script exits 0 WITHOUT touching the committed
sample file, so the page keeps showing the illustrative examples. Standard
library only.
"""
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
SUBURBS_PATH = os.path.join(DATA, "suburbs.json")
OUT_PATH = os.path.join(DATA, "listings.json")

MAX_PRICE = 1_100_000
MIN_BEDS = 3
MIN_LAND = 500
PER_SUBURB = 6
TOTAL_CAP = 40

TOKEN_URL = "https://auth.domain.com.au/v1/connect/token"
SEARCH_URL = "https://api.domain.com.au/v1/listings/residential/_search"


def _post(url, data, headers, is_json):
    body = json.dumps(data).encode() if is_json else urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")[:300]
        raise RuntimeError(f"HTTP {e.code} from {url}: {detail}") from None


def get_token():
    tok = os.environ.get("DOMAIN_ACCESS_TOKEN")
    if tok:
        return tok.strip()
    cid = os.environ.get("DOMAIN_CLIENT_ID")
    sec = os.environ.get("DOMAIN_CLIENT_SECRET")
    if not (cid and sec):
        return None
    resp = _post(
        TOKEN_URL,
        {"client_id": cid, "client_secret": sec,
         "grant_type": "client_credentials", "scope": "api_listings_read"},
        {"Content-Type": "application/x-www-form-urlencoded"},
        is_json=False,
    )
    return resp.get("access_token")


def search_suburb(token, suburb, pc):
    payload = {
        "listingType": "Sale",
        "propertyTypes": ["House"],
        "minBedrooms": MIN_BEDS,
        "maxPrice": MAX_PRICE,
        "pageSize": 20,
        "locations": [{
            "state": "WA", "suburb": suburb, "postCode": pc,
            "includeSurroundingSuburbs": False,
        }],
    }
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    return _post(SEARCH_URL, payload, headers, is_json=True)


def normalise(items, suburb, pc, median_low_k):
    out = []
    for it in items:
        if it.get("type") != "PropertyListing":
            continue
        L = it.get("listing", {})
        pd = L.get("propertyDetails", {}) or {}
        price = (L.get("priceDetails", {}) or {}).get("price")
        beds = pd.get("bedrooms")
        land = pd.get("landArea")
        if price and price > MAX_PRICE:
            continue
        if beds and beds < MIN_BEDS:
            continue
        slug = L.get("listingSlug") or L.get("seoUrl") or ""
        listing_id = L.get("id")
        # direct link to the exact property page when we have a slug or id
        if slug:
            url = "https://www.domain.com.au/" + slug.lstrip("/")
            direct = True
        elif listing_id:
            url = f"https://www.domain.com.au/{listing_id}"
            direct = True
        else:
            url = f"https://www.domain.com.au/sale/{suburb.lower().replace(' ', '-')}-wa-{pc}/"
            direct = False
        meets = bool(beds and beds >= MIN_BEDS and (not land or land >= MIN_LAND)
                     and (not price or price <= MAX_PRICE))
        bargain = bool(price and median_low_k and price <= median_low_k * 1000 * 0.97)
        out.append({
            "suburb": suburb, "pc": pc, "price": price,
            "priceText": (L.get("priceDetails", {}) or {}).get("displayPrice") or
                         (f"${price:,}" if price else "Contact agent"),
            "beds": beds, "baths": pd.get("bathrooms"), "cars": pd.get("carspaces"),
            "land": land, "address": pd.get("displayableAddress") or f"{suburb} {pc}",
            "url": url, "direct": direct, "bargain": bargain, "meets": meets,
            "reason": _reason(beds, land, price, median_low_k, bargain),
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


def main():
    try:
        token = get_token()
    except Exception as e:
        print(f"ERROR getting Domain access token: {e}", file=sys.stderr)
        print("Leaving the committed sample data/listings.json untouched.")
        return 0
    if not token:
        print("No Domain credentials (DOMAIN_CLIENT_ID/SECRET or DOMAIN_ACCESS_TOKEN). "
              "Leaving the committed sample data/listings.json untouched.")
        return 0
    print("Got Domain access token; searching target suburbs...")

    with open(SUBURBS_PATH) as fh:
        suburbs = json.load(fh)["suburbs"]
    targets = [s for s in suburbs if s.get("band")]  # in-budget shopping list

    listings = []
    for s in targets:
        try:
            items = search_suburb(token, s["name"], s["pc"])
            got = normalise(items, s["name"], s["pc"], s.get("mlo"))
            print(f"  {s['name']} {s['pc']}: {len(got)} listing(s)")
            listings.extend(got)
        except Exception as e:  # one suburb failing must not kill the run
            print(f"  warn: {s['name']} {s['pc']} failed: {e}", file=sys.stderr)
    # bargains first, then by price ascending
    listings.sort(key=lambda x: (not x["bargain"], x["price"] or 9_9_9_9_9_9_9))
    listings = listings[:TOTAL_CAP]

    if not listings:
        print("No live listings returned (check the project is in Production, not "
              "Sandbox, and that the plan includes residential listing search). "
              "Keeping the committed sample so the page does not go blank.")
        return 0

    payload = {
        "meta": {
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "source": "domain-api",
            "note": "Live houses from the Domain Developer API matching the brief "
                    "(3+ beds, <=$1.1M, in-budget target suburbs). Bargains = priced "
                    "below the suburb median. Refreshed daily by GitHub Actions.",
            "criteria": {"max_price": MAX_PRICE, "min_land": MIN_LAND,
                         "min_beds": MIN_BEDS, "types": ["House"]},
        },
        "listings": listings,
    }
    with open(OUT_PATH, "w") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    print(f"Wrote {len(listings)} listings to data/listings.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
