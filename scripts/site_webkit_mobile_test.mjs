import { webkit } from 'playwright';
import fs from 'node:fs/promises';

const base = process.env.SITE_BASE_URL || 'http://127.0.0.1:8000';
const outDir = process.env.SITE_SMOKE_OUT || 'artifacts/site-webkit';
await fs.mkdir(outDir, { recursive: true });

const browser = await webkit.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
const errors = [];
const failedRequests = [];
page.on('pageerror', err => errors.push(`pageerror: ${err.message}`));
page.on('requestfailed', req => failedRequests.push(`${req.method()} ${req.url()} :: ${req.failure()?.errorText || 'failed'}`));
page.on('response', res => { if (res.status() >= 400) failedRequests.push(`HTTP ${res.status()} ${res.url()}`); });
page.on('console', msg => { if (msg.type() === 'error') errors.push(`console: ${msg.text()}`); });

const response = await page.goto(`${base}/`, { waitUntil: 'networkidle', timeout: 30000 });
if (!response || !response.ok()) errors.push(`page load failed: ${response?.status() ?? 'no response'}`);

await page.waitForFunction(() => document.querySelectorAll('#projectionCards .projection-card[id^="card-"]').length === 56, { timeout: 15000 }).catch(() => {});
let cards = await page.locator('#projectionCards .projection-card[id^="card-"]').count();
if (cards !== 56) errors.push(`expected 56 projection cards, got ${cards}`);

const lastCard = page.locator('#projectionCards .projection-card[id^="card-"]').last();
await lastCard.scrollIntoViewIfNeeded().catch(() => {});
const lastVisible = await lastCard.evaluate(el => {
  const r = el.getBoundingClientRect();
  const s = getComputedStyle(el);
  return { display: s.display, visibility: s.visibility, opacity: s.opacity, height: r.height, top: r.top, bottom: r.bottom, contentVisibility: s.contentVisibility };
}).catch(() => null);
if (!lastVisible || lastVisible.display === 'none' || lastVisible.visibility === 'hidden' || Number(lastVisible.opacity) === 0 || lastVisible.height < 20) {
  errors.push(`last projection card not visibly rendered: ${JSON.stringify(lastVisible)}`);
}

const toggle = page.locator('#cbMobileNavToggle');
await toggle.click();
const research = page.locator('.primary-nav a[href="#research"]');
await research.click();
await page.waitForTimeout(350);
const researchState = await page.evaluate(() => {
  const el = document.getElementById('research');
  const r = el?.getBoundingClientRect();
  const s = el ? getComputedStyle(el) : null;
  return { hash: location.hash, top: r?.top ?? null, opacity: s?.opacity ?? null, visibility: s?.visibility ?? null, navOpen: document.body.dataset.navOpen };
});
if (researchState.hash !== '#research') errors.push(`research tab did not set hash: ${researchState.hash}`);
if (researchState.opacity === '0' || researchState.visibility === 'hidden') errors.push(`research section hidden after navigation: ${JSON.stringify(researchState)}`);
if (researchState.navOpen === 'true') errors.push('mobile navigation remained open after Research click');

await toggle.click();
const projections = page.locator('.primary-nav a[href="#projections"]');
await projections.click();
await page.waitForTimeout(350);
cards = await page.locator('#projectionCards .projection-card[id^="card-"]').count();
const projectionState = await page.evaluate(() => ({
  hash: location.hash,
  week: document.getElementById('weekFilter')?.value || '',
  date: document.getElementById('dateFilter')?.value || '',
  conference: document.getElementById('conferenceFilter')?.value || '',
  search: document.getElementById('teamSearch')?.value || '',
  count: document.querySelectorAll('#projectionCards .projection-card[id^="card-"]').length,
  navOpen: document.body.dataset.navOpen,
  width: document.documentElement.scrollWidth,
  viewport: document.documentElement.clientWidth
}));
if (projectionState.hash !== '#projections') errors.push(`projections tab did not set hash: ${projectionState.hash}`);
if (projectionState.count !== 56) errors.push(`projections tab did not restore 56 cards: ${projectionState.count}`);
if (projectionState.date || projectionState.conference || projectionState.search) errors.push(`projections tab left filters active: ${JSON.stringify(projectionState)}`);
if (projectionState.navOpen === 'true') errors.push('mobile navigation remained open after Projections click');
if (projectionState.width > projectionState.viewport + 2) errors.push(`horizontal overflow ${projectionState.width} > ${projectionState.viewport}`);

await page.screenshot({ path: `${outDir}/cfb-mobile-webkit.png`, fullPage: true });
const report = { base, cards, lastVisible, researchState, projectionState, failedRequests, errors };
await fs.writeFile(`${outDir}/report.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
await browser.close();
if (failedRequests.length || errors.length) process.exit(1);
