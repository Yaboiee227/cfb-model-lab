import { webkit } from 'playwright';
import fs from 'node:fs/promises';

const base = process.env.SITE_BASE_URL || 'http://127.0.0.1:8000';
const outDir = process.env.SITE_SMOKE_OUT || 'artifacts/site-webkit';
await fs.mkdir(outDir, { recursive: true });

const cases = [
  { name: 'cfb-mobile-webkit', path: '/', league: 'cfb', expectedGames: 56, search: 'Virginia' },
  { name: 'nfl-mobile-webkit', path: '/?league=nfl', league: 'nfl', expectedGames: 14, search: 'Chiefs' }
];

const browser = await webkit.launch({ headless: true });
const report = [];
let failed = false;

for (const tc of cases) {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const errors = [];
  const failedRequests = [];
  page.on('pageerror', err => errors.push(`pageerror: ${err.message}`));
  page.on('requestfailed', req => failedRequests.push(`${req.method()} ${req.url()} :: ${req.failure()?.errorText || 'failed'}`));
  page.on('response', res => { if (res.status() >= 400) failedRequests.push(`HTTP ${res.status()} ${res.url()}`); });
  page.on('console', msg => { if (msg.type() === 'error') errors.push(`console: ${msg.text()}`); });

  const response = await page.goto(`${base}${tc.path}`, { waitUntil: 'networkidle', timeout: 30000 });
  if (!response || !response.ok()) errors.push(`page load failed: ${response?.status() ?? 'no response'}`);

  await page.waitForFunction(expected => {
    const cards = document.querySelectorAll('#projectionCards .projection-card[id^="card-"]').length;
    const loaded = Number((document.querySelector('#gamesLoaded')?.textContent || '').replace(/[^0-9]/g, ''));
    return cards === expected && loaded === expected && document.body.classList.contains('site-v2');
  }, tc.expectedGames, { timeout: 20000 }).catch(() => {});

  const activeLeague = await page.evaluate(() => document.documentElement.dataset.league || 'cfb');
  if (activeLeague !== tc.league) errors.push(`expected league ${tc.league}, got ${activeLeague}`);

  let cards = await page.locator('#projectionCards .projection-card[id^="card-"]').count();
  if (cards !== tc.expectedGames) errors.push(`expected ${tc.expectedGames} projection cards, got ${cards}`);

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

  await page.evaluate(() => window.scrollTo(0, 0));
  const shellClosed = await page.evaluate(() => {
    const header = document.querySelector('.site-header')?.getBoundingClientRect();
    const inner = document.querySelector('.header-inner')?.getBoundingClientRect();
    const nav = document.querySelector('.primary-nav');
    const navStyle = nav ? getComputedStyle(nav) : null;
    const controls = ['.brand', '#cbMobileNavToggle', '#leagueSwitch', '#themeToggle']
      .map(selector => document.querySelector(selector)?.getBoundingClientRect())
      .filter(Boolean)
      .map(r => ({ left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height }));
    return {
      header: header && { top: header.top, bottom: header.bottom, height: header.height },
      inner: inner && { top: inner.top, bottom: inner.bottom, height: inner.height },
      navDisplay: navStyle?.display || '',
      navOpen: document.body.dataset.navOpen,
      controls,
      scrollWidth: document.documentElement.scrollWidth,
      viewport: document.documentElement.clientWidth
    };
  });

  if (!shellClosed.header || shellClosed.header.height > 82) errors.push(`mobile header unexpectedly tall/wrapped: ${JSON.stringify(shellClosed.header)}`);
  if (shellClosed.navOpen === 'true') errors.push('mobile navigation starts open');
  if (shellClosed.navDisplay !== 'none') errors.push(`mobile navigation should be collapsed initially, got ${shellClosed.navDisplay}`);
  if (shellClosed.scrollWidth > shellClosed.viewport + 2) errors.push(`horizontal overflow ${shellClosed.scrollWidth} > ${shellClosed.viewport}`);
  for (const control of shellClosed.controls) {
    if (control.left < -1 || control.right > shellClosed.viewport + 1) errors.push(`header control outside viewport: ${JSON.stringify(control)}`);
    if (shellClosed.header && (control.top < shellClosed.header.top - 1 || control.bottom > shellClosed.header.bottom + 1)) errors.push(`header control escaped header bounds: ${JSON.stringify(control)}`);
  }

  const toggle = page.locator('#cbMobileNavToggle');
  if (!(await toggle.count())) {
    errors.push('mobile navigation toggle missing');
  } else {
    await toggle.click();
    const openState = await page.evaluate(() => {
      const header = document.querySelector('.site-header')?.getBoundingClientRect();
      const nav = document.querySelector('.primary-nav')?.getBoundingClientRect();
      const style = document.querySelector('.primary-nav') ? getComputedStyle(document.querySelector('.primary-nav')) : null;
      return {
        navOpen: document.body.dataset.navOpen,
        display: style?.display || '',
        headerBottom: header?.bottom ?? null,
        navTop: nav?.top ?? null,
        navBottom: nav?.bottom ?? null,
        viewportHeight: innerHeight
      };
    });
    if (openState.navOpen !== 'true' || openState.display === 'none') errors.push(`mobile navigation did not open: ${JSON.stringify(openState)}`);
    if (openState.headerBottom !== null && openState.navTop !== null && openState.navTop < openState.headerBottom - 2) errors.push(`mobile menu overlaps header: ${JSON.stringify(openState)}`);

    const research = page.locator('.primary-nav a[href="#research"]');
    await research.click();
    await page.waitForTimeout(250);
    const researchState = await page.evaluate(() => ({
      hash: location.hash,
      navOpen: document.body.dataset.navOpen,
      opacity: getComputedStyle(document.getElementById('research')).opacity,
      visibility: getComputedStyle(document.getElementById('research')).visibility
    }));
    if (researchState.hash !== '#research') errors.push(`research tab did not set hash: ${researchState.hash}`);
    if (researchState.opacity === '0' || researchState.visibility === 'hidden') errors.push(`research section hidden after navigation: ${JSON.stringify(researchState)}`);
    if (researchState.navOpen === 'true') errors.push('mobile navigation remained open after Research click');
  }

  await page.locator('#teamSearch').fill(tc.search);
  await page.waitForTimeout(100);
  const narrowed = await page.locator('#projectionCards .projection-card[id^="card-"]').count();
  if (narrowed >= tc.expectedGames) errors.push(`search did not narrow ${tc.league} slate: ${narrowed}/${tc.expectedGames}`);

  await toggle.click();
  await page.locator('.primary-nav a[href="#projections"]').first().click();
  await page.waitForFunction(expected => {
    return document.querySelectorAll('#projectionCards .projection-card[id^="card-"]').length === expected &&
      !(document.querySelector('#teamSearch')?.value || '') &&
      location.hash === '#projections' &&
      document.body.dataset.navOpen !== 'true';
  }, tc.expectedGames, { timeout: 10000 }).catch(() => {});

  cards = await page.locator('#projectionCards .projection-card[id^="card-"]').count();
  const projectionState = await page.evaluate(() => ({
    hash: location.hash,
    search: document.getElementById('teamSearch')?.value || '',
    date: document.getElementById('dateFilter')?.value || '',
    count: document.querySelectorAll('#projectionCards .projection-card[id^="card-"]').length,
    navOpen: document.body.dataset.navOpen,
    width: document.documentElement.scrollWidth,
    viewport: document.documentElement.clientWidth
  }));
  if (projectionState.hash !== '#projections') errors.push(`projections tab did not set hash: ${projectionState.hash}`);
  if (projectionState.count !== tc.expectedGames) errors.push(`projections tab did not restore ${tc.expectedGames} cards: ${projectionState.count}`);
  if (projectionState.search || projectionState.date) errors.push(`projections tab left filters active: ${JSON.stringify(projectionState)}`);
  if (projectionState.navOpen === 'true') errors.push('mobile navigation remained open after Projections click');
  if (projectionState.width > projectionState.viewport + 2) errors.push(`horizontal overflow after navigation ${projectionState.width} > ${projectionState.viewport}`);

  const screenshot = `${outDir}/${tc.name}.png`;
  await page.screenshot({ path: screenshot, fullPage: false });
  report.push({ ...tc, cards, lastVisible, shellClosed, projectionState, failedRequests, errors, screenshot });
  if (failedRequests.length || errors.length) failed = true;
  await page.close();
}

await browser.close();
await fs.writeFile(`${outDir}/report.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
if (failed) process.exit(1);
