// M2: anchor ANYWHERE in WA and get fit-ranked nearby suburbs for THIS buyer.
//
// Every input drives the output: the anchor sets which suburbs are in play
// (M1 base layer), the criteria weight proximity vs land, the budget gates on
// real prices, and the buy-timing comes from the profile's finances. Prices are
// derived from LIVE listings per suburb (real, current, statewide) - injected as
// a dependency so this module stays pure and testable. No prices are invented:
// a suburb with no listings is scored on what we do know (distance) and flagged.
//
// Honest limit: schools/growth/family are not yet scored for arbitrary suburbs
// (that is the next layer - ABS demographics + Landgate growth, both free).

import { budgetBand, buyTiming } from "./engine/finance.js";
import { resolveWeights } from "./engine/profile.js";
import { findWaSuburb, nearbyWaSuburbs } from "./engine/baselayer.js";
import { parsePrice } from "./engine/util.js";
import type { BuyerProfile, BudgetBand, ScoringWeights } from "./engine/types.js";
import type { Listing } from "./engine/data.js";

function median(xs: number[]): number | null {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m]! : Math.round((s[m - 1]! + s[m]!) / 2);
}

export interface PriceSignal {
  listings: number;
  priced: number;
  medianPrice: number | null;
  typicalLand: number | null;
  typicalBeds: number | null;
}

/** Derive a real price signal for a suburb from its current listings. */
export function priceSignal(listings: Listing[]): PriceSignal {
  const prices = listings
    .map((L) => L.price ?? parsePrice(L.priceText))
    .filter((p): p is number => !!p && p >= 50000);
  const lands = listings.map((L) => L.land).filter((x): x is number => !!x && x > 0);
  const beds = listings.map((L) => L.beds).filter((x): x is number => !!x && x > 0);
  return {
    listings: listings.length,
    priced: prices.length,
    medianPrice: median(prices),
    typicalLand: median(lands),
    typicalBeds: median(beds),
  };
}

export interface AreaScore {
  fit: number; // 0-100
  proxScore: number;
  landScore: number | null;
  inBudget: boolean | null;
  budgetPenalty: number;
}

/** Score one area for the buyer: criteria-weighted (proximity + land where we
 *  have it), then gated by budget against the real median price. */
export function scoreArea(km: number, signal: PriceSignal, budget: BudgetBand, weights: ScoringWeights): AreaScore {
  const proxScore = Math.max(0, Math.min(10, 10 - km / 2));
  const landScore = signal.typicalLand != null ? Math.max(0, Math.min(10, signal.typicalLand / 100)) : null;

  const comps: Array<[number, number]> = [[proxScore, weights.prox]];
  if (landScore != null) comps.push([landScore, weights.land]);
  const wsum = comps.reduce((a, [, w]) => a + w, 0) || 1;
  const base = comps.reduce((a, [v, w]) => a + v * w, 0) / wsum; // 0..10

  let inBudget: boolean | null = null;
  let penalty = 1;
  if (signal.medianPrice != null && budget.ceiling > 0) {
    const ratio = signal.medianPrice / budget.ceiling;
    inBudget = ratio <= 1;
    if (ratio > 1) penalty = Math.max(0.15, 1 - (ratio - 1) * 3); // 10% over -> 0.7, 33% over -> 0.15
  }
  return {
    fit: Math.round(base * 10 * penalty * 10) / 10,
    proxScore: Math.round(proxScore * 10) / 10,
    landScore: landScore == null ? null : Math.round(landScore * 10) / 10,
    inBudget,
    budgetPenalty: Math.round(penalty * 100) / 100,
  };
}

export type FetchSuburbListings = (suburb: string, pc: string) => Promise<Listing[]>;

export interface AreaRow {
  name: string;
  pc: string;
  km: number;
  medianPrice: number | null;
  typicalLand: number | null;
  listings: number;
  fit: number;
  inBudget: boolean | null;
}

/** The M2 deliverable: any WA anchor + this profile -> fit-ranked nearby areas
 *  with real prices, the budget band and the buy-timing. */
export async function recommendAreas(
  profile: BuyerProfile,
  anchorName: string,
  opts: { radiusKm?: number; limit?: number },
  fetchSuburbListings: FetchSuburbListings,
) {
  const anchor = findWaSuburb(anchorName);
  if (!anchor) throw new Error(`Unknown WA suburb '${anchorName}'. WA only; check the spelling.`);

  // Budget and timing are finance-driven and anchor-independent: they work for
  // any buyer, any area. (This is the "optimal time to buy" for the profile.)
  const budget = budgetBand(profile);
  const timing = buyTiming(profile, budget);
  const weights = resolveWeights(profile);

  const radiusKm = opts.radiusKm ?? 15;
  const limit = opts.limit ?? 12;
  const near = nearbyWaSuburbs(anchorName, { maxKm: radiusKm, limit }).nearby;
  const candidates = [{ name: anchor.name, pc: anchor.pc, km: 0 }, ...near.map((s) => ({ name: s.name, pc: s.pc, km: s.km }))];

  const areas: AreaRow[] = [];
  for (const c of candidates) {
    const sig = priceSignal(await fetchSuburbListings(c.name, c.pc));
    const sc = scoreArea(c.km, sig, budget, weights);
    areas.push({
      name: c.name,
      pc: c.pc,
      km: c.km,
      medianPrice: sig.medianPrice,
      typicalLand: sig.typicalLand,
      listings: sig.listings,
      fit: sc.fit,
      inBudget: sc.inBudget,
    });
  }
  areas.sort((a, b) => b.fit - a.fit);

  const anchorRow = areas.find((a) => a.name === anchor.name);
  const affordability =
    anchorRow && anchorRow.medianPrice != null
      ? {
          anchorEntryPrice: anchorRow.medianPrice,
          reachable: anchorRow.medianPrice <= budget.ceiling,
          gapToAnchor: anchorRow.medianPrice - budget.ceiling,
          source: "live listings (median asking price)",
        }
      : { note: "No live listings for the anchor; set RAPIDAPI_KEY in Vercel for real prices." };

  const anyPriced = areas.some((a) => a.medianPrice != null);
  return {
    anchor: { name: anchor.name, pc: anchor.pc },
    budget,
    timing,
    weights,
    scored_on: ["proximity (distance from anchor)", "land (from listings)", "budget (from live listing prices)"],
    not_scored: ["schools", "growth", "family", "amenity - per-suburb layers pending (ABS/Landgate, free)"],
    affordability,
    source: anyPriced
      ? "live listings (Realty in AU via RapidAPI)"
      : "no live prices: set RAPIDAPI_KEY in Vercel - areas are located and distance-scored, but not price/budget scored",
    areas,
  };
}
