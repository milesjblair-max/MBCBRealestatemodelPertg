// M2 tests: the criteria-driven, anchor-anywhere area recommender. Listings are
// injected (synthetic), so this verifies the real logic - price signal, the
// criteria/budget scoring, and end-to-end ranking for a Mandurah anchor - without
// the network. Proves every input moves the output.

import { priceSignal, scoreArea, recommendAreas } from "../lib/area-recommend.js";
import type { BuyerProfile, BudgetBand, ScoringWeights } from "../lib/engine/types.js";
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
  ({ suburb: "x", price, land, beds, priceText: price ? `$${price}` : "Contact agent" }) as Listing;

// ---- price signal -----------------------------------------------------------
const sig = priceSignal([L(800000, 600), L(900000, 700), L(1000000, 800), L(null, null)]);
ok("counts listings", sig.listings === 4, `${sig.listings}`);
ok("median price from real listings", sig.medianPrice === 900000, `${sig.medianPrice}`);
ok("typical land from real listings", sig.typicalLand === 700, `${sig.typicalLand}`);
ok("ignores unpriced listings in the median", priceSignal([L(null, null)]).medianPrice === null);

// ---- scoreArea: budget gates on real price ----------------------------------
const budget: BudgetBand = { floor: 360000, ceiling: 500000, borrowingCapacity: 400000, cash: 100000, borrowedFunds: 0, monthlyServicing: 0 };
const wBalanced: ScoringWeights = { growth: 0, family: 0, land: 0.3, kdr: 0, prox: 0.3, post: 0, school: 0 };
const inB = scoreArea(3, { listings: 5, priced: 5, medianPrice: 450000, typicalLand: 600, typicalBeds: 4 }, budget, wBalanced);
const overB = scoreArea(3, { listings: 5, priced: 5, medianPrice: 650000, typicalLand: 600, typicalBeds: 4 }, budget, wBalanced);
ok("in-budget area is flagged in budget", inB.inBudget === true);
ok("over-budget area is flagged over budget", overB.inBudget === false);
ok("over-budget area scores lower (budget gates)", overB.fit < inB.fit, `${overB.fit} < ${inB.fit}`);

// ---- criteria drive the score: land weight ----------------------------------
const wLand: ScoringWeights = { growth: 0, family: 0, land: 1, kdr: 0, prox: 0, post: 0, school: 0 };
const bigLand = scoreArea(5, { listings: 3, priced: 3, medianPrice: 400000, typicalLand: 900, typicalBeds: 4 }, budget, wLand);
const smallLand = scoreArea(5, { listings: 3, priced: 3, medianPrice: 400000, typicalLand: 400, typicalBeds: 4 }, budget, wLand);
ok("with land weighted, bigger land scores higher", bigLand.fit > smallLand.fit, `${bigLand.fit} > ${smallLand.fit}`);

// ---- criteria drive the score: proximity weight -----------------------------
const wProx: ScoringWeights = { growth: 0, family: 0, land: 0, kdr: 0, prox: 1, post: 0, school: 0 };
const sigSame = { listings: 3, priced: 3, medianPrice: 400000, typicalLand: 600, typicalBeds: 4 };
ok("with proximity weighted, closer scores higher", scoreArea(2, sigSame, budget, wProx).fit > scoreArea(10, sigSame, budget, wProx).fit);

// ---- end to end: anchor Mandurah, real ranking ------------------------------
// A modest buyer. Inject prices: Mandurah over budget, Halls Head in budget with
// bigger land. The recommender should rank Halls Head above the anchor.
async function main(): Promise<void> {
const profile: BuyerProfile = {
  region: "WA",
  anchor: "Mandurah",
  income: 120000,
  finances: { deposit: 100000 },
  life_stage: "young_family",
  criteria: { land: 5, proximity: 3, schools: 0, growth: 0, family: 0, amenity: 0, project: 0 },
};
const fixtures: Record<string, Listing[]> = {
  Mandurah: [L(640000, 500), L(680000, 520), L(700000, 540)], // over a ~$500k ceiling
  "Halls Head": [L(440000, 760), L(470000, 800), L(460000, 780)], // in budget, big land
};
const fetch = async (s: string): Promise<Listing[]> => fixtures[s] ?? [];

const res = await recommendAreas(profile, "Mandurah", { radiusKm: 12, limit: 12 }, fetch);
ok("returns the budget band", res.budget.ceiling > 0);
ok("returns the buy-timing (from the profile)", typeof res.timing.posture === "string" && res.timing.urgency >= 0);
ok("anchor affordability from live price", "anchorEntryPrice" in res.affordability && (res.affordability as { anchorEntryPrice: number }).anchorEntryPrice === 680000);
ok("anchor is correctly priced out (modest budget vs Mandurah)", "reachable" in res.affordability && (res.affordability as { reachable: boolean }).reachable === false);

const mandurah = res.areas.find((a) => a.name === "Mandurah")!;
const hallsHead = res.areas.find((a) => a.name === "Halls Head")!;
ok("Halls Head is in budget", hallsHead.inBudget === true, `${hallsHead.medianPrice}`);
ok("Mandurah is over budget", mandurah.inBudget === false);
ok("Halls Head out-ranks the over-budget anchor", hallsHead.fit > mandurah.fit, `${hallsHead.fit} > ${mandurah.fit}`);
ok("areas are sorted by fit", res.areas.every((a, i, arr) => i === 0 || arr[i - 1]!.fit >= a.fit));

// A different anchor works too (statewide, not Mandurah-specific).
const albany = await recommendAreas({ ...profile, anchor: "Albany" }, "Albany", { radiusKm: 15, limit: 6 }, async () => []);
ok("works for a regional anchor (Albany)", albany.anchor.name === "Albany" && albany.areas.length >= 1);
ok("unknown anchor throws", await (async () => { try { await recommendAreas(profile, "Atlantis", {}, async () => []); return false; } catch { return true; } })());
}

main().then(() => {
  console.log(`\narea-recommend: ${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
}).catch((e) => { console.error(e); process.exit(1); });
