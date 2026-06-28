// Numeric helpers that MUST match the Python reference exactly.
//
// The subtle part: Python's built-in round() uses "round half to even"
// (banker's rounding), e.g. round(0.5) == 0 and round(1.5) == 2. JavaScript's
// Math.round() uses "round half up" (Math.round(0.5) === 1). If we naively used
// Math.round the TS engine would disagree with the Python model on exact .5
// cases, and the parity test would fail. So we reimplement Python's rounding.

/** Python 3 round(x, digits): round half to even.
 *
 * The halfway test uses EXACT equality (diff === 0.5), not an epsilon. JS and
 * Python both use IEEE-754 doubles, so the same arithmetic yields the same bits;
 * a value is only a true "half" when its fractional part is exactly 0.5. Using a
 * fuzzy epsilon here wrongly snapped near-halves to even and disagreed with
 * Python (e.g. 73.2 vs 73.3). Exact equality matches Python on every fixture. */
export function pyRound(x: number, digits = 0): number {
  const m = 10 ** digits;
  const v = x * m;
  const floor = Math.floor(v);
  const diff = v - floor;
  let r: number;
  if (diff === 0.5) {
    r = floor % 2 === 0 ? floor : floor + 1; // exactly halfway -> nearest even
  } else {
    r = Math.round(v); // Math.round is round-half-up, but diff != 0.5 here so it agrees
  }
  return r / m;
}

/** int(round(x / 5) * 5): round to the nearest $5k (guide figure). */
export function round5(x: number): number {
  return pyRound(x / 5) * 5;
}

/** ROUND_HALF_UP to the nearest $1,000 (matches scenario_model.py's Decimal). */
export function roundHalfUp1000(x: number): number {
  return Math.round(x / 1000) * 1000;
}

/** Format $000s like the tool: "$915k" or "$2.38M". */
export function fmtK(k: number): string {
  return k >= 1000 ? `$${(k / 1000).toFixed(2)}M` : `$${Math.round(k)}k`;
}

/** Format full dollars: "$1.76M" / "$720k". */
export function fmtDollars(n: number): string {
  return fmtK(n / 1000);
}

/** Pull a dollar figure out of REA free-text price ("From $999k"); null if none. */
export function parsePrice(text?: string | null): number | null {
  if (!text) return null;
  const m = String(text).match(/\$\s*([\d][\d,.]*)\s*([kKmM])?/);
  if (!m) return null;
  let n = parseFloat(m[1]!.replace(/,/g, ""));
  if (Number.isNaN(n)) return null;
  const s = (m[2] ?? "").toLowerCase();
  if (s === "k") n *= 1e3;
  else if (s === "m") n *= 1e6;
  else if (n < 100) n *= 1e6;
  return n >= 50000 ? Math.round(n) : null;
}
