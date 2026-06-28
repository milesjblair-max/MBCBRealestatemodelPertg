// The onboarding contract: the questions the MCP asks a new user, and a mapper
// from their flat answers to a BuyerProfile. Phase 2 exposes this as an MCP
// prompt / a set_profile tool; defining it here keeps the question set versioned
// with the engine.

import type { BuyerProfile, CriteriaInput, LifeStage } from "./types.js";

export interface OnboardingQuestion {
  id: string;
  prompt: string;
  type: "enum" | "suburb" | "number" | "boolean" | "criteria";
  options?: string[];
  optional?: boolean;
}

export const LIFE_STAGES: LifeStage[] = [
  "young_single",
  "young_couple",
  "young_family",
  "established_family",
  "downsizer",
];

export const ONBOARDING_QUESTIONS: OnboardingQuestion[] = [
  { id: "region", prompt: "Which state are you buying in? (WA / Perth only for now)", type: "enum", options: ["WA"] },
  { id: "anchor", prompt: "Which suburb do you most want to live near?", type: "suburb" },
  { id: "age", prompt: "Your age?", type: "number" },
  { id: "income", prompt: "Gross annual household income (AUD)?", type: "number" },
  { id: "deposit", prompt: "Cash available for a deposit (AUD)?", type: "number" },
  { id: "cash_buffer", prompt: "Extra liquid cash beyond the deposit (AUD)?", type: "number", optional: true },
  { id: "credit_line", prompt: "Any line of credit or family facility available (AUD)?", type: "number", optional: true },
  { id: "credit_rate_pct", prompt: "Interest rate on that facility (%)? (0 if interest-free)", type: "number", optional: true },
  { id: "currently_renting", prompt: "Are you renting right now?", type: "boolean" },
  { id: "monthly_commitments", prompt: "Existing monthly loan repayments (AUD)?", type: "number", optional: true },
  { id: "life_stage", prompt: "Which best describes you?", type: "enum", options: LIFE_STAGES },
  {
    id: "criteria",
    prompt: "Rate 0-5 how much each matters: growth, schools, family, land, proximity, amenity, project (KDR/reno appetite). Skip to use the life-stage defaults.",
    type: "criteria",
    optional: true,
  },
  { id: "min_beds", prompt: "Minimum bedrooms?", type: "number", optional: true },
  { id: "min_land", prompt: "Minimum land size (sqm)?", type: "number", optional: true },
  { id: "horizon_years", prompt: "How many years until you want to be in the home?", type: "number", optional: true },
];

export type OnboardingAnswers = Record<string, unknown>;

/** Map flat onboarding answers into a structured BuyerProfile. */
export function profileFromAnswers(a: OnboardingAnswers): BuyerProfile {
  const num = (k: string) => (a[k] == null ? undefined : Number(a[k]));
  const profile: BuyerProfile = {
    region: "WA",
    anchor: String(a.anchor ?? ""),
    age: num("age"),
    income: num("income"),
    finances: {
      deposit: num("deposit"),
      cash_buffer: num("cash_buffer"),
      credit_line: num("credit_line"),
      credit_rate_pct: num("credit_rate_pct"),
      currently_renting: a.currently_renting == null ? undefined : Boolean(a.currently_renting),
      monthly_commitments: num("monthly_commitments"),
    },
    life_stage: a.life_stage as LifeStage | undefined,
    criteria: (a.criteria as CriteriaInput) ?? undefined,
    filters: {
      min_beds: num("min_beds"),
      min_land: num("min_land"),
    },
    horizon_years: num("horizon_years"),
  };
  return profile;
}
