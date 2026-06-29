// The WA Home Model engine: model logic decoupled from any UI or transport.
// Phase 2 (the MCP server) imports these and exposes each as a tool.

// Price estimator (unchanged, buyer-agnostic)
export { estimate } from "./avm.js";
export { assessProperty } from "./assess.js";

// Original (hardcoded-Como) scoring + forecast, kept for the existing tool/parity
export { scoreSuburb, scoreSuburbObj, rank } from "./scoring.js";
export { buildTimeline, metrics, BASELINE_WEIGHTS } from "./scenario.js";

// Dynamic, profile-driven layer (multi-user)
export { resolveProfile, resolveWeights } from "./profile.js";
export { borrowingCapacity, budgetBand, buyTiming } from "./finance.js";
export { rankSuburbsForProfile, scoreSuburbForProfile, matchListings } from "./recommend.js";
export { ONBOARDING_QUESTIONS, profileFromAnswers } from "./onboarding.js";
export { distanceKm, proximityScore } from "./geo.js";

// WA-wide base layer (anchor anywhere in WA, not just the curated 14)
export { WA_SUBURBS, findWaSuburb, nearbyWaSuburbs } from "./baselayer.js";

export { SUBURBS, CRITERIA_WEIGHTS, BASELINE, findSuburb, loadListings } from "./data.js";
export type { Suburb, Estimate, Condition, BuyerProfile, ResolvedProfile } from "./types.js";

// ---- demo: `npm run demo` ----
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { resolveProfile } from "./profile.js";
import { rankSuburbsForProfile, matchListings } from "./recommend.js";
import { loadListings } from "./data.js";
import { fmtDollars } from "./util.js";
import type { BuyerProfile } from "./types.js";

function isMain(): boolean {
  return import.meta.url === `file://${process.argv[1]}`;
}

function showProfile(label: string, file: string): void {
  const here = dirname(fileURLToPath(import.meta.url));
  const raw = JSON.parse(readFileSync(join(here, "..", "..", "data", "profiles", file), "utf8")) as BuyerProfile;
  const rp = resolveProfile(raw);
  console.log(`\n== ${label} (anchor: ${rp.anchor.name}) ==`);
  console.log(`  budget    ${fmtDollars(rp.budget.floor)} - ${fmtDollars(rp.budget.ceiling)}  (borrowing cap ${fmtDollars(rp.budget.borrowingCapacity)})`);
  console.log(`  timing    ${rp.timing.posture.toUpperCase()} (urgency ${rp.timing.urgency}/100)`);
  console.log(`            ${rp.timing.rationale[0]}`);
  const top = rankSuburbsForProfile(rp).slice(0, 3);
  console.log(`  top areas ${top.map((s) => `${s.name} ${s.score}`).join(", ")}`);
  const listings = matchListings(rp, loadListings());
  console.log(`  listings  ${listings.length} match the budget/filters; best fit: ${listings[0]?.suburb ?? "none"}`);
}

if (isMain()) {
  console.log("== WA Home Model engine: same market, two different buyers ==");
  showProfile("Cash-rich family, 0% facility", "como-family-patient.json");
  showProfile("First-home buyer, small deposit, renting", "first-home-small-deposit.json");
  console.log("\nNote how budget, buy-timing and the suburb ranking all shift with the profile.");
}
