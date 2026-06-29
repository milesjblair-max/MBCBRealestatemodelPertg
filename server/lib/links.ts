// Deep-links into the full interactive HTML tool, which the app serves at
// /tool.html (published by scripts/sync-engine.mjs). The MCP returns one of these
// so the user can open the real fan chart, heat map and listing tiles, pre-set
// to match what they asked for in chat. The HTML reads these query params
// (prior, bear/base/bull, tab) and hydrates its controls on load.

/** The public base URL of this deployment. Vercel sets the production domain in
 *  VERCEL_PROJECT_PRODUCTION_URL; fall back to the known production host. */
export function baseUrl(): string {
  const env =
    process.env.PUBLIC_BASE_URL ||
    process.env.VERCEL_PROJECT_PRODUCTION_URL ||
    "mbcb-realestatemodel-pertg.vercel.app";
  return env.startsWith("http") ? env.replace(/\/$/, "") : `https://${env}`;
}

export type ToolTab = "listings" | "modelling" | "construction" | "criteria";

export interface ToolViewParams {
  tab?: ToolTab; // which section to open
  prior?: number; // proximity-vs-schools slider, 0 (proximity) .. 100 (schools)
  weights?: { bear?: number; base?: number; bull?: number }; // scenario weights
}

/** Derive the proximity-vs-schools slider position (0..100) from resolved
 *  weights, so a deep-link built from a tool result reflects the buyer. */
export function priorFromWeights(school: number, prox: number): number {
  const sum = school + prox;
  if (sum <= 0) return 50;
  return Math.round((school / sum) * 100);
}

/** Map a buyer's stated priority to the HTML's proximity-vs-schools slider. */
export function priorFromPriority(priority?: string): number | undefined {
  switch ((priority ?? "").toLowerCase()) {
    case "schools":
      return 85;
    case "proximity":
      return 15;
    case "balanced":
      return 50;
    default:
      return undefined;
  }
}

/** Build a deep-link to the interactive tool with the view pre-set. */
export function toolUrl(p: ToolViewParams = {}): string {
  const q = new URLSearchParams();
  if (p.tab) q.set("tab", p.tab);
  if (p.prior != null) q.set("prior", String(Math.round(p.prior)));
  if (p.weights?.bear != null) q.set("bear", String(Math.round(p.weights.bear)));
  if (p.weights?.base != null) q.set("base", String(Math.round(p.weights.base)));
  if (p.weights?.bull != null) q.set("bull", String(Math.round(p.weights.bull)));
  const qs = q.toString();
  return `${baseUrl()}/tool.html${qs ? `?${qs}` : ""}`;
}
