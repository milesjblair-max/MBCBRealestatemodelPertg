// Zod schemas for the MCP tool inputs. These mirror the engine's BuyerProfile
// (server/lib/engine/types.ts) - the same types that gave us the parity-tested
// engine now define the tool contract a client sees. Keeping them here keeps the
// route file readable.

import { z } from "zod";

export const LIFE_STAGES = [
  "young_single",
  "young_couple",
  "young_family",
  "established_family",
  "downsizer",
] as const;

export const CONDITIONS = ["original", "dated", "good", "renovated", "new"] as const;

export const CriteriaSchema = z
  .object({
    growth: z.number().min(0).max(5).optional(),
    schools: z.number().min(0).max(5).optional(),
    family: z.number().min(0).max(5).optional(),
    land: z.number().min(0).max(5).optional(),
    proximity: z.number().min(0).max(5).optional(),
    amenity: z.number().min(0).max(5).optional(),
    project: z.number().min(0).max(5).optional(),
  })
  .describe("Importance 0-5 per dimension. Omit to use life-stage defaults.");

export const FinancesSchema = z
  .object({
    deposit: z.number().nonnegative().optional().describe("Cash available for a deposit (AUD)."),
    cash_buffer: z.number().nonnegative().optional().describe("Extra liquid cash beyond the deposit (AUD)."),
    credit_line: z.number().nonnegative().optional().describe("Line of credit / family facility available (AUD)."),
    credit_rate_pct: z.number().nonnegative().optional().describe("Interest rate on that facility (%); 0 if interest-free."),
    currently_renting: z.boolean().optional(),
    monthly_commitments: z.number().nonnegative().optional().describe("Existing monthly loan repayments (AUD)."),
  })
  .describe("The buyer's cash position. Drives the budget band and the buy-timing posture.");

export const ProfileSchema = z
  .object({
    region: z.literal("WA").describe("Only WA (Perth) is supported for now."),
    anchor: z.string().describe("The suburb the buyer most wants to live near (must be in the dataset)."),
    age: z.number().int().positive().optional(),
    income: z.number().nonnegative().optional().describe("Gross annual household income (AUD)."),
    finances: FinancesSchema.optional(),
    life_stage: z.enum(LIFE_STAGES).optional(),
    criteria: CriteriaSchema.optional(),
    filters: z
      .object({
        min_beds: z.number().int().nonnegative().optional(),
        min_land: z.number().nonnegative().optional(),
        max_distance_km: z.number().positive().optional(),
      })
      .optional(),
    horizon_years: z.number().positive().optional(),
  })
  .describe("A WA home-buyer profile. The engine resolves it into a budget band, a buy-timing posture and normalised scoring weights.");

export type ProfileInput = z.infer<typeof ProfileSchema>;
