// Suburb Buyer-Fit scoring - a faithful port of model/scoring.py (Layer 3).
// prior 0..100: 0 = all weight on Como-proximity, 100 = all on school catchment,
// 50 = balanced. Returns a 0-100 fit score, with over-budget suburbs penalised.

import { SUBURBS, CRITERIA_WEIGHTS, findSuburb } from "./data.js";
import { pyRound } from "./util.js";
import type { Suburb } from "./types.js";

export interface SuburbScore {
  score: number;
  over: boolean;
}

export function scoreSuburbObj(s: Suburb, prior: number): SuburbScore {
  const swing = 0.2;
  const t = (prior - 50) / 50; // -1..+1
  const w = { ...CRITERIA_WEIGHTS };
  w.prox = Math.max(0, CRITERIA_WEIGHTS.prox - swing * t * 0.5);
  w.post = Math.max(0, CRITERIA_WEIGHTS.post + swing * t * 0.5);

  const sc = s.scores;
  let composite =
    sc.growth * w.growth +
    sc.family * w.family +
    sc.land * w.land +
    sc.kdr * w.kdr +
    sc.prox * w.prox;

  // postcode dimension blends the static postcode score with school catchment
  const postBlend = sc.post * (1 - (prior / 100) * 0.5) + s.school * ((prior / 100) * 0.5);
  composite += postBlend * w.post;

  let score = composite * 10;
  let over = false;
  if (!s.band) {
    const mid = (s.mlo + s.mhi) / 2;
    if (mid > 1100) {
      score *= 0.55;
      over = true;
    } else {
      score *= 0.85;
    }
  }
  return { score: pyRound(score * 10) / 10, over };
}

export function scoreSuburb(name: string, prior = 50): SuburbScore {
  const s = findSuburb(name);
  if (!s) throw new Error(`Unknown suburb '${name}'`);
  return scoreSuburbObj(s, prior);
}

export interface RankedSuburb extends SuburbScore {
  name: string;
  pc: string;
  km: number;
  reg: string;
}

export function rank(prior = 50): RankedSuburb[] {
  return SUBURBS.map((s) => ({
    name: s.name,
    pc: s.pc,
    km: s.km,
    reg: s.reg,
    ...scoreSuburbObj(s, prior),
  })).sort((a, b) => b.score - a.score);
}
