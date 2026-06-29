// find_listings tests: the pure hard-filter that powers anchor-anywhere listing
// search (e.g. "Mandurah houses over 700sqm"). The point is that hard filters
// are HARD, and that unknown land is dropped as unknown - never silently passed.

import { applyHardFilters } from "../lib/listings-live.js";
import type { Listing } from "../lib/engine/data.js";

let pass = 0;
let fail = 0;
function ok(name: string, cond: boolean, detail = ""): void {
  if (cond) pass++;
  else {
    fail++;
    console.error(`  FAIL ${name}${detail ? `: ${detail}` : ""}`);
  }
}

const L = (price: number | null, land: number | null, beds = 4): Listing =>
  ({ suburb: "Mandurah", price, land, beds, priceText: price ? `$${price}` : "Contact agent" }) as Listing;

const stock = [
  L(700000, 800, 4), // clean pass at 700sqm
  L(680000, 760, 3),
  L(640000, 520, 4), // under 700 -> belowLand
  L(720000, null, 4), // unknown land -> unknownLand (NOT a pass)
  L(900000, 900, 2), // too few beds
  L(1500000, 1000, 5), // over price
];

const { kept, dropped } = applyHardFilters(stock, { minLand: 700, minBeds: 3, maxPrice: 1100000 });

ok("keeps only listings with known land >= 700", kept.every((l) => l.land != null && l.land >= 700), JSON.stringify(kept.map((l) => l.land)));
ok("keeps exactly the two clean passes", kept.length === 2, `${kept.length}`);
ok("under-threshold land counted as belowLand", dropped.belowLand === 1, `${dropped.belowLand}`);
ok("UNKNOWN land dropped as unknownLand, not belowLand", dropped.unknownLand === 1 && !kept.some((l) => l.land == null), `${dropped.unknownLand}`);
ok("too-few-beds dropped", dropped.tooFewBeds === 1, `${dropped.tooFewBeds}`);
ok("over-price dropped", dropped.overPrice === 1, `${dropped.overPrice}`);
ok("kept sorted by price ascending", kept.every((l, i, a) => i === 0 || (a[i - 1]!.price ?? 0) <= (l.price ?? 0)));

// No land filter: unknown land is no longer dropped (land is irrelevant).
const r2 = applyHardFilters([L(720000, null, 4)], { minBeds: 3 });
ok("no land filter -> unknown land kept", r2.kept.length === 1 && r2.dropped.unknownLand === 0);

// No filters at all: everything passes.
const r3 = applyHardFilters(stock, {});
ok("no filters -> all kept", r3.kept.length === stock.length, `${r3.kept.length}`);

console.log(`\nfind-listings: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
