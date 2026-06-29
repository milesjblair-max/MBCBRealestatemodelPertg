// The MCP server. Each engine function from Phase 1 is exposed here as one MCP
// tool over Streamable HTTP, via Vercel's mcp-handler. The handler is stateless
// (no Redis), so it runs on a single Vercel serverless function.
//
// Route shape: this file is app/api/[transport]/route.ts and the handler is
// created with basePath "/api", so the MCP endpoint is  POST /api/mcp .
//
// The hard correctness work was done in Phase 1: this layer is schema -> call
// engine -> return. The engine is the same parity-tested code (vendored into
// lib/engine), so the tools inherit its to-the-dollar agreement with the Python
// model.

import { createMcpHandler } from "mcp-handler";
import { z } from "zod";

import { estimate } from "@/lib/engine/avm";
import { assessProperty } from "@/lib/engine/assess";
import { buildTimeline, metrics, BASELINE_WEIGHTS } from "@/lib/engine/scenario";
import { resolveProfile } from "@/lib/engine/profile";
import { rankSuburbsForProfile, matchListings } from "@/lib/engine/recommend";
import { ONBOARDING_QUESTIONS } from "@/lib/engine/onboarding";
import { SUBURBS, loadListings } from "@/lib/engine/data";
import { nearbyWaSuburbs } from "@/lib/engine/baselayer";
import type { BuyerProfile } from "@/lib/engine/types";

import { ProfileSchema, CONDITIONS } from "@/lib/schema";
import { searchListingsLive } from "@/lib/listings-live";
import { checkBearer } from "@/lib/auth";
import { registerPrompts } from "@/lib/prompts";
import { toolUrl, dashboardUrl } from "@/lib/links";

// The live-listings tool calls an external API and reads env vars, so the route
// must run on the Node.js runtime, not the Edge runtime.
//
// maxDuration is 300s: with Fluid Compute enabled (server/vercel.json) the
// platform keeps a warm instance and can hold a streaming MCP response open for
// the whole call, so a long tool turn (e.g. several live-listing fetches) will
// not be cut off. Mirrored in vercel.json so the limit is explicit either way.
export const runtime = "nodejs";
export const maxDuration = 300;

// Every tool result is prefixed with this so the user always knows the real
// (Western-Australia-scoped) tool produced the answer, not the model guessing.
const SCOPE = "Como home model - Western Australia (Perth) only.";
const json = (data: unknown) => ({
  content: [
    { type: "text" as const, text: SCOPE },
    { type: "text" as const, text: JSON.stringify(data, null, 2) },
  ],
});

const handler = createMcpHandler(
  (server) => {
    // ---- Price estimator (buyer-agnostic, parity-tested) -------------------
    server.tool(
      "estimate_price",
      "Estimate the likely sale price of a WA house from its suburb and (optional) land size, beds, baths and condition. Returns a likely figure, a low-high range, the typical advertised guide floor, and a confidence level.",
      {
        suburb: z.string().describe("A suburb in the dataset, e.g. 'Shelley'."),
        land: z.number().positive().optional().describe("Land size in sqm."),
        beds: z.number().int().positive().optional(),
        baths: z.number().int().positive().optional(),
        condition: z.enum(CONDITIONS).optional().describe("Property condition."),
      },
      async ({ suburb, land, beds, baths, condition }) =>
        json(estimate(suburb, land ?? null, beds ?? null, baths ?? null, condition ?? null)),
    );

    // ---- Full property assessment (estimate + fit + pros/cons) -------------
    server.tool(
      "assess_property",
      "Assess a specific property end to end: price estimate plus a buyer-fit read with plain-English pros and cons (land, bedrooms, KDR optionality, school zone, distance).",
      {
        suburb: z.string(),
        land: z.number().positive().optional(),
        beds: z.number().int().positive().optional(),
        baths: z.number().int().positive().optional(),
        condition: z.enum(CONDITIONS).optional(),
        prior: z.number().min(0).max(100).optional().describe("Proximity-vs-schools slider, 0 (proximity) to 100 (schools). Default 50."),
      },
      async ({ suburb, land, beds, baths, condition, prior }) =>
        json(assessProperty(suburb, land ?? null, beds ?? null, baths ?? null, condition ?? null, prior ?? 50)),
    );

    // ---- Forecast (scenario fan chart + headline metrics) ------------------
    server.tool(
      "forecast",
      "Run the scenario forecast for a ~$1.0M Perth house to Mid-29. Optionally pass bear/base/bull weights (they are normalised); omit for the 30/50/20 baseline. Returns the bear/base/bull/expected timeline and headline metrics.",
      {
        bear: z.number().min(0).max(100).optional(),
        base: z.number().min(0).max(100).optional(),
        bull: z.number().min(0).max(100).optional(),
      },
      async ({ bear, base, bull }) => {
        const weights =
          bear == null && base == null && bull == null
            ? BASELINE_WEIGHTS
            : { bear: bear ?? 0, base: base ?? 0, bull: bull ?? 0 };
        const timeline = buildTimeline(weights);
        return json({ weights, timeline, metrics: metrics(timeline) });
      },
    );

    // Note: there is deliberately ONE suburb-ranking path, rank_suburbs_for_profile,
    // so a caller cannot accidentally get a stale answer. The original Como buyer is
    // just a profile you can pass to it; there is no separate fixed-Como tool.

    // ---- Reference data -----------------------------------------------------
    server.tool(
      "list_suburbs",
      "List the WA suburbs the engine knows, with postcode, median range ($000s) and whether they sit in the original $800k-$1.1M band. Useful before choosing an anchor.",
      {},
      async () =>
        json(
          SUBURBS.map((s) => ({ name: s.name, pc: s.pc, region: s.reg, median_k: [s.mlo, s.mhi], in_band: s.band })),
        ),
    );

    server.tool(
      "nearby_suburbs",
      "Find the WA suburbs nearest ANY anchor - anchor anywhere in WA (Mandurah, Albany, Geraldton, not just the curated set). Returns real suburbs sorted by distance from the WA-wide base layer (~1800 suburbs). This is geographic coverage; price and fit scoring for arbitrary suburbs is being layered on next.",
      {
        anchor: z.string().describe("Any WA suburb to centre on, e.g. 'Mandurah'."),
        radius_km: z.number().positive().optional().describe("Max distance from the anchor in km. Default 15."),
        limit: z.number().int().min(1).max(50).optional().describe("How many suburbs to return. Default 12."),
      },
      async ({ anchor, radius_km, limit }) => {
        try {
          return json(nearbyWaSuburbs(anchor, { maxKm: radius_km, limit }));
        } catch (e) {
          return json({ error: (e as Error).message });
        }
      },
    );

    server.tool(
      "onboarding_questions",
      "Return the onboarding question set the MCP asks a new buyer (region, anchor, age, income, finances, life stage, criteria, filters). Ask these, then call resolve_profile.",
      {},
      async () => json(ONBOARDING_QUESTIONS),
    );

    server.tool(
      "capabilities",
      "What this connector is, what it can do, and how to use it. Call this first (or whenever the user asks what this does) and present it before anything else.",
      {},
      async () =>
        json({
          name: "Como home model",
          scope: "Western Australia (Perth) only",
          what:
            "A house-price and suburb-fit engine for a WA buyer. Tell it where you want to live, your income and cash, and what matters, and it works out a realistic budget, whether you can afford your anchor suburb, a buy-timing call, a ranked shortlist of suburbs, matching listings, and a market forecast - with a one-click visual dashboard.",
          start_here:
            "Give your anchor suburb + income + deposit + what matters most (schools / proximity / land). I will resolve your profile and return a dashboard link. No commands to memorise.",
          what_it_can_do: [
            "Anchor ANYWHERE in WA and find the nearest real suburbs (nearby_suburbs) - ~1800 suburbs, e.g. Mandurah returns Halls Head, Erskine, Greenfields",
            "Estimate a specific house's price and fit (estimate_price, assess_property)",
            "Resolve your budget, affordability gap to your anchor, and buy-timing (resolve_profile)",
            "Rank the model's curated WA suburb set for you and count which are viable (rank_suburbs_for_profile)",
            "Match current listings to your filters (match_listings, search_listings)",
            "Forecast the market to mid-2029 across bear/base/bull (forecast)",
            "Open a full visual dashboard for your profile (every tool returns dashboardUrl)",
          ],
          prompts: ["find_a_home", "see_listings", "estimate_a_listing", "about_this_tool"],
          suburbs: SUBURBS.map((s) => s.name),
          coverage:
            `Geographic coverage is now WA-wide: ~1800 suburbs in the base layer, so you can anchor anywhere ` +
            `(use nearby_suburbs). Rich fit-scoring (budget + criteria + listings) currently runs on the ${SUBURBS.length} ` +
            `curated suburbs; for an anchor outside that set, nearby_suburbs returns the real neighbours but price/fit ` +
            `scoring for them is still being layered in. Be honest about which suburbs are fully scored vs only located.`,
          example_dashboard: dashboardUrl({
            region: "WA",
            anchor: "Como",
            income: 180000,
            finances: { deposit: 250000 },
            life_stage: "young_family",
            criteria: { schools: 5, proximity: 2 },
            filters: { max_distance_km: 10 },
          }),
          not_advice: "General information only, not financial advice.",
        }),
    );

    // ---- Dynamic, profile-driven layer (multi-user) ------------------------
    server.tool(
      "resolve_profile",
      "Resolve a WA buyer profile into the working parameters the engine scores with: a budget band (from income + funds), a buy-timing posture (act-now / balanced / patient-opportunistic, with the why), and normalised criteria weights. Errors clearly if the region is not WA or the anchor is unknown.",
      { profile: ProfileSchema },
      async ({ profile }) => {
        try {
          const rp = resolveProfile(profile as BuyerProfile);
          return json({ ...rp, dashboardUrl: dashboardUrl(profile) });
        } catch (e) {
          return json({ error: (e as Error).message });
        }
      },
    );

    server.tool(
      "rank_suburbs_for_profile",
      "Rank the suburbs for a specific buyer: their anchor sets the (live haversine) proximity, their criteria set the weights, their budget penalises over-budget areas. Returns suburbs sorted by fit, plus the resolved budget and timing.",
      { profile: ProfileSchema },
      async ({ profile }) => {
        try {
          const rp = resolveProfile(profile as BuyerProfile);
          const ranking = rankSuburbsForProfile(rp);
          const ring = rp.filters.max_distance_km;
          const inRing = (s: { km: number }) => ring == null || s.km <= ring;
          const viable = ranking.filter((s) => s.inBudget && inRing(s));
          return json({
            budget: rp.budget,
            timing: rp.timing,
            affordability: rp.affordability,
            summary: {
              total: ranking.length,
              inBudget: ranking.filter((s) => s.inBudget).length,
              withinRing: ring == null ? null : ranking.filter(inRing).length,
              viable: viable.length,
              viableSuburbs: viable.map((s) => s.name),
            },
            ranking,
            dashboardUrl: dashboardUrl(profile),
          });
        } catch (e) {
          return json({ error: (e as Error).message });
        }
      },
    );

    server.tool(
      "match_listings",
      "Match current listings to a buyer's hard constraints (min beds, min land, budget ceiling, max distance) and rank them by suburb fit. By default uses the latest committed feed; set live=true to pull fresh from RapidAPI (requires RAPIDAPI_KEY).",
      {
        profile: ProfileSchema,
        live: z.boolean().optional().describe("Pull fresh listings from RapidAPI instead of the committed feed."),
      },
      async ({ profile, live }) => {
        try {
          const rp = resolveProfile(profile as BuyerProfile);
          const listings = live ? (await searchListingsLive({ cap: 6 })).listings : loadListings();
          return json({ budget: rp.budget, matches: matchListings(rp, listings), listingsViewUrl: toolUrl({ tab: "listings" }) });
        } catch (e) {
          return json({ error: (e as Error).message });
        }
      },
    );

    // ---- Live listings (external API) --------------------------------------
    server.tool(
      "search_listings",
      "Search live for-sale houses (3+ beds, <=$1.1M, with photos) in the in-budget WA target suburbs via the Realty in AU API. Falls back to the committed sample when no RAPIDAPI_KEY is configured.",
      {
        suburb: z.string().optional().describe("Restrict to one in-budget suburb; omit to sweep the targets."),
        cap: z.number().int().min(1).max(8).optional().describe("How many suburbs to sweep when no suburb is given. Default 4."),
      },
      async ({ suburb, cap }) => json(await searchListingsLive({ suburb, cap })),
    );

    // Guided prompts (the "/" menu): the scoped, form-driven front door.
    registerPrompts(server);
  },
  {
    serverInfo: { name: "como-home-model", version: "0.3.0" },
    capabilities: { tools: {}, prompts: {} },
    instructions:
      "The Como home model: a WESTERN AUSTRALIA (Perth) ONLY house-price and " +
      "suburb-fit engine. When the user first engages, asks what this does, or seems " +
      "unsure what to type, call the `capabilities` tool and present its menu BEFORE " +
      "doing anything else - do not make the user guess the commands. " +
      "Prefer the guided prompts: /find_a_home (budget, timing " +
      "and a suburb ranking), /estimate_a_listing (price + fit for one house), and " +
      "/about_this_tool (orientation). Never invent a financial figure the user did " +
      "not give; if one is missing, ask. If a suburb or state outside the dataset is " +
      "requested, say it is out of scope. estimate_price and forecast are buyer-agnostic. " +
      "Rendering: give a concise Markdown summary first (works everywhere), then, when " +
      "supported, a self-contained HTML artifact dashboard built only from the tools' " +
      "numbers. Do NOT use the separate 'visualize' MCP-app tool to draw charts (it is " +
      "desktop-bound and times out on mobile); a native HTML artifact renders client-side. " +
      "When a tool result includes dashboardUrl or listingsViewUrl, end your reply with it " +
      "as 'Open your dashboard: <url>' - that is a real server-rendered page, the most " +
      "reliable way for the user to see the result.",
  },
  {
    basePath: "/api",
    maxDuration: 300,
    verboseLogs: true,
  },
);

// Bearer gate in front of the MCP handler (open if MCP_BEARER_TOKEN is unset).
async function guarded(req: Request): Promise<Response> {
  const denied = checkBearer(req);
  if (denied) return denied;
  return handler(req);
}

export { guarded as GET, guarded as POST, guarded as DELETE };
