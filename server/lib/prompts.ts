// MCP PROMPTS: guided, parameterised templates the client (Claude Desktop) shows
// in its "/" menu and renders as a fill-in form, one labelled field per argument.
//
// This is what makes the server usable instead of an open chat. Tools are the
// verbs; prompts are the guided front door that collects the right inputs (with
// descriptions), states the Western-Australia-only scope, and tells the model to
// run the tools WITHOUT inventing any figure the user did not provide.
//
// Note: MCP passes every prompt argument as a string, so the schemas are strings
// and the template hands them to the model to map into the typed tool inputs.

import { z } from "zod";
import { SUBURBS } from "@/lib/engine/data";

const ANCHORS = SUBURBS.map((s) => s.name).join(", ");

const SCOPE_LINE =
  "SCOPE: This is the Como home model and it covers WESTERN AUSTRALIA (Perth) ONLY. " +
  "If the user names a suburb or state outside this list, say so plainly and stop. " +
  `Valid suburbs: ${ANCHORS}.`;

const NO_GUESS =
  "HARD RULE: do not invent, assume, or placeholder ANY financial figure (income, " +
  "deposit, credit facility, rate). If a value needed to run is missing, ask the " +
  "user one short question and wait. A guessed budget silently inverts the whole " +
  "ranking, so it is better to ask than to estimate.";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function registerPrompts(server: any): void {
  // ---- 1. The main guided flow ------------------------------------------
  server.prompt(
    "find_a_home",
    "Guided WA (Perth) home search. Fill in your details; the model resolves your budget and buy-timing and ranks suburbs using the engine, without guessing any numbers.",
    {
      anchor: z
        .string()
        .describe(`The WA suburb you most want to live NEAR. Must be one of: ${ANCHORS}.`),
      income: z.string().describe("Gross annual HOUSEHOLD income in AUD, e.g. 180000."),
      deposit: z.string().describe("Cash you have available for a deposit in AUD, e.g. 250000."),
      credit_line: z
        .string()
        .optional()
        .describe(
          "Any family or credit facility available to you in AUD. Enter 0 if none. This is the single biggest lever on your budget, so give the REAL number.",
        ),
      credit_rate_pct: z
        .string()
        .optional()
        .describe("Interest rate on that facility as a percent. Enter 0 if it is interest-free."),
      equity_release: z
        .string()
        .optional()
        .describe(
          "Equity you would release from a property you ALREADY own, in AUD. This is borrowed money: it helps cover the price but carries servicing (unlike cash), so it does not stretch your budget as far as the same amount in cash.",
        ),
      equity_rate_pct: z
        .string()
        .optional()
        .describe("Interest rate on that released equity, as a percent. Leave blank for a standard mortgage rate."),
      currently_renting: z
        .string()
        .optional()
        .describe("Are you renting right now? Enter yes or no. This decides the buy-timing call."),
      priority: z
        .string()
        .optional()
        .describe("What matters most: schools, proximity, land, or balanced. Default balanced."),
      max_distance_km: z
        .string()
        .optional()
        .describe(
          "HARD limit on distance from your anchor, in km (e.g. 10 to stay in the inner-south pocket near Como). Leave blank for no limit. Use this if staying near your anchor matters.",
        ),
      horizon_years: z
        .string()
        .optional()
        .describe("Years until you want to be living in the home, e.g. 3."),
    },
    (a: Record<string, string | undefined>) => ({
      messages: [
        {
          role: "user",
          content: {
            type: "text",
            text: [
              SCOPE_LINE,
              NO_GUESS,
              "",
              `TASK: The user wants a home near ${a.anchor ?? "(ask which suburb)"}. Build a BuyerProfile and call the tools resolve_profile and rank_suburbs_for_profile (and match_listings if they want listings). Map the inputs:`,
              `- region: "WA"`,
              `- anchor: ${a.anchor ?? "ASK"}`,
              `- income: ${a.income ?? "ASK"}`,
              `- finances.deposit: ${a.deposit ?? "ASK"}`,
              `- finances.credit_line: ${a.credit_line ?? "ASK the user (do NOT guess)"}`,
              `- finances.credit_rate_pct: ${a.credit_rate_pct ?? "ASK (0 if interest-free)"}`,
              `- finances.equity_release: ${a.equity_release && a.equity_release.trim() !== "" ? a.equity_release : "none (only if they own a property and would borrow against it)"}`,
              `- finances.equity_rate_pct: ${a.equity_rate_pct && a.equity_rate_pct.trim() !== "" ? a.equity_rate_pct : "default mortgage rate"}`,
              `- finances.currently_renting: ${a.currently_renting ?? "ASK"}`,
              `- life_stage: infer (e.g. young_family) only from what the user said`,
              `- criteria from priority="${a.priority ?? "balanced"}": schools -> schools 5, proximity 2; proximity -> proximity 5, schools 3; land -> land 5; balanced -> omit and use the life-stage defaults`,
              `- filters.max_distance_km: ${a.max_distance_km && a.max_distance_km.trim() !== "" ? a.max_distance_km : "none (do not cap distance)"}`,
              `- horizon_years: ${a.horizon_years ?? "ASK if buy-timing is wanted"}`,
              "",
              "THEN present, concisely (no rambling):",
              "1. One line confirming this is the WA Como model and the resolved budget band. If the band used borrowed funds (a credit facility or released equity), note the budget.cash vs budget.borrowedFunds split and that borrowed money was serviced, not counted as free cash.",
              "2. The buy-timing posture (act-now / balanced / patient-opportunistic) with its one-line reason.",
              "3. A ranked suburb table: suburb, km from anchor, score, in-budget (yes/no).",
              "4. At most one honest caveat (e.g. WA school catchments are drawn street by street, so 'in Shelley' does not guarantee the Rossmoyne intake; or the anchor itself may be over budget).",
            ].join("\n"),
          },
        },
      ],
    }),
  );

  // ---- 2. Price + fit on a specific listing -----------------------------
  server.prompt(
    "estimate_a_listing",
    "Estimate the price of a specific WA house and assess how well it fits you.",
    {
      suburb: z.string().describe(`The suburb of the listing. One of: ${ANCHORS}.`),
      land: z.string().optional().describe("Land size in sqm, e.g. 720."),
      beds: z.string().optional().describe("Bedrooms, e.g. 4."),
      baths: z.string().optional().describe("Bathrooms, e.g. 2."),
      condition: z
        .string()
        .optional()
        .describe("One of: original, dated, good, renovated, new."),
    },
    (a: Record<string, string | undefined>) => ({
      messages: [
        {
          role: "user",
          content: {
            type: "text",
            text: [
              SCOPE_LINE,
              `TASK: Call estimate_price (and assess_property) for a house in ${a.suburb ?? "ASK"} with land=${a.land ?? "unknown"}, beds=${a.beds ?? "unknown"}, baths=${a.baths ?? "unknown"}, condition=${a.condition ?? "unknown"}.`,
              "Present the likely price, the low-high range, the typical advertised guide floor, the confidence level, and the buyer-fit pros and cons. Keep it tight. Do not invent details the user did not give.",
            ].join("\n"),
          },
        },
      ],
    }),
  );

  // ---- 3. Orientation: what is this and how do I use it -----------------
  server.prompt(
    "about_this_tool",
    "What this MCP does, the suburbs and state it covers, and how to drive it.",
    {},
    () => ({
      messages: [
        {
          role: "user",
          content: {
            type: "text",
            text: [
              SCOPE_LINE,
              "TASK: Briefly explain to the user, in plain English: (a) this is the Como home model for Western Australia (Perth) only; (b) it can estimate a house price, score and rank suburbs for their situation, forecast the market, and match listings; (c) the best way to start is the /find_a_home prompt, or estimate_a_listing for a specific property. Call list_suburbs to show the suburbs it covers with their median ranges. Keep it short and concrete.",
            ].join("\n"),
          },
        },
      ],
    }),
  );
}
