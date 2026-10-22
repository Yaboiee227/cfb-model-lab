import { chromium } from 'playwright';
import fs from 'node:fs/promises';

const base = process.env.SITE_BASE_URL || 'http://127.0.0.1:8000';
const outDir = process.env.SITE_SMOKE_OUT || 'artifacts/site-smoke';
await fs.mkdir(outDir, { recursive: true });

const cases = [
  { name: 'cfb-desktop', path: '/', viewport: { width: 1440, height: 1000 }, league: 'cfb', expectedGames: 56 },
  { name: 'cfb-mobile', path: '/', viewport: { width: 390, height: 844 }, league: 'cfb', expectedGames: 56 },
  { name: 'nfl-desktop', path: '/?league=nfl', viewport: { width: 1440, height: 1000 }, league: 'nfl' },
  { name: 'nfl-mobile', path: '/?league=nfl', viewport: { width: 390, height: 844 }, league: 'nfl' },
  { name: 'week8-desktop', path: '/week-8.html', viewport: { width: 1440, height: 1000 }, week8: true, expectedGames: 56 },
  { name: 'week8-mobile', path: '/week-8.html', viewport: { width: 390, height: 844 }, week8: true, expectedGames: 56 }
];

const browser = await chromium.launch({ headless: true });
const report = [];
let failed = false;

for (const tc of cases) {
  const page = await browser.newPage({ viewport: tc.viewport });
  const errors = [];
  page.on('pageerror', err => errors.push(`pageerror: ${err.message}`));
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`console: ${msg.text()}`);
  });

  const url = `${base}${tc.path}`;
  const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
  if (!response || !response.ok()) errors.push(`HTTP ${response?.status() ?? 'no response'} for ${url}`);

  if (tc.week8) {
    await page.waitForFunction(() => document.querySelector('#weekCount')?.textContent?.trim() === '56', { timeout: 15000 }).catch(() => {});
    const count = await page.locator('#weekCount').textContent().catch(() => null);
    if (String(count || '').trim() !== String(tc.expectedGames)) errors.push(`Week 8 count expected ${tc.expectedGames}, got ${count}`);
    const release = await page.locator('#release').textContent().catch(() => '');
    if (/unavailable|error/i.test(release || '')) errors.push(`Week 8 release status shows failure: ${release}`);
  } else {
    await page.waitForFunction(() => {
      const text = document.querySelector('#gamesLoaded')?.textContent?.trim();
      return text && text !== '—' && text !== '0';
    }, { timeout: 15000 }).catch(() => {});

    const activeLeague = await page.evaluate(() => document.documentElement.dataset.league || 'cfb');
    if (activeLeague !== tc.league) errors.push(`Expected league ${tc.league}, got ${activeLeague}`);
    const loadedText = await page.locator('#gamesLoaded').textContent().catch(() => null);
    const loaded = Number(String(loadedText || '').replace(/[^0-9]/g, ''));
    if (!Number.isFinite(loaded) || loaded <= 0) errors.push(`No games loaded: ${loadedText}`);
    if (tc.expectedGames && loaded !== tc.expectedGames) errors.push(`Expected ${tc.expectedGames} games, got ${loaded}`);
  }

  const layout = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    bodyScrollWidth: document.body.scrollWidth,
    bodyClientWidth: document.body.clientWidth,
    title: document.title
  }));
  if (layout.scrollWidth > layout.clientWidth + 2) errors.push(`Horizontal document overflow ${layout.scrollWidth}px > ${layout.clientWidth}px`);
  if (layout.bodyScrollWidth > layout.bodyClientWidth + 2) errors.push(`Horizontal body overflow ${layout.bodyScrollWidth}px > ${layout.bodyClientWidth}px`);

  const screenshot = `${outDir}/${tc.name}.png`;
  await page.screenshot({ path: screenshot, fullPage: true });
  report.push({ name: tc.name, url, viewport: tc.viewport, layout, errors, screenshot });
  if (errors.length) failed = true;
  await page.close();
}

await browser.close();
await fs.writeFile(`${outDir}/report.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
if (failed) process.exit(1);
