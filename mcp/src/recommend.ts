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
  meets: boolean; // satisfies EVERY hard filter, computed live against THIS profile
  meetsNotes: string[]; // when meets is false, the plain-English reasons
}

/** Match listings to the buyer's profile. Two distinct ideas, kept separate on
 *  purpose:
 *
 *  - EXCLUDE (dropped from the result): a listing that DEFINITELY fails a hard
 *    filter on KNOWN data - over the budget ceiling, beyond max distance, or
 *    fewer beds than required. No point showing these.
 *  - meets (a flag on what IS shown): does it satisfy every hard filter on the
 *    data we actually have? Crucially, UNKNOWN is not a pass: a listing with
 *    `land: null` does NOT meet a 700sqm rule, it is simply unknown, so meets is
 *    false with a note. (This is the null-land bug fix: previously null land was
 *    silently treated as meeting any land minimum.)
 *
 *  Near-miss land (e.g. 520sqm against a 700 rule) is kept but flagged meets:
 *  false so the buyer can see it under "best fit" without it lying about the
 *  criteria. `meets` always reflects THIS profile's filters, never a baked value. */
export function matchListings(rp: ResolvedProfile, listings: Listing[] = []): ListingMatch[] {
  const out: ListingMatch[] = [];
  for (const L of listings) {
    const s = findSuburb(L.suburb);
    const dist = s ? distanceKm(rp.anchor, s) : null;
    const price = L.price ?? parsePrice(L.priceText);

    // Hard EXCLUDES: a known value that definitively breaks a hard filter.
    if (rp.filters.min_beds && L.beds != null && L.beds < rp.filters.min_beds) continue;
    if (price && price > rp.budget.ceiling) continue;
    if (rp.filters.max_distance_km != null && dist != null && dist > rp.filters.max_distance_km) continue;

    // meets: does it satisfy every hard filter on KNOWN data? Unknown != pass.
    const notes: string[] = [];
    if (rp.filters.min_land) {
      if (L.land == null) notes.push(`land size unknown (not confirmed >= ${rp.filters.min_land}sqm)`);
      else if (L.land < rp.filters.min_land) notes.push(`land ${L.land}sqm is under ${rp.filters.min_land}sqm`);
    }
    if (rp.filters.min_beds && L.beds == null) notes.push(`beds unknown (need ${rp.filters.min_beds}+)`);
    if (!price) notes.push("price on application (not confirmed within budget)");

    out.push({
      ...L,
      meets: notes.length === 0,
      meetsNotes: notes,
      fit: s ? scoreSuburbForProfile(s, rp).score : 0,
      km: dist != null ? Math.round(dist * 10) / 10 : null,
    });
  }
  // Confirmed matches first, then by suburb fit.
  return out.sort((a, b) => Number(b.meets) - Number(a.meets) || b.fit - a.fit);
}
