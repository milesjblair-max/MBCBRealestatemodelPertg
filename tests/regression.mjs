// regression.mjs - browser-driven regression tests for web/index.html.
//
// Renders the real tool in headless Chromium and asserts the invariants that
// have bitten us before: broken portal URLs, the duplicated Como label,
// collapsible sections, the AVM estimate/scorecard, and the reset contract.
// Exits non-zero on any failure so tests/run.sh can gate a deploy.
//
// Add a check here whenever we add a feature or fix a bug, so the fix sticks.
import { chromium } from 'playwright-core';
import { fileURLToPath } from 'url';
import path from 'path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const url = 'file://' + root + '/web/index.html';
const exe = process.env.PW_EXECUTABLE || undefined;

let fails = 0, passes = 0;
function ok(cond, msg) {
  if (cond) { passes++; } else { fails++; console.error('  FAIL: ' + msg); }
}

const browser = await chromium.launch(exe ? { executablePath: exe } : {});
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const consoleErrors = [];
page.on('pageerror', e => consoleErrors.push('pageerror: ' + e.message));
page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });

await page.goto(url);
await page.waitForTimeout(300);

// ---- load + chrome ----
ok(consoleErrors.length === 0, 'no console errors on load: ' + JSON.stringify(consoleErrors));
ok(await page.$('link[rel="icon"]') !== null, 'favicon present');

// ---- tabs ----
const tabs = await page.$$eval('.tab', ts => ts.map(t => t.getAttribute('data-target')));
ok(tabs.length === 4 && ['listings', 'modelling', 'construction', 'criteria'].every(t => tabs.includes(t)),
  'four tabs present: ' + tabs);

// ---- listings order A, B, C ----
const order = await page.$$eval('section[data-tab="listings"]', ns => ns.map(n => n.id));
ok(JSON.stringify(order) === JSON.stringify(['avm', 'listings', 'properties']),
  'listings order is estimator, watchlist, properties: ' + order);

// ---- collapsibles ----
const caretCount = await page.$$eval('.sec-head .caret svg', n => n.length);
ok(caretCount >= 7, 'every section has a chevron caret: ' + caretCount);
ok(await page.$('#avm .caret') !== null, 'section A (estimator) is collapsible');
const before = await page.$eval('#properties', n => n.classList.contains('collapsed'));
await page.click('#properties .sec-head');
const after = await page.$eval('#properties', n => n.classList.contains('collapsed'));
ok(before !== after, 'clicking a section header toggles collapse');

// ---- portal URL formats (the REIWA/REA/Domain bug class) ----
const urlCheck = await page.evaluate(() => {
  const bad = [];
  for (const s of SUBURBS) {
    const u = listingUrls(s);
    const slug = s.name.toLowerCase().replace(/ /g, '-');
    if (!/^https:\/\/www\.realestate\.com\.au\/buy\/property-house-with-3-bedrooms-between-0-1100000-in-/.test(u.rea)) bad.push('rea ' + s.name + ' ' + u.rea);
    if (!/^https:\/\/www\.domain\.com\.au\/sale\/[a-z0-9-]+-wa-\d{4}\//.test(u.dom)) bad.push('dom ' + s.name + ' ' + u.dom);
    if (u.reiwa !== `https://reiwa.com.au/for-sale/${slug}/houses/`) bad.push('reiwa ' + s.name + ' ' + u.reiwa);
    for (const k of ['rea', 'dom', 'reiwa']) {
      try { new URL(u[k]); } catch (e) { bad.push('unparseable ' + k + ' ' + s.name); }
      if (/\s/.test(u[k])) bad.push('whitespace ' + k + ' ' + s.name);
    }
  }
  return bad;
});
ok(urlCheck.length === 0, 'all suburb portal URLs are valid and correctly formatted: ' + JSON.stringify(urlCheck.slice(0, 4)));

// ---- inline listing URLs are valid absolute https ----
const inlineBad = await page.evaluate(() => {
  const bad = [];
  for (const l of INLINE_LISTINGS.listings) {
    try { const u = new URL(l.url); if (u.protocol !== 'https:') bad.push(l.suburb); } catch (e) { bad.push(l.suburb); }
  }
  return bad;
});
ok(inlineBad.length === 0, 'inline listing URLs are valid https: ' + JSON.stringify(inlineBad));

// ---- AVM engine + lookups ----
const avm = await page.evaluate(() => {
  const r = avmEstimate('Shelley', 696, 3, 1, 'original');
  const looks = avmLookups('31 saunders street como', r);
  return {
    likely: r.likely, low: r.low, high: r.high, conf: r.conf,
    nLooks: looks.length,
    allGoogle: looks.every(l => /^https:\/\/www\.google\.com\/search\?q=/.test(l[1])),
    looksValid: looks.every(l => { try { new URL(l[1]); return true; } catch (e) { return false; } })
  };
});
ok(avm.likely === 915, 'AVM Shelley 3/1/696 original likely = $915k (got ' + avm.likely + ')');
ok(avm.low < avm.likely && avm.high > avm.likely, 'AVM range brackets the likely value');
ok(avm.nLooks === 4, 'AVM produces 4 sale-history lookups');
ok(avm.allGoogle && avm.looksValid, 'AVM lookups are all valid Google searches');

// ---- AVM UI renders ----
await page.fill('#avmAddr', '12 Example St, Shelley WA 6148, 4 bed 2 bath 720m2');
await page.dispatchEvent('#avmAddr', 'input');
ok(await page.inputValue('#avmBeds') === '4' && await page.inputValue('#avmLand') === '720',
  'pasted listing auto-fills beds and land');
await page.click('#avmGo');
await page.waitForTimeout(150);
ok((await page.textContent('.avm-headline .big')).includes('$'), 'AVM headline renders a dollar figure');
ok(await page.$('.avm-fit .ring') !== null, 'AVM fit ring renders');
ok((await page.$$('.avm-col.pros li')).length > 0, 'AVM pros render');
ok((await page.$$('.avm-lookup a')).length === 4, 'AVM renders 4 lookup links');

// ---- map: Como once, no duplicate; bubbles; legend key ----
await page.evaluate(() => showTab('modelling', false));
await page.waitForTimeout(150);
const comoLabels = await page.$$eval('#heatMap text', ts => ts.filter(t => t.textContent.trim() === 'Como').length);
ok(comoLabels === 1, 'Como appears exactly once on the map (no duplicate): ' + comoLabels);
const bubbles = await page.$$eval('#heatMap g.bubble', g => g.length);
ok(bubbles === 13, 'map draws 13 suburb bubbles (Como excluded as the anchor): ' + bubbles);
ok(await page.$('.map-legend .lg-grad') !== null, 'map has a colour-key gradient');
ok((await page.$$('.map-legend .lg-row')).length >= 3, 'map legend explains fit, over-budget and anchor');

// ---- reset contract: weights restore to 30/50/20 ----
await page.evaluate(() => { document.getElementById('bearSlider').value = 60; document.getElementById('bearSlider').dispatchEvent(new Event('input', { bubbles: true })); });
await page.click('#resetForecast');
await page.waitForTimeout(100);
const w = await page.evaluate(() => ({ bear: Math.round(W.bear), base: Math.round(W.base), bull: Math.round(W.bull) }));
ok(w.bear === 30 && w.base === 50 && w.bull === 20, 'reset restores baseline weights 30/50/20: ' + JSON.stringify(w));

// ---- opens at the top, not jumped to a mid-page section id ----
// about:blank first so the next goto is a real document load (not a same-doc
// fragment nav, which would not re-run the boot code).
await page.goto('about:blank');
await page.goto(url + '#listings');
await page.waitForTimeout(350);
const scrollY = await page.evaluate(() => window.scrollY);
ok(scrollY < 5, 'page opens at the top even with a #listings hash (scrollY=' + scrollY + ')');

// ---- no console errors accumulated through all interactions ----
ok(consoleErrors.length === 0, 'no console errors after interactions: ' + JSON.stringify(consoleErrors));

await browser.close();
console.log(`\nregression.mjs: ${passes} passed, ${fails} failed`);
process.exit(fails ? 1 : 0);
