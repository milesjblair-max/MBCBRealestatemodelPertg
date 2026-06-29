// A REAL, server-rendered dashboard. The page is built here, on the server, from
// the same parity-tested engine the tools use - so it looks identical every time,
// every number traces to the engine, and the chart is inline SVG (no external
// script for an artifact sandbox to block). This is the thing we can actually
// test, instead of asking the client model to hand-draw HTML.

import { resolveProfile } from "./engine/profile.js";
import { rankSuburbsForProfile } from "./engine/recommend.js";
import { buildTimeline, metrics, BASELINE_WEIGHTS } from "./engine/scenario.js";
import type { BuyerProfile } from "./engine/types.js";

function money(n: number): string {
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  return `$${Math.round(n / 1000)}k`;
}
function esc(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
}

/** Inline SVG fan chart: bear/base/bull/expected paths + the buyer's ceiling. */
function fanChartSvg(ceiling: number): string {
  const tl = buildTimeline(BASELINE_WEIGHTS);
  const W = 720, H = 300, padL = 48, padR = 18, padT = 16, padB = 30;
  const xs = (i: number) => padL + (i * (W - padL - padR)) / (tl.length - 1);
  const all = tl.flatMap((r) => [r.bear, r.base, r.bull]).concat([ceiling]);
  const lo = Math.min(...all) * 0.96, hi = Math.max(...all) * 1.03;
  const ys = (v: number) => padT + (1 - (v - lo) / (hi - lo)) * (H - padT - padB);
  const pts = (key: "bear" | "base" | "bull" | "expected") =>
    tl.map((r, i) => `${xs(i).toFixed(1)},${ys(r[key]).toFixed(1)}`).join(" ");
  const line = (key: "bear" | "base" | "bull" | "expected", color: string, dash = "") =>
    `<polyline fill="none" stroke="${color}" stroke-width="2.5" ${dash ? `stroke-dasharray="${dash}"` : ""} points="${pts(key)}"/>`;
  const yTicks = [lo, (lo + hi) / 2, hi]
    .map((v) => `<text x="${padL - 8}" y="${(ys(v) + 4).toFixed(1)}" text-anchor="end" class="ax">$${(v / 1e6).toFixed(1)}M</text>`)
    .join("");
  const xLabels = tl
    .map((r, i) => `<text x="${xs(i).toFixed(1)}" y="${H - 8}" text-anchor="middle" class="ax">${esc(r.label.replace(" (mid-26)", ""))}</text>`)
    .join("");
  const cy = ys(ceiling).toFixed(1);
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Bear, base, bull and expected paths for a one million dollar Perth house to mid-2029, with the buyer's ceiling line.">
    ${yTicks}${xLabels}
    ${line("bull", "#0F7A5F")}${line("base", "#2A78D6")}${line("bear", "#BC4B12")}${line("expected", "#8A867C", "5 4")}
    <line x1="${padL}" y1="${cy}" x2="${W - padR}" y2="${cy}" stroke="#1A1815" stroke-width="2" stroke-dasharray="6 5"/>
    <text x="${W - padR}" y="${(+cy - 6).toFixed(1)}" text-anchor="end" class="ceil">your ceiling ${money(ceiling)}</text>
  </svg>`;
}

function card(k: string, v: string, x = "", flag = false): string {
  return `<div class="m${flag ? " flag" : ""}"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div>${x ? `<div class="x">${esc(x)}</div>` : ""}</div>`;
}

export interface DashboardResult {
  html: string;
  status: number;
}

export function buildDashboardHtml(profile: BuyerProfile): DashboardResult {
  let rp;
  try {
    rp = resolveProfile(profile);
  } catch (e) {
    const msg = (e as Error).message;
    return {
      status: 400,
      html: `<!doctype html><meta charset="utf-8"><title>Out of scope</title><body style="font-family:system-ui;background:#0f1413;color:#e7efee;padding:40px"><h1>WA Home Model - WA only</h1><p>${esc(msg)}</p></body>`,
    };
  }

  const ranking = rankSuburbsForProfile(rp);
  const ring = rp.filters.max_distance_km;
  const inRing = (s: { km: number }) => ring == null || s.km <= ring;
  const viable = ranking.filter((s) => s.inBudget && inRing(s));
  const m = metrics(buildTimeline(BASELINE_WEIGHTS));
  const a = rp.affordability;
  const anchor = rp.anchor.name;
  const maxScore = Math.max(1, ...ranking.map((s) => s.score));

  const rows = ranking
    .map((s) => {
      const pct = Math.max(0, Math.min(100, (s.score / maxScore) * 100));
      const over = !s.inBudget;
      return `<tr class="${over ? "out" : ""}">
        <td class="sub">${esc(s.name)}${s.name === anchor ? '<span class="tag">anchor</span>' : ""}</td>
        <td class="km">${s.km.toFixed(1)}</td>
        <td class="sc"><span class="bar" style="width:${pct.toFixed(0)}%;background:${over ? "#BC4B12" : "#0F7A5F"}"></span><span class="scv">${s.score.toFixed(1)}</span></td>
        <td>${s.inBudget ? '<span class="b ok">in budget</span>' : '<span class="b over">over</span>'}</td>
        <td>${inRing(s) ? '<span class="b yes">within</span>' : '<span class="b no">beyond</span>'}</td>
      </tr>`;
    })
    .join("");

  const scen = buildTimeline(BASELINE_WEIGHTS);
  const at = (label: string, key: "bear" | "base" | "bull") => money(scen.find((r) => r.label === label)![key]);

  const chips = [
    ["anchor", anchor],
    ["income", profile.income ? money(profile.income) : "n/a"],
    ["deposit", profile.finances?.deposit ? money(profile.finances.deposit) : "n/a"],
    ["life stage", rp.lifeStage.replace("_", " ")],
    ring != null ? ["radius", `<=${ring}km`] : null,
  ].filter(Boolean) as [string, string][];

  const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>WA Home Model - ${esc(anchor)} dashboard</title>
<style>
  :root{--paper:#F7F6F2;--card:#fff;--ink:#1A1815;--ink2:#57544D;--ink3:#8A867C;--line:#E4E2DA;--teal:#0F7A5F;--clay:#BC4B12;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--paper);color:var(--ink);font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;line-height:1.55}
  .wrap{max-width:920px;margin:0 auto;padding:30px 20px 60px}
  .eyebrow{font:600 11.5px/1 ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink3);margin:0 0 10px}
  h1{font-size:27px;margin:0;max-width:20ch;letter-spacing:-.01em}
  .lede{color:var(--ink2);margin:12px 0 0;max-width:62ch}
  .chips{display:flex;flex-wrap:wrap;gap:7px;margin:18px 0 0}
  .chip{font:500 11.5px/1 ui-monospace,monospace;color:var(--ink2);background:var(--card);border:1px solid var(--line);border-radius:999px;padding:5px 11px}
  .chip b{color:var(--ink);font-weight:600}
  h2{font-size:16px;margin:34px 0 14px}
  .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:11px}
  .m{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:15px 16px}
  .m.flag{border-color:var(--clay)}
  .m .k{font-size:12px;color:var(--ink3);margin:0 0 7px}
  .m .v{font:500 22px/1 ui-monospace,monospace}
  .m.flag .v{color:var(--clay)}
  .m .x{font-size:11.5px;color:var(--ink2);margin:8px 0 0}
  .chart{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
  .legend{display:flex;flex-wrap:wrap;gap:14px;margin:0 0 10px;font-size:12px;color:var(--ink2)}
  .legend i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:6px;vertical-align:middle}
  .ax{font:11px ui-monospace,monospace;fill:var(--ink3)}
  .ceil{font:11px ui-monospace,monospace;fill:var(--ink)}
  table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:13.5px}
  th{text-align:left;font:500 11px/1 ui-monospace,monospace;letter-spacing:.04em;text-transform:uppercase;color:var(--ink3);padding:12px 14px;border-bottom:1px solid var(--line)}
  td{padding:10px 14px;border-bottom:1px solid var(--line);vertical-align:middle}
  tr:last-child td{border-bottom:0}
  tr.out td{opacity:.55}
  .sub{font-weight:600}
  .tag{font:9.5px ui-monospace,monospace;color:#3F3C91;background:#ECEBF6;padding:1px 6px;border-radius:4px;margin-left:6px}
  .km{font-family:ui-monospace,monospace;color:var(--ink2)}
  .sc{position:relative;min-width:120px}
  .bar{display:inline-block;height:9px;border-radius:3px;vertical-align:middle;margin-right:8px;max-width:80px}
  .scv{font:500 12px ui-monospace,monospace}
  .b{font:500 11px ui-monospace,monospace;padding:2px 8px;border-radius:999px;white-space:nowrap}
  .b.ok{color:#0A5642;background:#E4F1EB}.b.over{color:#8A3608;background:#F6E7DC}
  .b.yes{color:var(--ink2);background:#EDEBE3}.b.no{color:#8A3608;background:#F6E7DC}
  footer{margin:36px 0 0;padding-top:16px;border-top:1px solid var(--line);font-size:12px;color:var(--ink3)}
  @media(max-width:560px){h1{font-size:22px}.wrap{padding:22px 14px 44px}}
</style></head>
<body><div class="wrap">
  <p class="eyebrow">WA Home Model &middot; Western Australia &middot; resolved profile</p>
  <h1>${a.reachable ? `${esc(anchor)} is within reach.` : `Priced out of ${esc(anchor)} by ${money(a.gapToAnchor)}.`}</h1>
  <p class="lede">${a.reachable
    ? `Your ceiling of ${money(rp.budget.ceiling)} clears a typical ${esc(anchor)} house (entry ~${money(a.anchorEntryPrice)}).`
    : `A typical ${esc(anchor)} house starts near ${money(a.anchorEntryPrice)}; your ceiling is ${money(rp.budget.ceiling)}. This is engine output, not rounded to flatter.`}</p>
  <div class="chips">${chips.map(([k, v]) => `<span class="chip">${esc(k)} <b>${v}</b></span>`).join("")}</div>

  <h2>Budget &amp; buying window</h2>
  <div class="metrics">
    ${card("Budget band", `${money(rp.budget.floor)} - ${money(rp.budget.ceiling)}`, "floor to ceiling, after costs/buffer", true)}
    ${card("Borrowing capacity", money(rp.budget.borrowingCapacity), "on income, at the buffered rate")}
    ${card("Cash brought", money(rp.budget.cash), rp.budget.borrowedFunds ? `+ ${money(rp.budget.borrowedFunds)} borrowed (serviced)` : "servicing-free")}
    ${card("Buy posture", rp.timing.posture.replace(/-/g, " "), `urgency ${rp.timing.urgency}/100`, true)}
    ${card(`${anchor} entry`, money(a.anchorEntryPrice), a.reachable ? `${money(-a.gapToAnchor)} under ceiling` : `${money(a.gapToAnchor)} over ceiling`)}
    ${card("Viable suburbs", `${viable.length} / ${ranking.length}`, ring != null ? `in budget and within ${ring}km` : "in budget")}
  </div>

  <h2>Three-scenario forecast &rarr; mid-2029</h2>
  <p class="lede" style="margin-bottom:12px">Tracks a ~$1.0M Perth house (a market proxy). The dashed ink line is your ceiling. Blend 30 / 50 / 20. Expected mid-29 <b>${money(m.expected_mid29)}</b>, ~${m.expected_3yr_cagr_pct}%/yr.</p>
  <div class="chart">
    <div class="legend"><span><i style="background:#BC4B12"></i>Bear ${at("End-27", "bear")}</span><span><i style="background:#2A78D6"></i>Base ${at("Mid-29", "base")}</span><span><i style="background:#0F7A5F"></i>Bull ${at("Mid-29", "bull")}</span><span><i style="background:#8A867C"></i>Expected</span><span><i style="background:#1A1815"></i>Your ceiling</span></div>
    ${fanChartSvg(rp.budget.ceiling)}
  </div>

  <h2>Suburb heat table</h2>
  <p class="lede" style="margin-bottom:10px">Ranks the model's curated set of ${ranking.length} WA suburbs - a middle-ring cluster, not all of Perth. A genuinely better-fit suburb outside this set (Morley, Yokine, Inglewood, further out for land) will not appear here.</p>
  <table><thead><tr><th>Suburb</th><th>km</th><th>Fit</th><th>Budget</th><th>${ring != null ? `${ring}km ring` : "ring"}</th></tr></thead><tbody>${rows}</tbody></table>

  <footer>Built from <b>wa-home-model</b>: resolve_profile + rank_suburbs_for_profile + forecast (30/50/20 baseline). Every figure is engine output for this profile. General information only, not financial advice.</footer>
</div></body></html>`;

  return { html, status: 200 };
}
