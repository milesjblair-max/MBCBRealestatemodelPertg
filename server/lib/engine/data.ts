// Single source of truth: the engine reads the SAME data/*.json the Python
// model and the HTML tool read, so all three stay in lockstep.
//
// We load the JSON via static ESM imports (not readFileSync). Two reasons:
//   1. A bundler can SEE a static import and include the file, so this works
//      unchanged inside the Phase 2 Vercel serverless function. A
//      readFileSync(join(here, "..", "..", "data", name)) with a computed path
//      is invisible to the bundler's file tracer and would ENOENT at runtime.
//   2. tsx (the parity runner) and Next both resolve JSON imports natively, so
//      the same module works in the test harness and in production.
// The relative path "../../data/*.json" resolves to the repo's data/ folder
// from mcp/src, and to server/data/ from the vendored copy in the Vercel app -
// same relative shape, so the one file is correct in both trees.

import suburbsJson from "../../data/suburbs.json";
import criteriaJson from "../../data/criteria.json";
import baselineJson from "../../data/baseline.json";
import listingsJson from "../../data/listings.json";
import type { Suburb, CriteriaWeights } from "./types.js";

export const SUBURBS: Suburb[] = (suburbsJson as { suburbs: unknown[] }).suburbs as unknown as Suburb[];

export const CRITERIA_WEIGHTS: CriteriaWeights = (
  criteriaJson as { weighted_dimensions: CriteriaWeights }
).weighted_dimensions;

export interface BaselineRow {
  label: string;
  t: number;
  bear: number;
  base: number;
  bull: number;
  expected: number;
  trough?: boolean;
}
export const BASELINE = baselineJson as unknown as {
  timeline: BaselineRow[];
  key_numbers: Record<string, number>;
  weights: { bear: number; base: number; bull: number };
};

export function findSuburb(name: string): Suburb | undefined {
  const n = name.trim().toLowerCase();
  return SUBURBS.find((s) => s.name.toLowerCase() === n);
}

export interface Listing {
  suburb: string;
  pc?: string;
  price?: number | null;
  priceText?: string;
  beds?: number | null;
  baths?: number | null;
  cars?: number | null;
  land?: number | null;
  address?: string;
  image?: string | null;
  url?: string;
  new?: boolean;
  // Extra fields the daily fetch script (scripts/fetch_listings.py) writes.
  bargain?: boolean;
  meets?: boolean;
  reason?: string;
  direct?: boolean;
}
export function loadListings(): Listing[] {
  const data = listingsJson as { listings?: Listing[] };
  return data.listings ?? [];
}
