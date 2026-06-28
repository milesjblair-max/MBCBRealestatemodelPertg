// The Como engine: the model logic, decoupled from any UI or transport.
// Phase 2 (the MCP server) will import these functions and expose each as a
// tool; the HTML tool can eventually import the same functions too.

export { estimate } from "./avm.js";
export { scoreSuburb, scoreSuburbObj, rank } from "./scoring.js";
export { buildTimeline, metrics, BASELINE_WEIGHTS } from "./scenario.js";
export { assessProperty } from "./assess.js";
export { SUBURBS, CRITERIA_WEIGHTS, BASELINE, findSuburb } from "./data.js";
export type { Suburb, Estimate, Condition } from "./types.js";

// Run `npm run demo` to see the engine working end to end.
import { estimate } from "./avm.js";
import { rank } from "./scoring.js";
import { buildTimeline, metrics } from "./scenario.js";
import { assessProperty } from "./assess.js";
import { fmtK } from "./util.js";

function isMain(): boolean {
  return import.meta.url === `file://${process.argv[1]}`;
}

if (isMain()) {
  console.log("== Como engine demo ==\n");

  const e = estimate("Como", 1100, 4, 3, "good");
  console.log(`Estimate  31 Saunders St style (Como, 1100sqm, 4/3, good):`);
  console.log(`  likely ${fmtK(e.likely)}  range ${fmtK(e.low)}-${fmtK(e.high)}  (${e.confidence})\n`);

  console.log("Top 5 suburbs (balanced prior):");
  for (const s of rank(50).slice(0, 5)) console.log(`  ${s.score.toFixed(1)}  ${s.name}`);

  const f = metrics(buildTimeline());
  console.log(`\nForecast  expected Mid-29 ${fmtK(f.expected_mid29 / 1000)}, bear trough ${fmtK(f.bear_trough / 1000)}\n`);

  const a = assessProperty("Shelley", 696, 3, 1, "original");
  console.log(`Assess    Shelley 3/1/696 original: fit ${a.fit}/100, ${a.pros.length} pros, ${a.cons.length} cons`);
}
