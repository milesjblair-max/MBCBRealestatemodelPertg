// M1 proof: the WA-wide base layer lets the model anchor ANYWHERE in WA, and
// returns the real nearby suburbs. This is the test that proves "anchor Mandurah"
// works - the thing the curated 14-suburb model structurally could not do.

import { WA_SUBURBS, findWaSuburb, nearbyWaSuburbs } from "../src/baselayer.js";

let pass = 0;
let fail = 0;
function ok(name: string, cond: boolean, detail = ""): void {
  if (cond) pass++;
  else {
    fail++;
    console.error(`  FAIL ${name}${detail ? `: ${detail}` : ""}`);
  }
}

// Coverage: a real, state-wide base layer (not 14).
ok("base layer covers most of WA", WA_SUBURBS.length > 1500, `${WA_SUBURBS.length}`);

// Anchor anywhere: metro, Peel, and regional centres all resolve.
for (const s of ["Como", "Mandurah", "Albany", "Geraldton", "Kalgoorlie", "Broome"]) {
  ok(`resolves anchor ${s}`, !!findWaSuburb(s), "not found");
}
ok("anchor lookup is case-insensitive", !!findWaSuburb("mAnDuRaH"));
ok("unknown anchor is undefined", findWaSuburb("Sydney") === undefined);

// The Mandurah example, proven from real coordinates.
const m = nearbyWaSuburbs("Mandurah", { limit: 12, maxKm: 12 });
const names = m.nearby.map((s) => s.name);
ok("Mandurah returns nearby suburbs", m.nearby.length >= 5, `${m.nearby.length}`);
for (const expect of ["Halls Head", "Erskine", "Greenfields"]) {
  ok(`Mandurah neighbours include ${expect}`, names.includes(expect), names.slice(0, 8).join(", "));
}
ok("nearby are sorted by distance", m.nearby.every((s, i, a) => i === 0 || a[i - 1]!.km <= s.km));
ok("nearby respect the radius", m.nearby.every((s) => s.km <= 12));
ok("anchor is excluded from its own nearby list", !names.includes("Mandurah"));

// A different anchor returns a different neighbourhood (truly dynamic).
const como = nearbyWaSuburbs("Como", { limit: 6, maxKm: 6 }).nearby.map((s) => s.name);
ok("Como neighbours differ from Mandurah's", !como.some((n) => names.includes(n)), `${como.join(", ")}`);

// Unknown anchor throws cleanly.
ok("nearbyWaSuburbs throws on unknown anchor", (() => {
  try { nearbyWaSuburbs("Atlantis"); return false; } catch { return true; }
})());

console.log(`\nbaselayer: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
