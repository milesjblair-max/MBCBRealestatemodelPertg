// Resolve a raw BuyerProfile into the working parameters the engine scores with:
// normalised criteria weights, the anchor suburb, a budget band and a buy-timing
// posture. This is what replaces the hardcoded criteria.json.

import { findSuburb } from "./data.js";
import { budgetBand, buyTiming } from "./finance.js";
import type {
  BuyerProfile,
  CriteriaInput,
  LifeStage,
  ResolvedProfile,
  ScoringWeights,
} from "./types.js";

// Sensible default importance (0-5) per life stage. The user can override any of
// these; omitted dimensions fall back to the preset.
const PRESETS: Record<LifeStage, Required<CriteriaInput>> = {
  young_single: { growth: 4, schools: 0, family: 1, land: 1, proximity: 5, amenity: 5, project: 1 },
  young_couple: { growth: 4, schools: 1, family: 2, land: 2, proximity: 4, amenity: 4, project: 2 },
  young_family: { growth: 4, schools: 5, family: 5, land: 4, proximity: 4, amenity: 2, project: 2 },
  established_family: { growth: 3, schools: 5, family: 4, land: 4, proximity: 3, amenity: 3, project: 2 },
  downsizer: { growth: 3, schools: 0, family: 1, land: 1, proximity: 4, amenity: 5, project: 1 },
};

/** Map the user's 0-5 importance per dimension onto the suburb scoring
 *  dimensions and normalise so the weights sum to 1. */
function toWeights(c: Required<CriteriaInput>): ScoringWeights {
  const raw = {
    growth: c.growth,
    family: c.family,
    land: c.land,
    kdr: c.project, // "project" appetite maps to KDR upside
    prox: c.proximity, // dynamic distance to the anchor
    post: c.amenity, // postcode / lifestyle amenity
    school: c.schools,
  };
  const total = Object.values(raw).reduce((a, b) => a + b, 0) || 1;
  const w = {} as ScoringWeights;
  (Object.keys(raw) as (keyof ScoringWeights)[]).forEach((k) => (w[k] = raw[k] / total));
  return w;
}

export function resolveProfile(p: BuyerProfile): ResolvedProfile {
  if (p.region !== "WA") {
    throw new Error("Only WA (Perth) is supported for now.");
  }
  const anchor = findSuburb(p.anchor);
  if (!anchor) {
    throw new Error(`Unknown anchor suburb '${p.anchor}'. WA (Perth) suburbs only for now.`);
  }

  const lifeStage: LifeStage = p.life_stage ?? "young_family";
  const preset = PRESETS[lifeStage];
  const merged: Required<CriteriaInput> = { ...preset, ...(p.criteria ?? {}) };
  const weights = toWeights(merged);

  const budget = budgetBand(p);
  const timing = buyTiming(p, budget);

  // Can they afford a house at their own anchor? anchor.mlo is the median-low,
  // i.e. the typical entry-level house price for the suburb (in $000s).
  const anchorEntryPrice = anchor.mlo * 1000;
  const affordability = {
    anchorEntryPrice,
    reachable: budget.ceiling >= anchorEntryPrice,
    gapToAnchor: anchorEntryPrice - budget.ceiling,
  };

  return {
    anchor,
    weights,
    budget,
    timing,
    affordability,
    filters: {
      min_beds: p.filters?.min_beds ?? 0,
      min_land: p.filters?.min_land ?? 0,
      max_distance_km: p.filters?.max_distance_km ?? null,
    },
    lifeStage,
  };
}
