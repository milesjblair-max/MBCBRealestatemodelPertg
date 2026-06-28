// Single source of truth: the engine reads the SAME data/*.json the Python
// model and the HTML tool read, so all three stay in lockstep. We read from
// disk (relative to the repo) rather than copy the data into the package.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import type { Suburb, CriteriaWeights } from "./types.js";

const here = dirname(fileURLToPath(import.meta.url));
// mcp/src -> repo root -> data
const DATA_DIR = join(here, "..", "..", "data");

function loadJson<T>(name: string): T {
  return JSON.parse(readFileSync(join(DATA_DIR, name), "utf8")) as T;
}

export const SUBURBS: Suburb[] = loadJson<{ suburbs: Suburb[] }>("suburbs.json").suburbs;

export const CRITERIA_WEIGHTS: CriteriaWeights = loadJson<{
  weighted_dimensions: CriteriaWeights;
}>("criteria.json").weighted_dimensions;

export interface BaselineRow {
  label: string;
  t: number;
  bear: number;
  base: number;
  bull: number;
  expected: number;
  trough?: boolean;
}
export const BASELINE = loadJson<{
  timeline: BaselineRow[];
  key_numbers: Record<string, number>;
  weights: { bear: number; base: number; bull: number };
}>("baseline.json");

export function findSuburb(name: string): Suburb | undefined {
  const n = name.trim().toLowerCase();
  return SUBURBS.find((s) => s.name.toLowerCase() === n);
}
