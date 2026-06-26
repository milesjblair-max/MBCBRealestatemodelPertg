#!/usr/bin/env python3
"""
scenario_model.py — Como-Anchored Perth Home Model, forecast spine.

Regenerates the probability-weighted expected price path from the bear/base/bull
scenario anchors and the 30/50/20 weights, derives the headline metrics (bear
trough, cost of waiting, 3-year CAGR), and self-verifies against data/baseline.json.

This is the "Reset" contract: the web tool's BASELINE must match what this prints.
Standard library only — no dependencies.

    python3 scenario_model.py            # print timeline + metrics, verify -> PASS/FAIL

Method (see .claude/skills/wa-property-expert/references/methodology.md):
  Layer 1  city VECM / mean-reversion spine  -> calibrates the scenario anchors
  Layer 2  scenario-weighted Monte Carlo     -> this file (expected path + spread)
  Layer 3  suburb gradient-boosted panel      -> scoring.py
  Layer 4  hedonic property adjustment        -> per-listing (land, KDR optionality)

The anchor paths below are the calibrated Layer-1 output plus an analyst overlay
(cash rate 4.35%, iron ore ~US$95/t easing, Simandou ramp, NG/CGT drag from
1 Jul 2027, structural undersupply). Change an anchor or a weight and re-run;
do not hand-edit baseline.json.
"""
import json
import os
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE_PATH = os.path.join(HERE, "..", "data", "baseline.json")

# --- weights (must sum to 100) -------------------------------------------------
WEIGHTS = {"bear": 30, "base": 50, "bull": 20}

# --- scenario anchor paths (Layer-1 spine + analyst overlay), $ ----------------
# label, t (years from mid-2026), bear, base, bull
ANCHORS = [
    ("Now (mid-26)", 0.0, 1_000_000, 1_000_000, 1_000_000),
    ("End-26",       0.5, 1_020_000, 1_055_000, 1_080_000),
    ("Mid-27",       1.0,   975_000, 1_080_000, 1_150_000),
    ("End-27",       1.5,   935_000, 1_085_000, 1_210_000),
    ("Mid-28",       2.0,   930_000, 1_110_000, 1_280_000),
    ("End-28",       2.5,   955_000, 1_145_000, 1_340_000),
    ("Mid-29",       3.0, 1_000_000, 1_180_000, 1_400_000),
]


def round_half_up_1000(x: float) -> int:
    """Round to the nearest $1,000, half up (matches the web tool's display)."""
    return int(Decimal(x / 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) * 1000


def weighted_expected(bear, base, bull, w=WEIGHTS):
    tot = w["bear"] + w["base"] + w["bull"]
    raw = bear * w["bear"] / tot + base * w["base"] / tot + bull * w["bull"] / tot
    return round_half_up_1000(raw)


def build_timeline():
    rows = []
    bear_vals = [a[2] for a in ANCHORS]
    trough_idx = bear_vals.index(min(bear_vals))
    for i, (label, t, bear, base, bull) in enumerate(ANCHORS):
        row = {
            "label": label, "t": t,
            "bear": bear, "base": base, "bull": bull,
            "expected": weighted_expected(bear, base, bull),
        }
        if i == trough_idx:
            row["trough"] = True
        rows.append(row)
    return rows


def metrics(timeline):
    start = timeline[0]["expected"]
    end = timeline[-1]["expected"]
    bear_trough = min(r["bear"] for r in timeline)
    bull_end = timeline[-1]["bull"]
    # cost of waiting = bull-case rise by End-27 (index 3) vs now
    cost_of_waiting = timeline[3]["bull"] - timeline[0]["bull"]
    years = timeline[-1]["t"]
    cagr = (end / start) ** (1 / years) - 1
    return {
        "expected_mid29": end,
        "bear_trough": bear_trough,
        "bear_trough_drawdown_pct": round((bear_trough / start - 1) * 100, 1),
        "bull_mid29": bull_end,
        "cost_of_waiting_to_end27_bull": cost_of_waiting,
        "expected_3yr_cagr_pct": round(cagr * 100, 2),
    }


def fmt(n):
    return f"${n/1_000_000:.2f}M" if n >= 1_000_000 else f"${round(n/1000)}k"


def main():
    timeline = build_timeline()
    m = metrics(timeline)

    print("=" * 66)
    print(" Como-Anchored Perth Home Model — forecast spine (mid-2026)")
    print(f" Weights: bear {WEIGHTS['bear']}%  base {WEIGHTS['base']}%  bull {WEIGHTS['bull']}%")
    print("=" * 66)
    print(f"{'Period':<14}{'Bear':>10}{'Base':>10}{'Bull':>10}{'Expected':>11}")
    print("-" * 66)
    for r in timeline:
        flag = "  <- trough" if r.get("trough") else ""
        print(f"{r['label']:<14}{fmt(r['bear']):>10}{fmt(r['base']):>10}"
              f"{fmt(r['bull']):>10}{fmt(r['expected']):>11}{flag}")
    print("-" * 66)
    print(f" Expected Mid-29 .............. {fmt(m['expected_mid29'])}")
    print(f" Bear trough ................. {fmt(m['bear_trough'])} "
          f"({m['bear_trough_drawdown_pct']}%)")
    print(f" Bull Mid-29 ................. {fmt(m['bull_mid29'])}")
    print(f" Cost of waiting (bull->End-27) {fmt(m['cost_of_waiting_to_end27_bull'])}")
    print(f" Expected 3yr CAGR ........... {m['expected_3yr_cagr_pct']}%")
    print("=" * 66)

    # --- self-verify against the committed baseline.json -----------------------
    with open(BASELINE_PATH) as fh:
        baseline = json.load(fh)
    ok = True
    bl = baseline["timeline"]
    if len(bl) != len(timeline):
        ok = False
    for got, want in zip(timeline, bl):
        for k in ("bear", "base", "bull", "expected"):
            if got[k] != want[k]:
                ok = False
                print(f" MISMATCH {got['label']} {k}: model={got[k]} baseline={want[k]}")
    kn = baseline["key_numbers"]
    for k in ("expected_mid29", "bear_trough", "bull_mid29",
              "cost_of_waiting_to_end27_bull"):
        if kn.get(k) != m[k]:
            ok = False
            print(f" MISMATCH key_numbers.{k}: model={m[k]} baseline={kn.get(k)}")

    print(" VERIFY: model output matches data/baseline.json -> "
          + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
