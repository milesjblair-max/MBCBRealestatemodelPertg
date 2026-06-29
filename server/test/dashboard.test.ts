// The server-rendered dashboard, tested. This is the thing I could not test when
// the client model hand-drew the artifact: here the HTML is built on the server,
// so we assert it actually contains the engine's numbers, an inline SVG chart,
// and - critically - NO external script (the blank-chart failure came from an
// artifact sandbox blocking a CDN <script>; this page has zero JS, so it cannot
// go blank).

import { buildDashboardHtml } from "../lib/dashboard.js";
import type { BuyerProfile } from "../lib/engine/types.js";

let pass = 0;
let fail = 0;
function ok(name: string, cond: boolean, detail = ""): void {
  if (cond) pass++;
  else {
    fail++;
    console.error(`  FAIL ${name}${detail ? `: ${detail}` : ""}`);
  }
}

const comoModest: BuyerProfile = {
  region: "WA",
  anchor: "Como",
  income: 180000,
  finances: { deposit: 250000 },
  life_stage: "young_family",
  criteria: { schools: 5, proximity: 2 },
  filters: { max_distance_km: 10 },
};

const r = buildDashboardHtml(comoModest);
ok("renders with 200", r.status === 200, `${r.status}`);
ok("is a full HTML document", r.html.startsWith("<!doctype html>"));
ok("is branded as the engine", r.html.includes("wa-home-model"));
ok("states WA scope", r.html.includes("Western Australia"));
ok("shows the affordability headline (priced out of Como)", r.html.includes("Priced out of Como"), "anchor unreachable on this budget");
ok("draws an inline SVG chart", r.html.includes("<svg") && r.html.includes("<polyline"));
ok("labels the buyer's ceiling on the chart", r.html.includes("your ceiling"));
ok("has the budget and borrowing cards", r.html.includes("Budget band") && r.html.includes("Borrowing capacity"));
ok("has a suburb heat table with the anchor tagged", r.html.includes("anchor</span>"));

// The whole point: no external/inline script, so nothing for a sandbox to block.
ok("contains NO script tag (cannot go blank)", !r.html.includes("<script"), "found a script tag");
ok("loads nothing from a CDN", !/src=["']https?:\/\//i.test(r.html));

// A reachable buyer flips the headline.
const bentleyRich = buildDashboardHtml({
  region: "WA",
  anchor: "Bentley",
  income: 240000,
  finances: { deposit: 200000, cash_buffer: 600000, credit_line: 800000, credit_rate_pct: 0 },
  life_stage: "young_family",
});
ok("a reachable anchor reads 'within reach'", bentleyRich.html.includes("is within reach"));

// Out-of-scope anchor is a clean 400, not a crash.
const bad = buildDashboardHtml({ region: "WA", anchor: "Sydney" } as BuyerProfile);
ok("unknown anchor returns 400", bad.status === 400, `${bad.status}`);
ok("400 page explains WA-only", bad.html.includes("WA only"));

console.log(`\ndashboard: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
