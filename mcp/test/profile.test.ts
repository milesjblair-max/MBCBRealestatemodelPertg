// profile.test.ts - deterministic unit tests for the dynamic, profile-driven
// layer. The parity test proves the buyer-agnostic engine matches Python; this
// proves the multi-user layer behaves the way the spec demands:
//   - WA-only guard (region + known anchor)
//   - budget rises with income (serviceability is monotonic)
//   - the two buyers contrast the way the brief asked: a cash-rich buyer with a
//     0% facility is PATIENT, a renting small-deposit buyer is ACT-NOW
//   - the suburb ranking follows the anchor (proximity is dynamic, not Como)
//   - the criteria weights always normalise to 1
//
// No Python here: this layer is new and TS-only, so the tests are self-contained
// and run in the same gate as parity.

import { resolveProfile } from "../src/profile.js";
import { budgetBand, borrowingCapacity } from "../src/finance.js";
import { rankSuburbsForProfile } from "../src/recommend.js";
import { profileFromAnswers } from "../src/onboarding.js";
import type { BuyerProfile } from "../src/types.js";

let pass = 0;
let fail = 0;
function ok(name: string, cond: boolean, detail = ""): void {
  if (cond) pass++;
  else {
    fail++;
    console.error(`  FAIL ${name}${detail ? `: ${detail}` : ""}`);
  }
}

// ---- 1. WA-only guard -------------------------------------------------------
const baseWA: BuyerProfile = {
  region: "WA",
  anchor: "Como",
  income: 150000,
  life_stage: "young_family",
  finances: { deposit: 150000 },
};

ok("resolves a valid WA profile", (() => {
  try { resolveProfile(baseWA); return true; } catch { return false; }
})());

ok("rejects a non-WA region", (() => {
  try { resolveProfile({ ...baseWA, region: "NSW" as unknown as "WA" }); return false; }
  catch { return true; }
})());

ok("rejects an unknown anchor suburb", (() => {
  try { resolveProfile({ ...baseWA, anchor: "Sydney" }); return false; }
  catch { return true; }
})());

ok("anchor matching is case-insensitive", (() => {
  try { resolveProfile({ ...baseWA, anchor: "como" }); return true; } catch { return false; }
})());

// ---- 2. Budget is monotonic in income --------------------------------------
const cap100 = borrowingCapacity(100000);
const cap200 = borrowingCapacity(200000);
ok("borrowing capacity rises with income", cap200 > cap100, `${cap100} -> ${cap200}`);

const commitFree = borrowingCapacity(150000, 0);
const withCommit = borrowingCapacity(150000, 1500);
ok("monthly commitments reduce borrowing capacity", withCommit < commitFree, `${commitFree} -> ${withCommit}`);

const bLow = budgetBand({ ...baseWA, income: 90000 });
const bHigh = budgetBand({ ...baseWA, income: 220000 });
ok("budget ceiling rises with income", bHigh.ceiling > bLow.ceiling, `${bLow.ceiling} -> ${bHigh.ceiling}`);
ok("budget floor is below the ceiling", bLow.floor < bLow.ceiling && bHigh.floor < bHigh.ceiling);

const moreFunds = budgetBand({ ...baseWA, finances: { deposit: 400000 } });
const lessFunds = budgetBand({ ...baseWA, finances: { deposit: 100000 } });
ok("more own funds lifts the ceiling", moreFunds.ceiling > lessFunds.ceiling, `${lessFunds.ceiling} -> ${moreFunds.ceiling}`);

// ---- 3. The two-buyer timing contrast (the core of the brief) --------------
// "someone who has a small deposit and available cash should not buy in the
//  same period as someone with large cash and a 0% line of credit."
const cashRich: BuyerProfile = {
  region: "WA",
  anchor: "Como",
  age: 36,
  income: 240000,
  life_stage: "young_family",
  finances: { deposit: 200000, cash_buffer: 600000, credit_line: 800000, credit_rate_pct: 0, currently_renting: false },
  horizon_years: 3,
};
const firstHome: BuyerProfile = {
  region: "WA",
  anchor: "Bayswater",
  age: 28,
  income: 95000,
  life_stage: "young_couple",
  finances: { deposit: 55000, cash_buffer: 8000, credit_line: 0, currently_renting: true, monthly_commitments: 600 },
  horizon_years: 2,
};
const rRich = resolveProfile(cashRich);
const rFirst = resolveProfile(firstHome);

ok("cash-rich buyer is patient-opportunistic", rRich.timing.posture === "patient-opportunistic", rRich.timing.posture);
ok("cash-rich buyer urgency is low (<40)", rRich.timing.urgency < 40, `${rRich.timing.urgency}`);
ok("first-home buyer is act-now", rFirst.timing.posture === "act-now", rFirst.timing.posture);
ok("first-home buyer urgency is high (>=65)", rFirst.timing.urgency >= 65, `${rFirst.timing.urgency}`);
ok("the two buyers occupy different buy windows", rRich.timing.posture !== rFirst.timing.posture);
ok("cash-rich buyer has the bigger budget", rRich.budget.ceiling > rFirst.budget.ceiling);

// 0% facility is what tips an otherwise-balanced buyer to patient.
const sameButCostlyCredit = resolveProfile({ ...cashRich, finances: { ...cashRich.finances!, credit_rate_pct: 7 } });
ok("a 0% facility lowers urgency vs a 7% one", rRich.timing.urgency < sameButCostlyCredit.timing.urgency,
  `${rRich.timing.urgency} < ${sameButCostlyCredit.timing.urgency}`);

// ---- 4. The ranking follows the anchor (proximity is dynamic) --------------
const comoRank = rankSuburbsForProfile(rRich);
const northProfile: BuyerProfile = { ...cashRich, anchor: "Dianella" };
const northRank = rankSuburbsForProfile(resolveProfile(northProfile));
const comoDistComo = comoRank.find((s) => s.name === "Como")!.km;
const northDistComo = northRank.find((s) => s.name === "Como")!.km;
ok("Como is ~0km from a Como anchor", comoDistComo < 0.5, `${comoDistComo}`);
ok("Como is far from a Dianella anchor", northDistComo > 10, `${northDistComo}`);
ok("the top-ranked suburb changes with the anchor",
  comoRank[0]!.name !== northRank[0]!.name || comoRank[0]!.km !== northRank[0]!.km);

// ---- 5. Weights always normalise to 1 --------------------------------------
const sum = (Object.values(rRich.weights) as number[]).reduce((a, b) => a + b, 0);
ok("criteria weights sum to 1", Math.abs(sum - 1) < 1e-9, `${sum}`);

const customCriteria = resolveProfile({
  ...baseWA,
  criteria: { growth: 5, schools: 0, family: 0, land: 0, proximity: 0, amenity: 0, project: 0 },
});
const cSum = (Object.values(customCriteria.weights) as number[]).reduce((a, b) => a + b, 0);
ok("custom criteria weights also sum to 1", Math.abs(cSum - 1) < 1e-9, `${cSum}`);
ok("a single-dimension profile concentrates weight there", customCriteria.weights.growth === 1, `${customCriteria.weights.growth}`);

// ---- 6. Onboarding mapping round-trips into a resolvable profile -----------
const fromAnswers = profileFromAnswers({
  region: "WA",
  anchor: "Shelley",
  age: 34,
  income: 180000,
  deposit: 250000,
  currently_renting: false,
  life_stage: "young_family",
  min_beds: 4,
  min_land: 500,
});
ok("onboarding answers resolve into a working profile", (() => {
  try {
    const r = resolveProfile(fromAnswers);
    return r.anchor.name === "Shelley" && r.filters.min_beds === 4 && r.filters.min_land === 500;
  } catch { return false; }
})());

console.log(`\nprofile: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
