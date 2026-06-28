// Scenario forecast spine - a port of model/scenario_model.py (Layer 2).
// Blends bear/base/bull anchor paths by their weights into the expected path,
// and derives the headline metrics. The baseline weights (30/50/20) must
// reproduce data/baseline.json exactly - the parity test checks that.

import { roundHalfUp1000 } from "./util.js";

export interface Weights {
  bear: number;
  base: number;
  bull: number;
}
export const BASELINE_WEIGHTS: Weights = { bear: 30, base: 50, bull: 20 };

// label, t (years from mid-2026), bear, base, bull
type Anchor = [string, number, number, number, number];
const ANCHORS: Anchor[] = [
  ["Now (mid-26)", 0.0, 1_000_000, 1_000_000, 1_000_000],
  ["End-26", 0.5, 1_020_000, 1_055_000, 1_080_000],
  ["Mid-27", 1.0, 975_000, 1_080_000, 1_150_000],
  ["End-27", 1.5, 935_000, 1_085_000, 1_210_000],
  ["Mid-28", 2.0, 930_000, 1_110_000, 1_280_000],
  ["End-28", 2.5, 955_000, 1_145_000, 1_340_000],
  ["Mid-29", 3.0, 1_000_000, 1_180_000, 1_400_000],
];

export interface TimelineRow {
  label: string;
  t: number;
  bear: number;
  base: number;
  bull: number;
  expected: number;
  trough?: boolean;
}

function weightedExpected(bear: number, base: number, bull: number, w: Weights): number {
  const tot = w.bear + w.base + w.bull;
  const raw = (bear * w.bear) / tot + (base * w.base) / tot + (bull * w.bull) / tot;
  return roundHalfUp1000(raw);
}

export function buildTimeline(w: Weights = BASELINE_WEIGHTS): TimelineRow[] {
  const bearVals = ANCHORS.map((a) => a[2]);
  const troughIdx = bearVals.indexOf(Math.min(...bearVals));
  return ANCHORS.map(([label, t, bear, base, bull], i) => {
    const row: TimelineRow = {
      label,
      t,
      bear,
      base,
      bull,
      expected: weightedExpected(bear, base, bull, w),
    };
    if (i === troughIdx) row.trough = true;
    return row;
  });
}

export interface ForecastMetrics {
  expected_mid29: number;
  bear_trough: number;
  bear_trough_drawdown_pct: number;
  bull_mid29: number;
  cost_of_waiting_to_end27_bull: number;
  expected_3yr_cagr_pct: number;
}

export function metrics(timeline: TimelineRow[]): ForecastMetrics {
  const start = timeline[0]!.expected;
  const end = timeline[timeline.length - 1]!.expected;
  const bearTrough = Math.min(...timeline.map((r) => r.bear));
  const bullEnd = timeline[timeline.length - 1]!.bull;
  const costOfWaiting = timeline[3]!.bull - timeline[0]!.bull;
  const years = timeline[timeline.length - 1]!.t;
  const cagr = (end / start) ** (1 / years) - 1;
  return {
    expected_mid29: end,
    bear_trough: bearTrough,
    bear_trough_drawdown_pct: Math.round((bearTrough / start - 1) * 100 * 10) / 10,
    bull_mid29: bullEnd,
    cost_of_waiting_to_end27_bull: costOfWaiting,
    expected_3yr_cagr_pct: Math.round((cagr * 100) * 100) / 100,
  };
}
