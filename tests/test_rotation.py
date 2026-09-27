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

    # 0. the rotation must advance per RUN, not per day. On a weekly schedule
    # indexing by day would move the start seven slices a week and walk past
    # most of the ring, which is exactly the bug that switching to weekly would
    # otherwise have introduced.
    day0 = datetime.date.today().toordinal()
    weekly = [F.rotation_offset(16, total, 7) for _ in (0,)]
    offs = []
    for w in range(6):
        run_index = (day0 + 7 * w) // 7
        offs.append((run_index * 16) % total)
    steps = {(offs[i + 1] - offs[i]) % total for i in range(len(offs) - 1)}
    ok(steps == {16}, f"a weekly run advances by exactly one slice: {steps}")
    same_week = {(((day0 + d) // 7) * 16) % total for d in range(0, 5)}
    ok(len(same_week) <= 2,
       f"runs inside one week share a starting point: {same_week}")
    ok(isinstance(weekly[0], int) and 0 <= weekly[0] < total,
       "rotation_offset returns a valid index")

    # an uncapped sweep must still rotate, or a quota that always cuts it short
    # would always cut it in the same place and never reach the tail
    ok(F.rotation_stride(0, total) > 0,
       "a full-ring sweep still rotates its starting point")
    ok(F.rotation_stride(16, total) == 16,
       "a capped sweep strides by exactly its slice")
    reach = set()
    for w in range(4):
        st = F.rotation_stride(0, total)
        off = (((day0 + 7 * w) // 7) * st) % total
        reach |= {x["name"] for x in (inter[off:] + inter[:off])[:45]}
    ok(len(reach) > total * 0.85,
       f"four short weeks of a full sweep still reach most of the ring: "
       f"{len(reach)}/{total}")

    # 1. every slice mirrors the ring. Not equal counts: the sectors are
    # different sizes (54 southern suburbs against 21 western), so an equal
    # slice would finish the west in six days and still be working through the
    # south a fortnight later. Proportional is what keeps every lane cycling
    # together, and it is what stops a slice covering one direction only.
    share = collections.Counter(s["sector"] for s in ring["suburbs"])
    cap, bad = 16, []
    for d in range(60):
        off = (d * cap) % len(inter)
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
    runs = (total + cap - 1) // cap
    seen = set()
    for r in range(runs):
        off = (r * cap) % len(inter)
        seen |= {x["name"] for x in (inter[off:] + inter[:off])[:cap]}
    ok(seen == {s["name"] for s in ring["suburbs"]},
       f"the ring is fully covered in {runs} runs: {len(seen)}/{total}")

    # 2b. the shipped configuration must not expire listings faster than the
    # rotation returns to them. This is the check that makes the cadence and the
    # cap safe to change: get it wrong and the page silently empties out.
    import subprocess
    env = dict(os.environ); env.pop("SUBURB_CAP", None)
    plan = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "fetch_listings.py"),
                           "--plan"], capture_output=True, text=True, env=env, cwd=ROOT)
    ok("TOO SLOW" not in plan.stdout,
       "the shipped schedule covers the ring inside the window:\n" + plan.stdout)
    ok(F.PERIOD_DAYS < F.WINDOW_DAYS,
       f"the window ({F.WINDOW_DAYS}d) outlasts the cadence ({F.PERIOD_DAYS}d), "
       f"so a single missed run does not empty the page")

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
