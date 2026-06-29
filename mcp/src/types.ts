// Shared types for the Como engine. These mirror the shapes in data/*.json.

export type River = "S" | "N";
export type Condition = "original" | "dated" | "good" | "renovated" | "new";

export interface SuburbScores {
  growth: number;
  family: number;
  land: number;
  kdr: number;
  prox: number;
  post: number;
}

export interface Suburb {
  name: string;
  pc: string;
  reg: River;
  km: number; // legacy: straight-line km to Como (the original anchor)
  lat: number;
  lng: number;
  school: number;
  prox: number;
  mlo: number; // median low ($000s)
  mhi: number; // median high ($000s)
  band: boolean; // sits within / below the original buyer's $800k-$1.1M band
  scores: SuburbScores;
  why?: string;
}

// ---- Dynamic buyer profile (what a user stipulates to the MCP) -------------

export type LifeStage =
  | "young_single"
  | "young_couple"
  | "young_family"
  | "established_family"
  | "downsizer";

/** Importance 0-5 per dimension. */
export interface CriteriaInput {
  growth?: number;
  schools?: number;
  family?: number;
  land?: number;
  proximity?: number;
  amenity?: number;
  project?: number; // appetite for KDR / renovation
}

export interface Finances {
  deposit?: number;
  cash_buffer?: number;
  credit_line?: number;
  credit_rate_pct?: number;
  currently_renting?: boolean;
  monthly_commitments?: number;
  // Equity in a property you already own. This is BORROWED money: it helps cover
  // the price but carries a servicing cost (unlike cash). Give the amount to
  // release directly, or the property's value and mortgage to compute it.
  equity_release?: number;
  equity_rate_pct?: number;
  property_value?: number;
  property_mortgage?: number;
}

export interface BuyerProfile {
  region: "WA";
  anchor: string; // a suburb in the dataset
  age?: number;
  income?: number;
  finances?: Finances;
  life_stage?: LifeStage;
  criteria?: CriteriaInput;
  filters?: { min_beds?: number; min_land?: number; max_distance_km?: number };
  horizon_years?: number;
}

/** Normalised weights over the suburb scoring dimensions (sum to 1). */
export interface ScoringWeights {
  growth: number;
  family: number;
  land: number;
  kdr: number;
  prox: number;
  post: number;
  school: number;
}

export interface BudgetBand {
  floor: number;
  ceiling: number;
  borrowingCapacity: number;
  cash: number; // servicing-free funds (deposit + buffer)
  borrowedFunds: number; // credit line + released equity (carry servicing)
  monthlyServicing: number; // monthly carrying cost of the borrowed funds
}

export interface BuyTiming {
  posture: "act-now" | "balanced" | "patient-opportunistic";
  urgency: number; // 0-100
  rationale: string[];
}

/** Can this buyer afford a house at their own anchor? The single most important
 *  read for an anchored buyer, computed from the data instead of guessed. */
export interface AnchorAffordability {
  anchorEntryPrice: number; // $ - typical entry (median-low) house price at the anchor
  reachable: boolean; // ceiling >= anchorEntryPrice
  gapToAnchor: number; // $ - anchorEntryPrice - ceiling; > 0 means priced out by this much
}

export interface ResolvedProfile {
  anchor: Suburb;
  weights: ScoringWeights;
  budget: BudgetBand;
  timing: BuyTiming;
  affordability: AnchorAffordability;
  filters: { min_beds: number; min_land: number; max_distance_km: number | null };
  lifeStage: LifeStage;
}

export type CriteriaWeights = Record<keyof SuburbScores, number>;

export interface Estimate {
  suburb: string;
  pc: string;
  medianRange: [number, number];
  likely: number; // $000s
  low: number;
  high: number;
  guideFloor: number; // typical advertised "offers above" floor
  spreadPct: number;
  confidence: "High" | "Medium" | "Low";
  inBand: boolean;
  school: number;
  adjustments: string[];
}
