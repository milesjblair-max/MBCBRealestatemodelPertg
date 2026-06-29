// matchListings tests: the live, profile-driven 'meets' verdict. The point is
// that meets reflects THIS buyer's filters and never a baked value, and that
// UNKNOWN data (null land) is not silently treated as a pass. Regression guard
// for the null-land bug and the stale 'meets' flag.

import { matchListings } from "../src/recommend.js";
import { resolveProfile } from "../src/profile.js";
import type { BuyerProfile } from "../src/types.js";
import type { Listing } from "../src/data.js";

let pass = 0;
let fail = 0;
function ok(name: string, cond: boolean, detail = ""): void {
  if (cond) pass++;
  else {
    fail++;
    console.error(`  FAIL ${name}${detail ? `: ${detail}` : ""}`);
  }
}

// A buyer whose land filter is 700sqm (the case the buyer reported).
const profile: BuyerProfile = {
  region: "WA",
  anchor: "Wilson",
  income: 180000,
  finances: { deposit: 250000 },
  life_stage: "young_family",
  criteria: { land: 5, proximity: 3 },
  filters: { min_beds: 3, min_land: 700, max_distance_km: 50 },
};
const rp = resolveProfile(profile);
ok("filter carried through: min_land is 700", rp.filters.min_land === 700, `${rp.filters.min_land}`);

const L = (suburb: string, land: number | null, beds: number | null, price: number | null): Listing =>
  ({ suburb, land, beds, price, priceText: price ? `$${price}` : "Contact agent" }) as Listing;

// Prices are kept under this profile's ~$837k ceiling so the budget gate does
// not exclude them; we are testing the land/meets logic, not the budget gate.
const res = matchListings(rp, [
  L("Wilson", 800, 4, 780000), // clean meet
  L("Wilson", 520, 4, 780000), // under 700 -> not a meet
  L("Wilson", null, 4, 780000), // unknown land -> NOT a meet (the bug)
  L("Wilson", 720, 4, null), // price on application -> not confirmed in budget
]);

const byLand = (land: number | null) => res.find((r) => (r.land ?? null) === land)!;

ok("known land >= filter meets", byLand(800).meets === true);
ok("known land under filter does NOT meet", byLand(520).meets === false);
ok("near-miss land is kept, not dropped", byLand(520) !== undefined);
ok("near-miss has an explanatory note", byLand(520).meetsNotes.some((n) => n.includes("520")));
ok("NULL land does NOT meet a land filter (null-land bug)", byLand(null).meets === false);
ok("null land has an 'unknown' note", byLand(null).meetsNotes.some((n) => n.toLowerCase().includes("unknown")));
ok("price-on-application is not a confirmed meet", byLand(720).meets === false);
ok("confirmed meets sort ahead of non-meets", res[0]!.meets === true);

// With NO land filter, land is irrelevant and even null land can meet.
const noLand = resolveProfile({ ...profile, filters: { min_beds: 3 } });
const res2 = matchListings(noLand, [L("Wilson", null, 4, 780000)]);
ok("no land filter -> null land can meet", res2[0]!.meets === true);

// A definitive hard fail (over budget) is EXCLUDED, not just flagged.
const res3 = matchListings(rp, [L("Wilson", 800, 4, 5_000_000)]);
ok("over-budget listing is excluded entirely", res3.length === 0, `${res3.length}`);

console.log(`\nmatchlistings: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
