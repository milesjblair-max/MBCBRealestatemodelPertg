// AVM price estimator - a faithful TypeScript port of model/avm.py.
// Anchors on the suburb median, then applies hedonic adjustments for land
// (scaled to the suburb's price level), bedrooms, bathrooms and condition.
// The parity test asserts this matches the Python output to the dollar.

import { findSuburb } from "./data.js";
import { pyRound, round5 } from "./util.js";
import type { Condition, Estimate } from "./types.js";

const REF_BEDS = 4;
const REF_BATHS = 2;
const REF_LAND: Record<string, number> = { S: 600, N: 650 };

// Marginal land value scales with the suburb median (Como land is worth far
// more per sqm than Nollamara land), tapering a little on very large blocks.
const LAND_K = 0.0011;
const LAND_TAPER_OVER = 350;
const LAND_TAPER = 0.7;

const BED_VALUE = 25;
const BATH_VALUE = 15;

const CONDITION: Record<Condition, number> = {
  original: 0.96,
  dated: 0.98,
  good: 1.0,
  renovated: 1.06,
  new: 1.13,
};

const BASE_SPREAD = 0.12;
const MIN_SPREAD = 0.07;
const MAX_SPREAD = 0.2;

function sign(n: number): string {
  return `${n >= 0 ? "+" : ""}${Math.round(n)}k`;
}

export function estimate(
  suburb: string,
  land?: number | null,
  beds?: number | null,
  baths?: number | null,
  condition?: string | null,
): Estimate {
  const s = findSuburb(suburb);
  if (!s) throw new Error(`Unknown suburb '${suburb}'`);

  const { mlo, mhi } = s;
  const mid = (mlo + mhi) / 2;
  const refLand = REF_LAND[s.reg] ?? 600;

  const notes: string[] = [];
  let value = mid;

  // Land: per-sqm rate scaled to the suburb, tapering on very large blocks.
  if (land != null) {
    const rate = LAND_K * mid;
    const diff = land - refLand;
    let adj: number;
    if (diff > LAND_TAPER_OVER) {
      adj = LAND_TAPER_OVER * rate + (diff - LAND_TAPER_OVER) * rate * LAND_TAPER;
    } else if (diff < -LAND_TAPER_OVER) {
      adj = -LAND_TAPER_OVER * rate + (diff + LAND_TAPER_OVER) * rate * LAND_TAPER;
    } else {
      adj = diff * rate;
    }
    value += adj;
    notes.push(`land ${land}sqm vs ~${refLand}sqm typical: ${sign(adj)}`);
  }

  if (beds != null) {
    const adj = (beds - REF_BEDS) * BED_VALUE;
    value += adj;
    notes.push(`${beds} bed vs ${REF_BEDS}: ${sign(adj)}`);
  }
  if (baths != null) {
    const adj = (baths - REF_BATHS) * BATH_VALUE;
    value += adj;
    notes.push(`${baths} bath vs ${REF_BATHS}: ${sign(adj)}`);
  }

  if (condition != null) {
    const key = condition.trim().toLowerCase() as Condition;
    if (!(key in CONDITION)) {
      throw new Error("condition must be one of: original | dated | good | renovated | new");
    }
    const factor = CONDITION[key];
    const before = value;
    value *= factor;
    notes.push(`${key} condition x${factor.toFixed(2)}: ${sign(value - before)}`);
  }

  // Range width: start wide, narrow with more inputs, widen on noisy cases.
  const supplied = [land, beds, baths, condition].filter((x) => x != null).length;
  let spread = BASE_SPREAD - 0.01 * Math.min(supplied, 4);

  const bandRel = (mhi - mlo) / mid;
  if (bandRel > 0.08) spread += (bandRel - 0.08) * 0.5;
  if (land != null && Math.abs(land - refLand) > LAND_TAPER_OVER) spread += 0.02;
  if (beds != null && (beds <= 2 || beds >= 6)) spread += 0.02;

  spread = Math.max(MIN_SPREAD, Math.min(MAX_SPREAD, spread));

  const likely = value;
  const low = likely * (1 - spread);
  const high = likely * (1 + spread);
  const confidence: Estimate["confidence"] =
    spread < 0.09 ? "High" : spread < 0.135 ? "Medium" : "Low";
  const guideFloor = likely * 0.95;

  return {
    suburb: s.name,
    pc: s.pc,
    medianRange: [mlo, mhi],
    likely: round5(likely),
    low: round5(low),
    high: round5(high),
    guideFloor: round5(guideFloor),
    spreadPct: pyRound(spread * 100, 1),
    confidence,
    inBand: !!s.band,
    school: s.school,
    adjustments: notes,
  };
}
