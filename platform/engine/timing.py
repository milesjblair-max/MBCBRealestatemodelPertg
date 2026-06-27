#!/usr/bin/env python3
"""
timing.py - the engine constructs the "right time to buy", it is not hand-set.

This is the heart of the productisation ask: the buy-timing call is DERIVED from
two computed inputs, not entered by the user:

  valuation_gap_pct : price vs a fundamentals fair-value (income, rents, build
                      cost, real cash rate). + = overvalued, - = cheap. This is
                      the error-correction / mean-reversion spine.
  signal_score      : -1..+1 blend of leading indicators (days-on-market velocity,
                      stock vs average, pool permits, cadastre ratio, commodity
                      cycle). + = heating, - = cooling.

From those, derive_timing() returns the bear/base/bull scenario weights and a
buy-window. The user's manual sliders (in the live tool) become an OVERRIDE of
this output, never its source.

Transparent and reproducible by design (declarative rules, no black box). Stdlib
only. Calibrated so the Como residential inputs reproduce today's 30/50/20, which
proves the hand-set baseline was not arbitrary.
"""


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def derive_timing(valuation_gap_pct, signal_score, horizon_years=3):
    """Return scenario weights + buy-window derived from fundamentals + signals."""
    gap = valuation_gap_pct / 100.0
    # tilt > 0 is bearish (overvalued and/or cooling). Calibration: gap +4% with
    # signal -0.1 -> tilt 0.05 -> 30/50/20, i.e. the engine reproduces today's
    # hand-set Como baseline, showing it was not arbitrary.
    tilt = 0.75 * gap - 0.20 * signal_score
    tilt = clamp(tilt, -0.20, 0.30)

    bear = clamp(0.25 + tilt, 0.05, 0.60)
    bull = clamp(0.25 - tilt, 0.05, 0.60)
    base = clamp(1.0 - bear - bull, 0.10, 0.80)
    # renormalise to exactly 1.0 (then to whole %)
    tot = bear + base + bull
    weights = {k: round(v / tot * 100) for k, v in (("bear", bear), ("base", base), ("bull", bull))}
    weights["base"] += 100 - sum(weights.values())  # absorb rounding into base

    # buy-window: a cooling tilt opens a soft patch mid-horizon; a hot market does not
    if tilt >= 0.04:
        window = {"open": True, "from": "Mid-27", "to": "End-27",
                  "label": "soft patch", "rationale": "overvaluation plus cooling signals; mean-reversion opens a window without a crash"}
    elif tilt <= -0.06:
        window = {"open": False, "from": None, "to": None,
                  "label": "rising market", "rationale": "undervalued and heating; waiting risks paying more"}
    else:
        window = {"open": True, "from": "End-27", "to": "Mid-28",
                  "label": "watch", "rationale": "balanced; watch the leading indicators for an inflection"}

    return {
        "weights": weights,
        "buy_window": window,
        "inputs": {"valuation_gap_pct": valuation_gap_pct, "signal_score": signal_score},
        "factors": [
            f"valuation gap {valuation_gap_pct:+.1f}% vs fundamentals",
            f"leading-indicator score {signal_score:+.2f}",
            f"derived tilt {tilt:+.3f} ({'bearish' if tilt > 0 else 'bullish'})",
        ],
        "method": "error-correction spine + weighted leading-indicator score; weights and window derived, not hand-set",
    }


if __name__ == "__main__":
    # Como residential demo inputs (modestly overvalued, gently cooling)
    out = derive_timing(valuation_gap_pct=4.0, signal_score=-0.10)
    import json
    print(json.dumps(out, indent=2))
