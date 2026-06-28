// Geography: distance from any anchor to any suburb, so "where you want to live"
// becomes a dynamic input instead of being hardcoded to Como.

import type { Suburb } from "./types.js";

const EARTH_KM = 6371;
const rad = (d: number) => (d * Math.PI) / 180;

/** Great-circle distance in km between two lat/lng points. */
export function haversineKm(aLat: number, aLng: number, bLat: number, bLng: number): number {
  const dLat = rad(bLat - aLat);
  const dLng = rad(bLng - aLng);
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(rad(aLat)) * Math.cos(rad(bLat)) * Math.sin(dLng / 2) ** 2;
  return EARTH_KM * 2 * Math.asin(Math.sqrt(s));
}

export function distanceKm(anchor: Suburb, s: Suburb): number {
  return haversineKm(anchor.lat, anchor.lng, s.lat, s.lng);
}

/** Distance -> a 0-10 proximity score (0km = 10, ~20km = 0). */
export function proximityScore(distKm: number): number {
  return Math.max(0, Math.min(10, 10 - distKm / 2));
}
