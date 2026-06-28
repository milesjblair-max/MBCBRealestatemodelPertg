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
  km: number;
  school: number;
  prox: number;
  mlo: number; // median low ($000s)
  mhi: number; // median high ($000s)
  band: boolean; // sits within / below the $800k-$1.1M band
  scores: SuburbScores;
  why?: string;
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
