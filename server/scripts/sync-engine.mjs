// sync-engine.mjs - vendor the canonical engine and data into the server so the
// Vercel deploy is fully self-contained (no reliance on parent directories
// existing at build time).
//
// Source of truth stays mcp/src/*.ts and data/*.json at the repo root. This
// script copies them verbatim into server/lib/engine and server/data. The
// deploy gate (tests/run.sh) runs this and fails if the committed copies have
// drifted, so the single-source-of-truth rule is enforced, not just hoped for.
//
// Why the relative paths line up: the engine's data.ts imports
// "../../data/*.json". From mcp/src that is the repo's data/; from the vendored
// copy at server/lib/engine that is server/data/ - same relative shape, so the
// identical file is correct in both trees.
//
// Run by `npm run sync` (and predev/prebuild). If the canonical sources are not
// present (an isolated upload of just server/), it no-ops and the committed
// copies are used.

import { cpSync, copyFileSync, existsSync, mkdirSync, rmSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const serverRoot = join(here, "..");
const repoRoot = join(serverRoot, "..");

const engineSrc = join(repoRoot, "mcp", "src");
const dataSrc = join(repoRoot, "data");
const engineDst = join(serverRoot, "lib", "engine");
const dataDst = join(serverRoot, "data");
// The interactive HTML tool, published into the app's public/ so the deep-link
// (built in lib/links.ts) can open the full visual experience at /tool.html.
const htmlSrc = join(repoRoot, "index.html");
const htmlDst = join(serverRoot, "public", "tool.html");

if (!existsSync(engineSrc) || !existsSync(dataSrc)) {
  console.log("[sync] canonical mcp/src or data/ not found; using committed copies.");
  process.exit(0);
}

function resync(src, dst, label) {
  rmSync(dst, { recursive: true, force: true });
  mkdirSync(dst, { recursive: true });
  cpSync(src, dst, { recursive: true });
  const n = readdirSync(dst).length;
  console.log(`[sync] ${label}: ${n} entries -> ${dst.replace(repoRoot + "/", "")}`);
}

resync(engineSrc, engineDst, "engine");
resync(dataSrc, dataDst, "data");

if (existsSync(htmlSrc)) {
  mkdirSync(dirname(htmlDst), { recursive: true });
  copyFileSync(htmlSrc, htmlDst);
  console.log("[sync] html: index.html -> server/public/tool.html");
}
console.log("[sync] done. server/lib/engine and server/data are generated; edit mcp/src and data/ instead.");
