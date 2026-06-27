"""
forecast.py - shared scenario spine. Given an asset class's calibrated anchor
paths (Layer 1) and the DERIVED scenario weights (from timing.py), produce the
bear/base/bull/expected timeline the UI draws. Identical math to the production
model/scenario_model.py, but the weights now come from the engine, not by hand.
Stdlib only.
"""
from decimal import Decimal, ROUND_HALF_UP


def _round1000(x):
    return int(Decimal(x / 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) * 1000


def derive_timeline(anchors, weights):
    """anchors: list of (label, t, bear, base, bull). weights: {bear,base,bull} %."""
    wb, wm, wl = weights["bear"], weights["base"], weights["bull"]
    tot = wb + wm + wl
    bear_vals = [a[2] for a in anchors]
    ti = bear_vals.index(min(bear_vals))
    rows = []
    for i, (label, t, bear, base, bull) in enumerate(anchors):
        row = {"label": label, "t": t, "bear": bear, "base": base, "bull": bull,
               "expected": _round1000(bear * wb / tot + base * wm / tot + bull * wl / tot)}
        if i == ti:
            row["trough"] = True
        rows.append(row)
    return rows
