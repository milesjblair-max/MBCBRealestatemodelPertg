// The WA-wide base layer: every WA suburb with real coordinates, so the model
// can anchor ANYWHERE in the state (Mandurah, Albany, Geraldton), not just the
// 14 curated suburbs. This is the geographic foundation of the rebuild; pricing,
// scores and listings are layered on top (live listings + Landgate/REIWA).
//
// Data is the free, public-domain coordinate layer built by
// scripts/build_wa_base_layer.py. It carries no prices - only facts.

import waData from "../../data/wa_suburbs.json";
import { haversineKm } from "./geo.js";
import type { WaSuburb } from "./types.js";

export const WA_SUBURBS: WaSuburb[] = (waData as { suburbs: WaSuburb[] }).suburbs;

const byName = new Map<string, WaSuburb>();
for (const s of WA_SUBURBS) byName.set(s.name.toLowerCase(), s);

/** Look up any WA suburb by name (case-insensitive). undefined if unknown. */
export function findWaSuburb(name: string): WaSuburb | undefined {
  return byName.get(name.trim().toLowerCase());
}

export interface NearbySuburb {
  name: string;
  pc: string;
  km: number; // distance from the anchor
  sa2: string;
}

/** The WA suburbs nearest a given anchor - the heart of "anchor anywhere".
 *  Returns up to `limit` suburbs within `maxKm`, nearest first, excluding the
 *  anchor itself. Throws if the anchor is not a known WA suburb. */
export function nearbyWaSuburbs(
  anchorName: string,
  opts: { limit?: number; maxKm?: number } = {},
): { anchor: WaSuburb; nearby: NearbySuburb[] } {
  const anchor = findWaSuburb(anchorName);
  if (!anchor) {
    throw new Error(`Unknown WA suburb '${anchorName}'. WA only; check the spelling.`);
  }
  const limit = opts.limit ?? 12;
  const maxKm = opts.maxKm ?? 15;
  const nearby = WA_SUBURBS.filter((s) => s.name !== anchor.name)
    .map((s) => ({
      name: s.name,
      pc: s.pc,
      sa2: s.sa2,
      km: Math.round(haversineKm(anchor.lat, anchor.lng, s.lat, s.lng) * 10) / 10,
    }))
    .filter((s) => s.km <= maxKm)
    .sort((a, b) => a.km - b.km)
    .slice(0, limit);
  return { anchor, nearby };
}
