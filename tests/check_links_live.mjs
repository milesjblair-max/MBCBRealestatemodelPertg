// check_links_live.mjs - hit the real portal URLs and fail on dead links.
//
// This is the test that would have caught the REIWA 404. It can only run where
// there is outbound network (e.g. GitHub Actions), NOT in the sandbox, which is
// firewalled off the portals. It renders the page, collects the generated
// portal URLs, and GETs a sample. It fails ONLY on 404/410 (a genuinely dead
// path); 403/429/timeouts are treated as "reachable but bot-guarded", not a
// failure, to avoid false alarms from portal bot protection.
import { chromium } from 'playwright-core';
import { fileURLToPath } from 'url';
import path from 'path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const url = 'file://' + root + '/web/index.html';
const exe = process.env.PW_EXECUTABLE || undefined;

const browser = await chromium.launch(exe ? { executablePath: exe } : {});
const page = await browser.newPage();
await page.goto(url);

// Collect one URL set per first few suburbs (enough to validate each portal's format).
const urls = await page.evaluate(() => {
  const out = [];
  for (const s of SUBURBS.slice(0, 4)) {
    const u = listingUrls(s);
    out.push(['REA ' + s.name, u.rea], ['Domain ' + s.name, u.dom], ['REIWA ' + s.name, u.reiwa]);
  }
  return out;
});
await browser.close();

let dead = 0;
for (const [label, u] of urls) {
  let status = 0, note = '';
  try {
    const res = await fetch(u, { method: 'GET', redirect: 'follow', headers: { 'User-Agent': 'Mozilla/5.0 regression-linkcheck' } });
    status = res.status;
  } catch (e) { note = 'network/' + (e.code || e.name || 'err'); }
  const isDead = status === 404 || status === 410;
  if (isDead) dead++;
  console.log(`${isDead ? 'DEAD' : ' ok '} [${status || note}] ${label} -> ${u}`);
}
console.log(`\ncheck_links_live.mjs: ${dead} dead link(s)`);
process.exit(dead ? 1 : 0);
