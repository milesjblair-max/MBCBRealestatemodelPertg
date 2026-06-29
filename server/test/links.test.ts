// Deterministic tests for the deep-link builder (the hybrid's hand-off to the
// full HTML tool). No network, no aliases - just URL correctness, so it runs in
// the deploy gate. Prompt registration and types are covered by `tsc` + the
// build; the live prompts/list is smoke-tested separately.

import { toolUrl, priorFromPriority, baseUrl } from "../lib/links.js";

let pass = 0;
let fail = 0;
function ok(name: string, cond: boolean, detail = ""): void {
  if (cond) pass++;
  else {
    fail++;
    console.error(`  FAIL ${name}${detail ? `: ${detail}` : ""}`);
  }
}

// baseUrl falls back to the production host and is always https with no trailing slash.
const b = baseUrl();
ok("baseUrl is https", b.startsWith("https://"), b);
ok("baseUrl has no trailing slash", !b.endsWith("/"), b);

// priority maps to the proximity-vs-schools slider.
ok("schools -> high prior", priorFromPriority("schools") === 85);
ok("proximity -> low prior", priorFromPriority("proximity") === 15);
ok("balanced -> mid prior", priorFromPriority("balanced") === 50);
ok("unknown -> undefined", priorFromPriority("whatever") === undefined);
ok("empty -> undefined", priorFromPriority(undefined) === undefined);

// toolUrl points at /tool.html and encodes only the params given.
const plain = toolUrl();
ok("plain url targets tool.html", plain.endsWith("/tool.html"), plain);

const full = toolUrl({ tab: "modelling", prior: 85, weights: { bear: 30, base: 50, bull: 20 } });
ok("url has tool.html path", full.includes("/tool.html?"), full);
ok("url carries tab", full.includes("tab=modelling"), full);
ok("url carries prior", full.includes("prior=85"), full);
ok("url carries weights", full.includes("bear=30") && full.includes("base=50") && full.includes("bull=20"), full);

const listings = toolUrl({ tab: "listings" });
ok("listings url has the listings tab", listings.includes("tab=listings"), listings);
ok("listings url omits absent params", !listings.includes("prior=") && !listings.includes("bear="), listings);

// rounding: fractional prior is rounded in the URL.
ok("prior is rounded", toolUrl({ prior: 84.6 }).includes("prior=85"), toolUrl({ prior: 84.6 }));

console.log(`\nlinks: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
