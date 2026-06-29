// Live listings, server-side: a TypeScript port of scripts/fetch_listings.py.
// It pulls real for-sale houses (with photos) from the "Realty in AU" API
// (apidojo, via RapidAPI), the same source the daily GitHub Action uses.
//
// DATA SOURCE NOTE: Realty in AU surfaces realestate.com.au listing data through
// a third-party RapidAPI endpoint. The owner chose this for a private tool. It is
// not an official REA feed and is rate-limited.
//
// With no RAPIDAPI_KEY in the environment this returns the committed sample
// (the same fallback the static page uses), so the tool always answers.

import { SUBURBS, loadListings, type Listing } from "@/lib/engine/data";
import { parsePrice } from "@/lib/engine/util";

const MAX_PRICE = 1_100_000;
const MIN_BEDS = 3;
const MIN_LAND = 500;
const PER_SUBURB = 6;
const TOTAL_CAP = 40;
const IMG_SIZE = "640x480";

const HOST = process.env.RAPIDAPI_HOST ?? "realty-in-au.p.rapidapi.com";
const LIST_URL = `https://${HOST}/properties/list`;

const PT_DENY = ["unit", "apartment", "flat", "studio", "block of units", "retirement", "new apartments"];
const UO_TEXT = ["u/o", "under offer", "under contract", "deposit taken", "sold", "leased", "now settled", "on hold", "withdrawn", "off market", "not available"];

type Json = Record<string, unknown>;

function dig(obj: unknown, ...paths: string[]): unknown {
  for (const path of paths) {
    let cur: unknown = obj;
    let ok = true;
    for (const key of path.split(".")) {
      if (cur && typeof cur === "object" && key in (cur as Json)) cur = (cur as Json)[key];
      else { ok = false; break; }
    }
    if (ok && cur !== null && cur !== undefined && cur !== "") return cur;
  }
  return undefined;
}

function toInt(v: unknown): number | null {
  if (v == null) return null;
  const n = parseInt(String(v).trim(), 10);
  return Number.isNaN(n) ? null : n;
}

function flatten(payload: Json): Json[] {
  const out: Json[] = [];
  const tiers = (payload.tieredResults ?? payload.results) as unknown;
  if (Array.isArray(tiers)) {
    for (const t of tiers) {
      if (t && typeof t === "object" && Array.isArray((t as Json).results)) out.push(...((t as Json).results as Json[]));
      else if (t && typeof t === "object" && ("address" in (t as Json) || "bedrooms" in (t as Json))) out.push(t as Json);
    }
  }
  const emb = dig(payload, "_embedded.listings", "data.results");
  if (Array.isArray(emb)) out.push(...(emb as Json[]));
  return out;
}

function fixReastatic(url: string | null): string | null {
  if (!url) return null;
  const m = url.match(/^(https:\/\/[^/]*reastatic\.net)\/(.+)/i);
  if (!m) return url;
  const [, domain, rest] = m;
  if (/^\d+x\d+$/.test(rest!.split("/")[0]!)) return url;
  return `${domain}/${IMG_SIZE}/${rest}`;
}

function imgFrom(obj: unknown): string | null {
  if (obj && typeof obj === "object" && !Array.isArray(obj)) {
    const o = obj as Json;
    const server = o.server;
    const uri = o.uri ?? o.url ?? o.templatedUrl;
    if (typeof server === "string" && typeof uri === "string") {
      const joined = server.replace(/\/$/, "") + "/" + uri.replace(/^\//, "");
      if (joined.includes("{size}")) return joined.replace("{size}", IMG_SIZE);
      if (joined.includes("reastatic")) return joined;
    }
    for (const v of Object.values(o)) { const r = imgFrom(v); if (r) return r; }
  } else if (Array.isArray(obj)) {
    for (const v of obj) { const r = imgFrom(v); if (r) return r; }
  } else if (typeof obj === "string") {
    if (obj.includes("reastatic") && (obj.includes("{size}") || /\.(jpe?g|png|webp)(\?|$)/i.test(obj)))
      return obj.replace("{size}", IMG_SIZE);
  }
  return null;
}

function image(L: Json): string | null {
  const tmpl = dig(L, "mainPhoto.templatedUrl", "mainPhoto.url", "image.templatedUrl");
  const found =
    typeof tmpl === "string" && tmpl.includes("reastatic")
      ? tmpl.replace("{size}", IMG_SIZE)
      : imgFrom(L.mainPhoto) ?? imgFrom(L.images) ?? imgFrom(L.media) ?? imgFrom(L);
  return fixReastatic(found);
}

function normalise(items: Json[], suburb: string, pc: string, medianLowK?: number): Listing[] {
  const out: Listing[] = [];
  for (const L of items) {
    if (!L || typeof L !== "object") continue;
    const priceTxt = String(dig(L, "price.display", "priceText", "price.label") ?? "Contact agent");
    const priceN = toInt(dig(L, "price.value", "price.from", "priceDetails.price")) ?? parsePrice(priceTxt);
    const beds = toInt(dig(L, "bedrooms", "features.general.bedrooms", "general.bedrooms"));
    const baths = toInt(dig(L, "bathrooms", "features.general.bathrooms"));
    const cars = toInt(dig(L, "carspaces", "carSpaces", "features.general.carspaces", "features.general.parkingSpaces"));
    const land = toInt(dig(L, "landSize.value", "landSize.displayValue", "propertySizes.land.displayValue"));
    const ptype = String(dig(L, "propertyType") ?? "").toLowerCase();
    if (PT_DENY.some((d) => ptype.includes(d))) continue;
    if (UO_TEXT.some((u) => priceTxt.toLowerCase().includes(u))) continue;
    if (land != null && land < 450) continue;
    if (priceN && priceN > MAX_PRICE) continue;
    if (beds != null && beds < MIN_BEDS) continue;

    const slug = dig(L, "prettyUrl", "_links.canonical.href", "listingUrl", "url");
    let url: string;
    if (typeof slug === "string" && slug.startsWith("http")) url = slug;
    else if (typeof slug === "string") url = "https://www.realestate.com.au" + (slug.startsWith("/") ? "" : "/") + slug;
    else url = `https://www.realestate.com.au/buy/in-${suburb.toLowerCase().replace(/ /g, "+")}%2c+wa+${pc}/list-1`;

    const addr = String(dig(L, "address.streetAddress", "address.displayAddress", "title") ?? `${suburb} ${pc}`);
    const bargain = Boolean(priceN && medianLowK && priceN <= medianLowK * 1000 * 0.97);

    out.push({
      suburb, pc, price: priceN, priceText: priceTxt, beds, baths, cars, land,
      address: addr, image: image(L), url, new: false, bargain,
    });
    if (out.length >= PER_SUBURB) break;
  }
  return out;
}

async function searchSuburb(key: string, suburb: string, pc: string): Promise<Json> {
  const loc = `${suburb}, WA ${pc}`;
  const params = new URLSearchParams({
    channel: "buy", page: "1", pageSize: "20",
    searchLocation: loc, search: loc, surroundingSuburbs: "false",
    sortType: "relevance", maximumPrice: String(MAX_PRICE),
    minimumBedrooms: String(MIN_BEDS), propertyTypes: "house",
  });
  const res = await fetch(`${LIST_URL}?${params}`, {
    headers: { "X-RapidAPI-Key": key, "X-RapidAPI-Host": HOST },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${suburb}`);
  return (await res.json()) as Json;
}

export interface LiveResult {
  source: "realty-in-au" | "sample";
  note: string;
  count: number;
  listings: Listing[];
}

/** Pull live houses for one suburb (or the in-budget targets). Falls back to the
 *  committed sample when no RAPIDAPI_KEY is configured or a call fails. */
export async function searchListingsLive(opts: { suburb?: string; cap?: number } = {}): Promise<LiveResult> {
  const key = process.env.RAPIDAPI_KEY;
  // Sample fallback. When a suburb was asked for, RESPECT it: filter the sample
  // to that suburb (often empty) rather than dumping every committed listing,
  // which would misleadingly look like a sweep of unrelated suburbs.
  const sample = (reason: string): LiveResult => {
    const all = loadListings();
    const scoped = opts.suburb
      ? all.filter((L) => (L.suburb ?? "").toLowerCase() === opts.suburb!.toLowerCase())
      : all;
    const note = opts.suburb
      ? scoped.length
        ? `No live data for '${opts.suburb}' (${reason}); showing committed sample listings for it.`
        : `No live listings for '${opts.suburb}' right now (${reason}), and none in the committed sample. This is not a sweep of other suburbs.`
      : `No live data (${reason}); returning the committed sample. Set RAPIDAPI_KEY in Vercel for live data.`;
    return { source: "sample", note, listings: scoped, count: scoped.length };
  };
  if (!key) {
    console.warn("[listings] RAPIDAPI_KEY not set on this deployment; serving committed sample");
    return sample("no RAPIDAPI_KEY on this deployment");
  }

  const inBudget = SUBURBS.filter((s) => s.band);
  const targets = opts.suburb
    ? inBudget.filter((s) => s.name.toLowerCase() === opts.suburb!.toLowerCase())
    : inBudget.slice(0, opts.cap ?? 4);
  if (targets.length === 0) return { source: "sample", note: `Unknown or out-of-scope suburb '${opts.suburb}'.`, listings: [], count: 0 };

  const listings: Listing[] = [];
  let lastError = "";
  for (const s of targets) {
    try {
      const payload = await searchSuburb(key, s.name, s.pc);
      const raw = flatten(payload);
      const norm = normalise(raw, s.name, s.pc, s.mlo);
      // Diagnostic: raw rows from the API vs rows we kept after normalise. If
      // raw>0 but norm=0 the response SHAPE changed (parser miss); raw=0 means
      // the API genuinely returned nothing for these query params.
      console.log(`[listings] ${s.name}: api-rows=${raw.length} kept=${norm.length} payload-keys=[${Object.keys(payload).join(",")}]`);
      listings.push(...norm);
    } catch (e) {
      // skip this suburb; keep whatever else we gathered
      lastError = (e as Error).message;
      console.warn(`[listings] live fetch failed for ${s.name}: ${lastError}`);
    }
  }
  if (listings.length === 0) {
    console.warn(`[listings] key present but 0 live listings from ${targets.length} suburb(s) (last error: ${lastError || "none, empty result"}); serving sample`);
    return sample(lastError ? `live fetch error: ${lastError}` : "the live feed returned no matching houses");
  }
  console.log(`[listings] live OK: ${listings.length} listings from ${targets.length} suburb(s) via RapidAPI`);

  listings.sort((a, b) => (a.price ?? 9e9) - (b.price ?? 9e9));
  const capped = listings.slice(0, TOTAL_CAP);
  return {
    source: "realty-in-au",
    note: "Live houses (3+ beds, <=$1.1M, in-budget suburbs) from Realty in AU via RapidAPI. Not an official REA feed.",
    count: capped.length,
    listings: capped,
  };
}

/** Live listings for ANY WA suburb (not limited to the curated set) - the M2
 *  per-suburb pricing primitive. Returns [] when no RAPIDAPI_KEY is set or the
 *  call fails, so callers degrade gracefully rather than throw. */
export async function fetchSuburbListings(suburb: string, pc: string): Promise<Listing[]> {
  const key = process.env.RAPIDAPI_KEY;
  if (!key) {
    console.warn(`[listings] RAPIDAPI_KEY not set; no live prices for ${suburb}`);
    return [];
  }
  try {
    const payload = await searchSuburb(key, suburb, pc);
    const raw = flatten(payload);
    const out = normalise(raw, suburb, pc, undefined);
    console.log(`[listings] ${suburb}: api-rows=${raw.length} kept=${out.length} payload-keys=[${Object.keys(payload).join(",")}]`);
    return out;
  } catch (e) {
    console.warn(`[listings] live fetch failed for ${suburb}: ${(e as Error).message}`);
    return [];
  }
}
