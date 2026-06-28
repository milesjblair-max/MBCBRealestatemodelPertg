// parity.ts - prove the TypeScript engine matches the Python model to the dollar.
//
// It runs gen_fixtures.py (the Python source of truth), then runs the SAME
// inputs through the TS engine and compares every number. Exits non-zero on any
// mismatch, so it can gate a deploy. This is the test that lets us trust the
// port - and the headline artefact of Phase 1.

import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { estimate } from "../src/avm.js";
import { scoreSuburb } from "../src/scoring.js";
import { buildTimeline, metrics, BASELINE_WEIGHTS } from "../src/scenario.js";
import { BASELINE } from "../src/data.js";

const here = dirname(fileURLToPath(import.meta.url));

interface Fixture {
  tool: "estimate" | "score";
  input: Record<string, unknown>;
  expected: Record<string, unknown>;
}

let pass = 0;
let fail = 0;
function check(name: string, got: unknown, want: unknown): void {
  const ok = got === want;
  if (ok) pass++;
  else {
    fail++;
    console.error(`  MISMATCH ${name}: ts=${JSON.stringify(got)} py=${JSON.stringify(want)}`);
  }
}

// 1. Run the Python reference and load its numbers.
const raw = execFileSync("python3", [join(here, "gen_fixtures.py")], { encoding: "utf8" });
const fixtures: Fixture[] = JSON.parse(raw);
console.log(`Loaded ${fixtures.length} fixtures from the Python model.`);

// 2. Re-run each through the TS engine and compare.
for (const f of fixtures) {
  if (f.tool === "estimate") {
    const i = f.input as { suburb: string; land?: number; beds?: number; baths?: number; condition?: string };
    const r = estimate(i.suburb, i.land ?? null, i.beds ?? null, i.baths ?? null, i.condition ?? null);
    const tag = `estimate(${i.suburb},${i.land ?? "-"},${i.beds ?? "-"},${i.baths ?? "-"},${i.condition ?? "-"})`;
    check(`${tag}.likely`, r.likely, f.expected.likely);
    check(`${tag}.low`, r.low, f.expected.low);
    check(`${tag}.high`, r.high, f.expected.high);
    check(`${tag}.guide_floor`, r.guideFloor, f.expected.guide_floor);
    check(`${tag}.spread_pct`, r.spreadPct, f.expected.spread_pct);
    check(`${tag}.confidence`, r.confidence, f.expected.confidence);
    check(`${tag}.in_band`, r.inBand, f.expected.in_band);
  } else if (f.tool === "score") {
    const i = f.input as { suburb: string; prior: number };
    const r = scoreSuburb(i.suburb, i.prior);
    check(`score(${i.suburb},${i.prior}).score`, r.score, f.expected.score);
    check(`score(${i.suburb},${i.prior}).over`, r.over, f.expected.over);
  }
}

// 3. Scenario: the TS timeline at the baseline weights must equal baseline.json
//    (which is itself the committed Python output).
const tl = buildTimeline(BASELINE_WEIGHTS);
for (let i = 0; i < tl.length; i++) {
  for (const k of ["bear", "base", "bull", "expected"] as const) {
    check(`timeline[${i}].${k}`, tl[i]![k], BASELINE.timeline[i]![k]);
  }
}
const m = metrics(tl);
for (const k of ["expected_mid29", "bear_trough", "bull_mid29", "cost_of_waiting_to_end27_bull"] as const) {
  check(`metrics.${k}`, m[k], BASELINE.key_numbers[k]);
}

console.log(`\nparity: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
