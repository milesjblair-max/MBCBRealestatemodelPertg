// Dynamic recommendations: score suburbs and listings against a RESOLVED buyer
// profile (their weights, their anchor, their budget) instead of the hardcoded
// Como criteria. This is what makes the area suggestions and listing matches
// move with the user's preferences.

import { SUBURBS, findSuburb, type Listing } from "./data.js";
import { distanceKm, proximityScore } from "./geo.js";
import { parsePrice } from "./util.js";
import type { ResolvedProfile, Suburb } from "./types.js";

export interface SuburbMatch {
  name: string;
  pc: string;
  km: number; // distance from the user's anchor
  score: number; // 0-100 fit against THIS profile
  inBudget: boolean;
  over: boolean;
}

export function scoreSuburbForProfile(s: Suburb, rp: ResolvedProfile): SuburbMatch {
  const dist = distanceKm(rp.anchor, s);
  const w = rp.weights;

  const composite =
    w.growth * s.scores.growth +
    w.family * s.scores.family +
    w.land * s.scores.land +
    w.kdr * s.scores.kdr +
    w.post * s.scores.post +
    w.school * s.school +
    w.prox * proximityScore(dist);

  let score = composite * 10; // 0-100
  const midK = (s.mlo + s.mhi) / 2;
  const ceilK = rp.budget.ceiling / 1000;
  const inBudget = midK <= ceilK;
  let over = false;
  if (midK > ceilK * 1.1) {
    score *= 0.45; // well over budget
    over = true;
  } else if (midK > ceilK) {
    score *= 0.8; // a touch over
    over = true;
  }
  if (rp.filters.max_distance_km != null && dist > rp.filters.max_distance_km) score = 0;

  return {
    name: s.name,
    pc: s.pc,
    km: Math.round(dist * 10) / 10,
    score: Math.round(score * 10) / 10,
    inBudget,
    over,
  };
}

export function rankSuburbsForProfile(rp: ResolvedProfile): SuburbMatch[] {
  return SUBURBS.map((s) => scoreSuburbForProfile(s, rp)).sort((a, b) => b.score - a.score);
}

export interface ListingMatch extends Listing {
  fit: number;
  km: number | null;
}

/** Filter listings to the profile's hard constraints, then rank by suburb fit. */
export function matchListings(rp: ResolvedProfile, listings: Listing[] = []): ListingMatch[] {
  const out: ListingMatch[] = [];
  for (const L of listings) {
    const s = findSuburb(L.suburb);
    const dist = s ? distanceKm(rp.anchor, s) : null;
    const price = L.price ?? parsePrice(L.priceText);

    const okBeds = !rp.filters.min_beds || (L.beds ?? 0) >= rp.filters.min_beds;
    const okLand = !rp.filters.min_land || !L.land || L.land >= rp.filters.min_land;
    const okBudget = !price || price <= rp.budget.ceiling;
    const okDist =
      rp.filters.max_distance_km == null || dist == null || dist <= rp.filters.max_distance_km;
    if (!(okBeds && okLand && okBudget && okDist)) continue;

    out.push({
      ...L,
      fit: s ? scoreSuburbForProfile(s, rp).score : 0,
      km: dist != null ? Math.round(dist * 10) / 10 : null,
    });
  }
  return out.sort((a, b) => b.fit - a.fit);
}
