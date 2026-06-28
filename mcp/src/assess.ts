// Property assessment - pros / cons / fit against the ten criteria.
// Ported from the avmAssess() function in web/index.html (this logic only ever
// lived in the JS tool, so it is unit-tested here rather than Python-parity'd).

import { estimate } from "./avm.js";
import { findSuburb } from "./data.js";
import { scoreSuburbObj } from "./scoring.js";
import { fmtK } from "./util.js";
import type { Condition } from "./types.js";

export interface AssessPoint {
  label: string;
  detail: string;
}
export interface Assessment {
  estimate: ReturnType<typeof estimate>;
  fit: number; // 0-100, at the given proximity-vs-schools prior
  pros: AssessPoint[];
  cons: AssessPoint[];
}

export function assessProperty(
  suburb: string,
  land?: number | null,
  beds?: number | null,
  baths?: number | null,
  condition?: string | null,
  prior = 50,
): Assessment {
  const s = findSuburb(suburb);
  if (!s) throw new Error(`Unknown suburb '${suburb}'`);
  const r = estimate(suburb, land, beds, baths, condition);
  const cond = condition?.trim().toLowerCase() as Condition | undefined;

  const pros: AssessPoint[] = [];
  const cons: AssessPoint[] = [];
  const pro = (label: string, detail: string) => pros.push({ label, detail });
  const con = (label: string, detail: string) => cons.push({ label, detail });

  if (land != null) {
    if (land >= 500) pro("Meets the 500sqm+ land filter", `${land}sqm block`);
    else con("Under 500sqm", `${land}sqm fails the hard land filter`);
  }
  if (beds != null) {
    if (beds >= 4) pro("4+ bedrooms", `${beds} beds, no KDR needed`);
    else if (s.scores.kdr >= 7 && (land == null || land >= 500))
      con(`Only ${beds} beds`, "but strong KDR economics here can add a 4th");
    else con(`Only ${beds} beds`, "below the 4+ target");
  }
  if (r.likely <= 1100) pro("Estimated inside the $800k-$1.1M band", `likely ${fmtK(r.likely)}`);
  else con("Estimate above the band", `~${fmtK(r.likely)}, over the soft $1.1M ceiling`);

  if (s.school >= 8) pro("Top-tier school catchment", "Rossmoyne / Willetton-grade demand");
  if (s.km <= 7) pro("Close to family in Como", `~${s.km}km`);
  else if (s.km >= 13) con("A fair way from Como", `~${s.km}km, the north-of-river trade-off`);
  if (s.scores.family >= 8) pro("Strong family area", "demographics, parks, schools");
  if (s.scores.growth >= 8) pro("High growth-after-dip score", "scarce land / undersupply");

  if (cond === "original" || cond === "dated") {
    if (s.scores.kdr >= 8 && (land == null || land >= 500))
      pro("Ideal knock-down-rebuild play", "original stock on big land, strong KDR margin");
    else con("Dated dwelling", "budget for a reno or rebuild");
  } else if (cond === "renovated" || cond === "new") {
    pro("Move-in ready", "little to spend up front");
  }

  if (!s.band) con("Suburb median above budget", "houses here mostly clear the band");
  if (s.scores.post >= 8) pro("Good postcode", "amenity and median level hold up");

  // Fit: the suburb's score at this prior, knocked down for hard-criteria misses.
  let fit = scoreSuburbObj(s, prior).score;
  if (land != null && land < 500) fit *= 0.6;
  if (r.likely > 1100) fit *= 0.9;
  fit = Math.max(0, Math.min(100, Math.round(fit)));

  return { estimate: r, fit, pros, cons };
}
