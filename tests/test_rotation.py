#!/usr/bin/env python3
"""
test_rotation.py - the rotating sweep and its rolling window.

The rotation exists because the full 143-call daily sweep exhausted the
RapidAPI plan's monthly quota, after which every run published nothing for 25
days. These checks pin the two properties that make a smaller daily slice safe:
every slice is balanced across the four sides of the city, and the page is
still built from the whole ring because unrefreshed suburbs are carried in a
rolling window rather than dropped.

Run: python3 tests/test_rotation.py   (no API key, no network)
"""
import collections
import datetime
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "model"))

CHECKS = {"n": 0, "bad": 0}


def ok(cond, label):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["bad"] += 1
        print(f"  FAIL: {label}")


def main():
    os.environ["SUBURB_CAP"] = "16"
    import fetch_listings as F

    with open(os.path.join(ROOT, "data", "perth_ring.json")) as fh:
        ring = json.load(fh)
    total = ring["meta"]["count"]
    inter = F.interleave_by_sector(ring["suburbs"])

    ok(len(inter) == total, f"interleaving keeps every suburb: {len(inter)}/{total}")
    ok(len({s["name"] for s in inter}) == total, "interleaving duplicates nothing")

    # 1. every daily slice mirrors the ring. Not equal counts: the sectors are
    # different sizes (54 southern suburbs against 21 western), so an equal
    # slice would finish the west in six days and still be working through the
    # south a fortnight later. Proportional is what keeps every lane cycling
    # together, and it is what stops a slice covering one direction only.
    share = collections.Counter(s["sector"] for s in ring["suburbs"])
    cap, bad = 16, []
    for d in range(60):
        day = datetime.date.today().toordinal() + d
        off = (day * cap) % len(inter)
        sl = (inter[off:] + inter[:off])[:cap]
        c = collections.Counter(x["sector"] for x in sl)
        if len(c) < 4:
            bad.append((d, "a direction is missing", dict(c)))
            continue
        for sec, n_ring in share.items():
            want = cap * n_ring / total
            if abs(c[sec] - want) > 1.5:
                bad.append((d, f"{sec} {c[sec]} vs ~{want:.1f}", dict(c)))
    ok(not bad, f"every daily slice mirrors the ring's composition: {bad[:3]}")

    # 2. the whole ring is covered inside the rolling window
    cycle = (total + cap - 1) // cap
    seen = set()
    for d in range(cycle):
        day = datetime.date.today().toordinal() + d
        off = (day * cap) % len(inter)
        seen |= {x["name"] for x in (inter[off:] + inter[:off])[:cap]}
    ok(seen == {s["name"] for s in ring["suburbs"]},
       f"the ring is fully covered in one {cycle}-day cycle: {len(seen)}/{total}")
    ok(cycle < F.WINDOW_DAYS,
       f"a full cycle ({cycle}d) finishes inside the window ({F.WINDOW_DAYS}d), "
       f"so nothing expires before it is re-checked")

    # 3. the rolling window carries, replaces and expires the right listings
    today = datetime.date.today()
    prev = [
        {"suburb": "Wilson", "url": "u1", "checked": today.isoformat()},
        {"suburb": "Dianella", "url": "u2",
         "checked": (today - datetime.timedelta(days=5)).isoformat()},
        {"suburb": "Balga", "url": "u3",
         "checked": (today - datetime.timedelta(days=F.WINDOW_DAYS + 1)).isoformat()},
        {"suburb": "Nedlands", "url": "u4"},          # no date at all
    ]
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump({"meta": {}, "listings": prev}, tmp)
    tmp.close()
    real, F.OUT_PATH = F.OUT_PATH, tmp.name
    try:
        kept, superseded, expired = F.carry_over({"Wilson"}, today)
    finally:
        F.OUT_PATH = real
        os.unlink(tmp.name)

    names = {k["suburb"] for k in kept}
    ok(superseded == 1 and "Wilson" not in names,
       "a suburb searched today is replaced, not duplicated")
    ok("Dianella" in names, "a suburb inside the window is carried forward")
    ok("Balga" not in names,
       f"a listing older than {F.WINDOW_DAYS} days is dropped, not shown as current")
    ok("Nedlands" not in names,
       "a listing with no checked date is dropped; unknown age is never treated as fresh")
    ok(expired == 2, f"both stale listings counted as expired: {expired}")

    print(f"rotation: {CHECKS['n'] - CHECKS['bad']} passed, {CHECKS['bad']} failed")
    return 1 if CHECKS["bad"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
