// GET /dashboard?anchor=...&income=...  ->  the server-rendered dashboard.
// Runs the engine on the query params and returns a complete HTML page. Not
// behind the bearer gate (the MCP route is); this is a viewable page.

import { buildDashboardHtml } from "@/lib/dashboard";
import type { BuyerProfile, CriteriaInput, LifeStage } from "@/lib/engine/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function criteriaFor(priority: string | null): CriteriaInput | undefined {
  switch ((priority ?? "").toLowerCase()) {
    case "schools": return { schools: 5, proximity: 2 };
    case "proximity": return { proximity: 5, schools: 3 };
    case "land": return { land: 5 };
    default: return undefined;
  }
}

export function GET(req: Request): Response {
  const sp = new URL(req.url).searchParams;

  // Preferred: a lossless base64url profile blob (what the tools emit).
  const blob = sp.get("p");
  if (blob) {
    try {
      const profile = JSON.parse(Buffer.from(blob, "base64url").toString("utf8")) as BuyerProfile;
      const { html, status } = buildDashboardHtml(profile);
      return new Response(html, { status, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });
    } catch {
      // fall through to readable params
    }
  }

  const num = (k: string): number | undefined => {
    const v = sp.get(k);
    return v == null || v === "" || isNaN(+v) ? undefined : +v;
  };
  const renting = sp.get("renting");

  const profile: BuyerProfile = {
    region: "WA",
    anchor: sp.get("anchor") ?? "",
    income: num("income"),
    finances: {
      deposit: num("deposit"),
      cash_buffer: num("cash_buffer"),
      credit_line: num("credit_line"),
      credit_rate_pct: num("credit_rate_pct"),
      equity_release: num("equity_release"),
      equity_rate_pct: num("equity_rate_pct"),
      currently_renting: renting == null ? undefined : renting === "1" || renting.toLowerCase() === "true" || renting.toLowerCase() === "yes",
    },
    life_stage: (sp.get("life_stage") as LifeStage | null) ?? undefined,
    criteria: criteriaFor(sp.get("priority")),
    filters: { max_distance_km: num("max_distance_km") },
    horizon_years: num("horizon_years"),
  };

  const { html, status } = buildDashboardHtml(profile);
  return new Response(html, {
    status,
    headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" },
  });
}
