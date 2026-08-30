#!/usr/bin/env python3
"""
value.py - relative-value engine: how far under fair value is this listing?

The listings feed used to search only the 8 curated in-budget suburbs, where a
researched median in data/suburbs.json told us what "cheap" meant. Sweeping the
whole inner-Perth ring breaks that: no free public source gives a reliable house
median for 143 suburbs, and inventing one would be worse than useless.

So this prices each listing against ITS OWN SUBURB'S CURRENT ASKING MARKET: the
other houses on the market right now in the same suburb that fit the same brief.
That is a real, checkable benchmark. It is deliberately NOT called a suburb
median, because it is not one; it is the median ASK of comparable current
listings, which is what a buyer is actually choosing between this weekend.

The chain per listing:
  1. Benchmark   - median ask of comparable current listings in the suburb
                   (falls back to the sector's median $/sqm when a suburb is thin)
  2. Fair value  - that benchmark, adjusted for how this property differs on
                   land, bedrooms and bathrooms (hedonic coefficients shared
                   with avm.py, so there is one source of truth)
  3. Discount    - (fair - asking) / fair
  4. Confidence  - how many comparables backed the benchmark
  5. Rank score  - the discount blended with buyer-fit, so "best bargain"
                   still means a bargain that suits THIS buyer

Honesty notes baked in:
  - No price published means no discount and no bargain flag. Unknown is never
    treated as cheap.
  - Under 3 comparables, the suburb benchmark is not trusted on its own.
  - A discount is a discount to the current asking market, not to valuation,
    and not a prediction. It flags where to look, not what something is worth.

Stdlib only.
"""
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# One source of truth for the hedonic coefficients: they live in avm.py.
from avm import LAND_K, LAND_TAPER_OVER, LAND_TAPER, BED_VALUE, BATH_VALUE  # noqa: E402

# ---- Thresholds (documented, deliberately conservative) ---------------------
MIN_COMPS = 3                # below this, a suburb benchmark is not trusted alone
GOOD_COMPS = 6               # at or above this, confidence is high
BARGAIN_DISC = 0.08          # 8% under fair value, on a trusted benchmark
BARGAIN_DISC_THIN = 0.14     # a bigger gap is needed when comps are thin
DISC_CAP = 0.20              # a 20%+ discount already scores full marks
# A discount beyond this is almost always a data artefact (a "from $649,000"
# on a half-duplex, a mis-parsed price), not a bargain. Flagged, not trusted.
DISC_IMPLAUSIBLE = 0.45
# "From $850,000" is a floor set under the real ask to draw enquiry, so taking
# it at face value manufactures a discount. Compared at a modest uplift instead.
GUIDE_UPLIFT = 1.04
# Land is a hard criterion for this buyer, so a listing that does not publish one
# is not neutral: it scores part marks on the land dimension, never full.
UNKNOWN_LAND_CREDIT = 0.4

# Buyer-fit inputs (the brief: family home, 500sqm+, 4+ beds, near Como)
TARGET_LAND = 500
TARGET_BEDS = 4
BUDGET_LO = 800_000
BUDGET_HI = 1_100_000
COMO_NEAR_KM = 8             # inside this reads as "near family"
COMO_FAR_KM = 22             # beyond this, proximity scores zero

DISC_WEIGHT = 0.60           # "best bargains" leans on price, but not blindly


def _pct(disc):
    """Discount as a whole percent, rounded half up.

    Computed once, here, and carried in the feed so the badge on a card and the
    sentence underneath it can never disagree. Python's round() is half-to-even
    and JavaScript's Math.round() is half-up, so 18.5 became 18 in one place and
    19 in the other until this existed.
    """
    return int(math.floor(disc * 100 + 0.5))


def _median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def suburb_benchmark(pool):
    """Median ask and typical attributes of the comparable listings in a suburb.

    `pool` is every parsed listing for that suburb that fits the brief, BEFORE
    the per-suburb display cut, so the benchmark sees the whole visible market
    rather than the handful we show.
    """
    priced = [p for p in pool if p.get("price")]
    lands = [p.get("land") for p in priced if p.get("land")]
    ppsqm = [p["price"] / p["land"] for p in priced if p.get("land")]
    return {
        "n": len(priced),
        "price": _median([p["price"] for p in priced]),
        "land": _median(lands),
        "beds": _median([p.get("beds") for p in priced]),
        "baths": _median([p.get("baths") for p in priced]),
        "ppsqm": _median(ppsqm),
    }


def sector_benchmark(pools_by_suburb, ring_by_name):
    """Fallback benchmarks per sector, for suburbs too thin to price themselves.

    Built from every priced listing in the sector, so a suburb with two houses
    on the market still gets a defensible reference point (the sector's median
    $/sqm and median ask) instead of being dropped or guessed at.
    """
    by_sector = {}
    for name, pool in pools_by_suburb.items():
        sec = (ring_by_name.get(name) or {}).get("sector")
        if not sec:
            continue
        by_sector.setdefault(sec, []).extend(pool)
    return {sec: suburb_benchmark(pool) for sec, pool in by_sector.items()}


def _land_adjust(land, ref_land, base_price):
    """Value of extra or missing land, at a rate that scales with the suburb.

    A square metre in Nedlands is not a square metre in Balga, so the marginal
    rate is a fraction of the local price level, tapering on very large blocks
    (the second 400sqm is worth less than the first). Same shape as avm.py.
    """
    rate = LAND_K * base_price          # dollars per sqm
    diff = land - ref_land
    if diff > LAND_TAPER_OVER:
        return LAND_TAPER_OVER * rate + (diff - LAND_TAPER_OVER) * rate * LAND_TAPER
    if diff < -LAND_TAPER_OVER:
        return -LAND_TAPER_OVER * rate + (diff + LAND_TAPER_OVER) * rate * LAND_TAPER
    return diff * rate


def fair_value(listing, bench, fallback=None):
    """Estimated fair ask for this property against its local asking market.

    Returns (fair_dollars, comps_used, basis) or (None, 0, reason) when there is
    not enough to say anything honest.
    """
    b, basis = bench, "suburb"
    if not b or not b.get("price") or b["n"] < MIN_COMPS:
        if fallback and fallback.get("price") and fallback["n"] >= MIN_COMPS:
            b, basis = fallback, "sector"
        elif b and b.get("price") and b["n"] > 0:
            basis = "suburb-thin"
        else:
            return None, 0, "no comparables"

    base = b["price"]
    fair = base

    # Land, where both sides are known. On a sector fallback the reference is
    # the sector's typical block, which is coarser, hence the lower confidence.
    if listing.get("land") and b.get("land"):
        fair += _land_adjust(listing["land"], b["land"], base)
    if listing.get("beds") and b.get("beds"):
        fair += (listing["beds"] - b["beds"]) * BED_VALUE * 1000
    if listing.get("baths") and b.get("baths"):
        fair += (listing["baths"] - b["baths"]) * BATH_VALUE * 1000

    return max(fair, 100_000), b["n"], basis


def confidence(comps, basis, has_land):
    if basis == "no comparables":
        return "none"
    if basis == "sector":
        return "low"
    if basis == "suburb-thin" or comps < MIN_COMPS:
        return "low"
    # Without a published land size the hedonic adjustment is doing nothing, so
    # the estimate is a suburb average wearing a property's name. Never "high".
    if not has_land:
        return "low"
    if comps >= GOOD_COMPS:
        return "high"
    return "medium"


def buyer_fit(listing, km_como):
    """0-100: how well this property suits the brief, ignoring price entirely.

    Deliberately built only from facts every listing carries (land, beds, price,
    distance). Growth, school-catchment and family scores exist for the 14
    curated suburbs only, so they are NOT used here; a ring-wide score built on
    data we have for 14 of 143 suburbs would be a fiction.
    """
    score, parts = 0.0, 0.0

    land = listing.get("land")
    if land:
        score += 30 * min(1.0, land / TARGET_LAND) if land < TARGET_LAND else 30
    else:
        # unknown is not a pass, and not a free ride either
        score += 30 * UNKNOWN_LAND_CREDIT
    parts += 30
    beds = listing.get("beds")
    if beds:
        score += 20 if beds >= TARGET_BEDS else 20 * (beds / TARGET_BEDS)
        parts += 20
    price = listing.get("price")
    if price:
        # inside the band scores full; under it scores full too (patience is
        # cheap, so cheaper is not a penalty); over the ceiling falls away fast
        if price <= BUDGET_HI:
            score += 20
        else:
            score += max(0, 20 * (1 - (price - BUDGET_HI) / 300_000))
        parts += 20
    if km_como is not None:
        near = max(0.0, min(1.0, (COMO_FAR_KM - km_como) / (COMO_FAR_KM - COMO_NEAR_KM)))
        score += 30 * near
        parts += 30

    return round(100 * score / parts) if parts else None


def score_listing(listing, bench, fallback, km_como):
    """Attach fair value, discount, confidence, buyer-fit and a rank score.

    Mutates and returns the listing dict, so the feed carries the reasoning with
    the data rather than recomputing it in the page.
    """
    fair, comps, basis = fair_value(listing, bench, fallback)
    price = listing.get("price")
    has_land = bool(listing.get("land"))
    conf = confidence(comps, basis, has_land)

    # An "offers from" figure is a floor, not an ask, so compare at an uplift.
    effective = price * GUIDE_UPLIFT if (price and listing.get("guide")) else price

    disc = None
    if fair and effective:
        disc = (fair - effective) / fair

    listing["fair"] = int(round(fair / 1000) * 1000) if fair else None
    listing["comps"] = comps
    listing["basis"] = basis
    listing["conf"] = conf
    listing["disc"] = round(disc, 3) if disc is not None else None
    listing["discPct"] = _pct(disc) if disc is not None else None
    listing["fit"] = buyer_fit(listing, km_como)

    # ---- the bargain flag, conservative on purpose --------------------------
    bargain = False
    if disc is not None and disc < DISC_IMPLAUSIBLE:
        need = BARGAIN_DISC if conf in ("high", "medium") else BARGAIN_DISC_THIN
        bargain = disc >= need
    listing["bargain"] = bargain
    listing["odd"] = bool(disc is not None and disc >= DISC_IMPLAUSIBLE)

    # ---- rank: mostly the discount, but it has to suit the buyer ------------
    disc_part = 100 * max(0.0, min(1.0, (disc or 0) / DISC_CAP)) if disc else 0.0
    if listing["odd"]:
        disc_part = 0.0                     # do not let an artefact top the list
    fit_part = listing["fit"] if listing["fit"] is not None else 50
    conf_mult = {"high": 1.0, "medium": 0.92, "low": 0.8, "none": 0.6}[conf]
    listing["rank"] = round(
        (DISC_WEIGHT * disc_part + (1 - DISC_WEIGHT) * fit_part) * conf_mult, 1)
    return listing


def explain(listing, suburb, km_como):
    """Plain-English why, for the card. No jargon, no invented precision."""
    bits = []
    if listing.get("beds"):
        bits.append(f"{listing['beds']}-bed")
    if listing.get("land"):
        bits.append(f"{listing['land']}sqm")
    head = ", ".join(bits) if bits else "House"

    disc, conf, comps = listing.get("disc"), listing.get("conf"), listing.get("comps")
    where = f"{suburb}"
    if km_como is not None:
        where += f", {km_como:g}km from Como"

    if listing.get("odd"):
        return (f"{head} in {where}. The asking figure is far below comparable "
                f"listings, which usually means a part-share, a duplex half or a "
                f"'from' price rather than a bargain. Worth a look, treated with "
                f"suspicion.")
    if disc is None:
        return (f"{head} in {where}. No price published, so it cannot be ranked "
                f"on value; the agent sets the guide on enquiry.")
    if disc >= 0.08:
        pct = listing.get("discPct", _pct(disc))
        basis = ("the other houses on the market in the suburb"
                 if listing.get("basis") == "suburb"
                 else "comparable listings across this side of the city")
        tail = ""
        if not listing.get("land"):
            tail = " No land size published, so confirm the block before anything else."
        elif listing.get("guide"):
            tail = " The price is a 'from' figure, so expect it to sell above."
        return (f"{head} in {where}, asking about {pct}% under {basis} "
                f"({comps} compared, {conf} confidence).{tail}")
    if disc >= 0:
        return (f"{head} in {where}, priced in line with comparable listings "
                f"({comps} compared). Fits the brief rather than undercutting it.")
    return (f"{head} in {where}, asking above comparable listings "
            f"({comps} compared). Included because it fits the brief on land and beds.")


# ---------------------------------------------------------------------------
# Self-test: python3 model/value.py
# These pin the behaviour that matters, which is what the engine REFUSES to call
# a bargain. Every case here is one that produced a false positive in practice.
def _selftest():
    checks, failed = 0, 0

    def ok(cond, label):
        nonlocal checks, failed
        checks += 1
        if not cond:
            failed += 1
            print(f"  FAIL: {label}")

    pool = [{"price": 900_000, "land": 700, "beds": 4, "baths": 2},
            {"price": 950_000, "land": 720, "beds": 4, "baths": 2},
            {"price": 880_000, "land": 680, "beds": 3, "baths": 1},
            {"price": 1_000_000, "land": 750, "beds": 4, "baths": 2},
            {"price": 920_000, "land": 700, "beds": 4, "baths": 2},
            {"price": 940_000, "land": 710, "beds": 4, "baths": 2}]
    bench = suburb_benchmark(pool)
    ok(bench["n"] == 6, "benchmark counts every priced comparable")
    ok(bench["price"] == 930_000, f"benchmark median ask, got {bench['price']}")

    # a like-for-like house well under the local market is a bargain
    cheap = score_listing({"price": 780_000, "land": 700, "beds": 4, "baths": 2},
                          bench, None, 5.0)
    ok(cheap["bargain"], "clear discount on a full set of attributes is a bargain")
    ok(cheap["conf"] == "high", f"6 comps plus land is high confidence, got {cheap['conf']}")

    # the same price with no land published must NOT be as trusted
    noland = score_listing({"price": 780_000, "beds": 4, "baths": 2}, bench, None, 5.0)
    ok(noland["conf"] == "low", f"unknown land is never high confidence, got {noland['conf']}")
    ok(noland["fit"] < cheap["fit"], "unknown land scores below a known 700sqm block")

    # a 'from' price is a floor, so it must produce a smaller discount
    guide = score_listing({"price": 780_000, "land": 700, "beds": 4, "baths": 2,
                           "guide": True}, bench, None, 5.0)
    ok(guide["disc"] < cheap["disc"], "a 'from' price discounts less than a firm ask")

    # no price at all is never cheap
    nop = score_listing({"land": 700, "beds": 4, "baths": 2}, bench, None, 5.0)
    ok(nop["disc"] is None and not nop["bargain"], "no published price is never a bargain")

    # an absurd gap is flagged as odd, not celebrated as the best buy
    odd = score_listing({"price": 380_000, "land": 700, "beds": 4, "baths": 2},
                        bench, None, 5.0)
    ok(odd["odd"] and not odd["bargain"], "an implausible gap is flagged, not trusted")
    ok(odd["rank"] < cheap["rank"], "an odd listing never outranks a real bargain")

    # a thin suburb falls back to the sector, at reduced confidence
    thin = suburb_benchmark(pool[:2])
    fell = score_listing({"price": 780_000, "land": 700, "beds": 4, "baths": 2},
                         thin, bench, 5.0)
    ok(fell["basis"] == "sector", f"under {MIN_COMPS} comps falls back, got {fell['basis']}")
    ok(fell["conf"] == "low", "a sector fallback is low confidence")

    # nothing to compare against says so rather than guessing
    empty = score_listing({"price": 780_000, "land": 700}, suburb_benchmark([]), None, 5.0)
    ok(empty["disc"] is None and empty["conf"] == "none", "no comparables means no verdict")

    # more land, closer to Como and more beds all raise fit
    ok(buyer_fit({"land": 700, "beds": 4, "price": 900_000}, 4)
       > buyer_fit({"land": 700, "beds": 4, "price": 900_000}, 20),
       "closer to Como fits better")
    ok(buyer_fit({"land": 700, "beds": 4, "price": 900_000}, 5)
       > buyer_fit({"land": 400, "beds": 4, "price": 900_000}, 5),
       "a bigger block fits better")

    # the badge figure and the sentence figure must come from the same number
    half = score_listing({"price": 757_950, "land": 700, "beds": 4, "baths": 2},
                         bench, None, 5.0)
    ok(half["discPct"] == _pct(half["disc"]), "the percent shown is derived once")
    ok(_pct(0.185) == 19, f"18.5 rounds half up to 19, got {_pct(0.185)}")
    ok(str(half["discPct"]) in explain(half, "Test", 5.0),
       "the sentence quotes the same percent the badge shows")

    print(f"value: {checks - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
