import { chromium } from 'playwright';
import fs from 'node:fs/promises';

const base = process.env.SITE_BASE_URL || 'http://127.0.0.1:8000';
const outDir = process.env.SITE_SMOKE_OUT || 'artifacts/site-smoke';
await fs.mkdir(outDir, { recursive: true });

const cases = [
  { name: 'cfb-desktop', path: '/', viewport: { width: 1440, height: 1000 }, league: 'cfb', expectedGames: 56, testProjectionNav: true },
  { name: 'cfb-mobile', path: '/', viewport: { width: 390, height: 844 }, league: 'cfb', expectedGames: 56, testSlateNavigation: true, testProjectionNav: true },
  { name: 'nfl-desktop', path: '/?league=nfl', viewport: { width: 1440, height: 1000 }, league: 'nfl', testProjectionNav: true },
  { name: 'nfl-mobile', path: '/?league=nfl', viewport: { width: 390, height: 844 }, league: 'nfl', testProjectionNav: true },
  { name: 'week8-desktop', path: '/week-8.html', viewport: { width: 1440, height: 1000 }, week8: true, expectedGames: 56 },
  { name: 'week8-mobile', path: '/week-8.html', viewport: { width: 390, height: 844 }, week8: true, expectedGames: 56 }
];

const browser = await chromium.launch({ headless: true });
const report = [];
let failed = false;

for (const tc of cases) {
  const page = await browser.newPage({ viewport: tc.viewport });
  const errors = [];
  const failedRequests = [];
  page.on('pageerror', err => errors.push(`pageerror: ${err.message}`));
  page.on('requestfailed', req => failedRequests.push(`${req.method()} ${req.url()} :: ${req.failure()?.errorText || 'failed'}`));
  page.on('response', res => {
    if (res.status() >= 400) failedRequests.push(`HTTP ${res.status()} ${res.url()}`);
  });
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`console: ${msg.text()}`);
  });

  const url = `${base}${tc.path}`;
  const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
  if (!response || !response.ok()) errors.push(`HTTP ${response?.status() ?? 'no response'} for ${url}`);

  let projectionIntegrity = null;
  let navigationIntegrity = null;

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

    await page.waitForFunction(expected => {
      const rows = document.querySelectorAll('#projectionBody tr[id^="game-"]').length;
      const cards = document.querySelectorAll('#projectionCards .projection-card[id^="card-"]').length;
      return rows === expected && cards === expected;
    }, loaded, { timeout: 15000 }).catch(() => {});

    projectionIntegrity = await page.evaluate(() => ({
      loadedText: document.querySelector('#gamesLoaded')?.textContent?.trim() || '',
      projectionCountText: document.querySelector('#projectionCount')?.textContent?.trim() || '',
      rowCount: document.querySelectorAll('#projectionBody tr[id^="game-"]').length,
      cardCount: document.querySelectorAll('#projectionCards .projection-card[id^="card-"]').length,
      renderState: document.documentElement.dataset.slateRender || ''
    }));
    if (projectionIntegrity.rowCount !== loaded) errors.push(`Projection table rendered ${projectionIntegrity.rowCount}/${loaded} games`);
    if (projectionIntegrity.cardCount !== loaded) errors.push(`Projection cards rendered ${projectionIntegrity.cardCount}/${loaded} games`);

    if (tc.testSlateNavigation) {
      await page.waitForSelector('#slateNavigation', { timeout: 15000 }).catch(() => {});
      const currentSlate = await page.evaluate(() => {
        let games = [];
        let week = '';
        try {
          games = Array.isArray(STATE?.projections) ? STATE.projections : [];
          week = String(document.querySelector('#weekFilter')?.value || STATE?.config?.currentWeek || '');
        } catch (_) {}
        const scoped = games.filter(game => !week || String(game.week) === week);
        const byDate = scoped.reduce((acc, game) => {
          if (game.date) acc[game.date] = (acc[game.date] || 0) + 1;
          return acc;
        }, {});
        const dates = Object.keys(byDate).sort();
        return {
          week,
          total: scoped.length,
          sampleDate: dates[0] || '',
          sampleDateCount: dates.length ? byDate[dates[0]] : 0
        };
      });

      const summaryBefore = await page.locator('#slateNavigationStatus').textContent().catch(() => '');
      const expectedSummary = new RegExp(`${currentSlate.total}\\s+CFB${currentSlate.week ? `\\s+Week\\s+${currentSlate.week}` : ''}\\s+games\\s+loaded`, 'i');
      if (!expectedSummary.test(summaryBefore || '')) errors.push(`Full-slate mobile summary incorrect: ${summaryBefore}`);

      const sampleChip = currentSlate.sampleDate
        ? page.locator(`#slateDayChips .slate-day-chip[data-date="${currentSlate.sampleDate}"]`)
        : page.locator('#slateDayChips .slate-day-chip[data-date]:not([data-date=""])').first();
      if (currentSlate.sampleDate && await sampleChip.count()) {
        await sampleChip.click();
        await page.waitForFunction(expected => document.querySelectorAll('#projectionCards .projection-card[id^="card-"]').length === expected, currentSlate.sampleDateCount, { timeout: 10000 }).catch(() => {});
        const sampleCards = await page.locator('#projectionCards .projection-card[id^="card-"]').count();
        if (sampleCards !== currentSlate.sampleDateCount) errors.push(`Date quick filter expected ${currentSlate.sampleDateCount} games, got ${sampleCards}`);

        await page.locator('#slateDayChips .slate-day-chip[data-date=""]').click();
        await page.waitForFunction(expected => document.querySelectorAll('#projectionCards .projection-card[id^="card-"]').length === expected, currentSlate.total, { timeout: 10000 }).catch(() => {});
        const restoredCards = await page.locator('#projectionCards .projection-card[id^="card-"]').count();
        if (restoredCards !== currentSlate.total) errors.push(`Show-all recovery expected ${currentSlate.total} games, got ${restoredCards}`);
        navigationIntegrity = {
          summaryBefore,
          activeWeek: currentSlate.week,
          sampledDate: currentSlate.sampleDate,
          sampleCards,
          restoredCards
        };
      } else {
        errors.push('Current-slate date quick-filter chip missing on CFB mobile');
      }
    }

    if (tc.testProjectionNav) {
      await page.locator('#teamSearch').fill(tc.league === 'cfb' ? 'Virginia' : 'Chiefs');
      await page.waitForTimeout(75);
      const narrowedCards = await page.locator('#projectionCards .projection-card[id^="card-"]').count();
      if (narrowedCards >= loaded) errors.push(`Projection-nav setup did not narrow the slate: ${narrowedCards}/${loaded}`);

      const projectionLink = page.locator('.primary-nav a[href="#projections"]').first();
      if (!(await projectionLink.count())) {
        errors.push('Primary Projections navigation link missing');
      } else {
        if (!(await projectionLink.isVisible().catch(() => false))) {
          const mobileToggle = page.locator('#cbMobileNavToggle');
          if (await mobileToggle.count()) {
            await mobileToggle.click();
            await projectionLink.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
          }
        }
        await projectionLink.click();
        await page.waitForFunction(expected => {
          const cards = document.querySelectorAll('#projectionCards .projection-card[id^="card-"]').length;
          const rows = document.querySelectorAll('#projectionBody tr[id^="game-"]').length;
          const search = document.querySelector('#teamSearch')?.value || '';
          const date = document.querySelector('#dateFilter')?.value || '';
          return cards === expected && rows === expected && !search && !date && location.hash === '#projections';
        }, loaded, { timeout: 10000 }).catch(() => {});

        const projectionNavState = await page.evaluate(() => ({
          hash: location.hash,
          search: document.querySelector('#teamSearch')?.value || '',
          week: document.querySelector('#weekFilter')?.value || '',
          date: document.querySelector('#dateFilter')?.value || '',
          sort: document.querySelector('#sortFilter')?.value || '',
          rowCount: document.querySelectorAll('#projectionBody tr[id^="game-"]').length,
          cardCount: document.querySelectorAll('#projectionCards .projection-card[id^="card-"]').length,
          mobileNavOpen: document.body.dataset.navOpen || 'false'
        }));
        if (projectionNavState.cardCount !== loaded || projectionNavState.rowCount !== loaded) errors.push(`Projections tab did not restore full current-week slate: ${projectionNavState.cardCount}/${loaded}`);
        if (projectionNavState.search || projectionNavState.date) errors.push(`Projections tab left filters active: ${JSON.stringify(projectionNavState)}`);
        if (projectionNavState.sort !== 'kickoff') errors.push(`Projections tab did not restore kickoff order: ${projectionNavState.sort}`);
        if (projectionNavState.hash !== '#projections') errors.push(`Projections tab did not land on #projections: ${projectionNavState.hash}`);
        if (tc.viewport.width <= 820 && projectionNavState.mobileNavOpen === 'true') errors.push('Mobile navigation remained open after selecting Projections');
        navigationIntegrity = { ...(navigationIntegrity || {}), narrowedCards, projectionNavState };
      }
    }
  }

  const layout = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    bodyScrollWidth: document.body.scrollWidth,
    bodyClientWidth: document.body.clientWidth,
    title: document.title
  }));

  const overflowOffenders = await page.evaluate(() => {
    const vw = document.documentElement.clientWidth;
    return [...document.querySelectorAll('body *')].map((el, index) => {
      const r = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      return {
        index,
        tag: el.tagName.toLowerCase(),
        id: el.id || '',
        className: typeof el.className === 'string' ? el.className : '',
        left: Math.round(r.left), right: Math.round(r.right), width: Math.round(r.width),
        position: style.position, overflowX: style.overflowX, display: style.display
      };
    }).filter(x => x.right > vw + 2 || x.left < -2)
      .sort((a,b) => (b.right - vw) - (a.right - vw))
      .slice(0, 20);
  });

  if (layout.scrollWidth > layout.clientWidth + 2) errors.push(`Horizontal document overflow ${layout.scrollWidth}px > ${layout.clientWidth}px`);
  if (layout.bodyScrollWidth > layout.bodyClientWidth + 2) errors.push(`Horizontal body overflow ${layout.bodyScrollWidth}px > ${layout.bodyClientWidth}px`);

  const screenshot = `${outDir}/${tc.name}.png`;
  await page.screenshot({ path: screenshot, fullPage: true });
  report.push({ name: tc.name, url, viewport: tc.viewport, layout, projectionIntegrity, navigationIntegrity, overflowOffenders, failedRequests, errors, screenshot });
  if (errors.length) failed = true;
  await page.close();
}

await browser.close();
await fs.writeFile(`${outDir}/report.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
if (failed) process.exit(1);
