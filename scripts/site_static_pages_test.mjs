import { webkit } from 'playwright';

const base = process.env.SITE_BASE_URL || 'http://127.0.0.1:8000';
const pages = [
  { page: 'recap', path: '/recap.html', marker: '#performance' },
  { page: 'ratings', path: '/ratings.html', marker: '#ratings' }
];

async function rankingExpectation(league) {
  const response = await fetch(`${base}/data/power-rankings/${league}.json`, { cache: 'no-store' });
  if (!response.ok) throw new Error(`Could not load ${league} power-ranking snapshot (${response.status})`);
  const snapshot = await response.json();
  const teams = Array.isArray(snapshot.teams) ? snapshot.teams : [];
  const matchups = Array.isArray(snapshot.remainingMatchupComparisons) ? snapshot.remainingMatchupComparisons : [];
  return {
    teams: teams.length,
    matchups: matchups.length,
    renderedMatchupRows: Math.max(1, matchups.length),
    topTeam: teams[0]?.teamName || teams[0]?.team || ''
  };
}

const expectedRatings = {
  cfb: await rankingExpectation('cfb'),
  nfl: await rankingExpectation('nfl')
};

const cases = [];
for (const page of pages) {
  for (const league of ['cfb', 'nfl']) {
    for (const width of [390, 1440]) {
      const query = league === 'nfl' ? '?league=nfl' : '';
      cases.push({ ...page, league, width, path: `${page.path}${query}` });
    }
  }
}

const browser = await webkit.launch({ headless: true });
const report = [];
let failed = false;

for (const tc of cases) {
  const mobile = tc.width < 900;
  const page = await browser.newPage({ viewport: { width: tc.width, height: 844 }, isMobile: mobile, hasTouch: mobile });
  const errors = [];
  const failedRequests = [];
  page.on('pageerror', err => errors.push(`pageerror: ${err.message}`));
  page.on('requestfailed', req => failedRequests.push(`${req.method()} ${req.url()} :: ${req.failure()?.errorText || 'failed'}`));
  page.on('response', res => { if (res.status() >= 400) failedRequests.push(`HTTP ${res.status()} ${res.url()}`); });

  const response = await page.goto(`${base}${tc.path}`, { waitUntil: 'networkidle', timeout: 30000 });
  if (!response || !response.ok()) errors.push(`page load failed: ${response?.status() ?? 'no response'}`);

  await page.waitForFunction(({ kind, league, expected }) => {
    if (kind === 'recap') return document.getElementById('graded')?.textContent?.trim() !== '—';
    const count = document.getElementById('count')?.textContent || '';
    const matchupCount = document.getElementById('matchupCount')?.textContent || '';
    const bodyRows = document.querySelectorAll('#ratingsBody tr').length;
    const matchupRows = document.querySelectorAll('#matchupsBody tr').length;
    const target = expected[league];
    return count.includes(`${target.teams} of ${target.teams} teams`) &&
      matchupCount.includes(`${target.matchups} current comparisons`) &&
      bodyRows === target.teams && matchupRows === target.renderedMatchupRows;
  }, { kind: tc.page, league: tc.league, expected: expectedRatings }, { timeout: 15000 }).catch(() => {});

  const state = await page.evaluate(({ kind }) => {
    const nav = document.querySelector('.page-nav');
    const topbar = document.querySelector('.topbar')?.getBoundingClientRect();
    const activeLeague = document.querySelector('.league-switch a.active')?.textContent?.trim().toLowerCase() || '';
    const marker = kind === 'recap' ? document.getElementById('graded')?.textContent?.trim() || '' : document.getElementById('count')?.textContent?.trim() || '';
    const ratingsRows = kind === 'ratings' ? [...document.querySelectorAll('#ratingsBody tr')].map(tr => tr.textContent.trim()) : [];
    const matchupRows = kind === 'ratings' ? [...document.querySelectorAll('#matchupsBody tr')].map(tr => tr.textContent.trim()) : [];
    const matchupCount = kind === 'ratings' ? document.getElementById('matchupCount')?.textContent?.trim() || '' : '';
    const marketNotice = kind === 'ratings' ? document.getElementById('marketNotice')?.textContent?.trim() || '' : '';
    return {
      title: document.title,
      activeLeague,
      marker,
      matchupCount,
      navDisplay: nav ? getComputedStyle(nav).display : '',
      navOverflowX: nav ? getComputedStyle(nav).overflowX : '',
      topbarHeight: topbar?.height || 0,
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      ratingsRowCount: ratingsRows.length,
      matchupRowCount: matchupRows.length,
      firstRatingRow: ratingsRows[0] || '',
      lastRatingRow: ratingsRows.at(-1) || '',
      firstMatchupRow: matchupRows[0] || '',
      marketNotice,
      tableWraps: [...document.querySelectorAll('.table-wrap')].map(el => ({ scrollWidth: el.scrollWidth, clientWidth: el.clientWidth, overflowX: getComputedStyle(el).overflowX }))
    };
  }, { kind: tc.page });

  if (state.activeLeague !== tc.league) errors.push(`league switch state mismatch: expected ${tc.league}, got ${state.activeLeague}`);
  if (state.scrollWidth > state.clientWidth + 2) errors.push(`document horizontal overflow ${state.scrollWidth} > ${state.clientWidth}`);
  if (!state.marker || /^—$|loading/i.test(state.marker)) errors.push(`${tc.page} data did not hydrate: ${state.marker}`);
  if (mobile && state.navDisplay === 'none') errors.push('mobile audit-page navigation is hidden');
  if (mobile && !['auto', 'scroll'].includes(state.navOverflowX)) errors.push(`mobile audit nav should scroll horizontally when needed, got ${state.navOverflowX}`);
  if (mobile && state.topbarHeight > 132) errors.push(`mobile audit topbar unexpectedly tall: ${state.topbarHeight}`);
  for (const wrap of state.tableWraps) {
    if (wrap.scrollWidth > wrap.clientWidth + 2 && !['auto', 'scroll'].includes(wrap.overflowX)) errors.push(`wide table is not contained by scroll wrapper: ${JSON.stringify(wrap)}`);
  }

  if (tc.page === 'ratings') {
    const expected = expectedRatings[tc.league];
    if (state.ratingsRowCount !== expected.teams) errors.push(`ratings row count mismatch: expected ${expected.teams}, got ${state.ratingsRowCount}`);
    if (state.matchupRowCount !== expected.renderedMatchupRows) errors.push(`matchup row count mismatch: expected ${expected.renderedMatchupRows} rendered rows for ${expected.matchups} comparisons, got ${state.matchupRowCount}`);
    if (!state.matchupCount.includes(`${expected.matchups} current comparisons`)) errors.push(`matchup summary mismatch: expected ${expected.matchups}, got ${state.matchupCount}`);
    if (!state.firstRatingRow || /loading|unavailable|error/i.test(state.firstRatingRow)) errors.push(`first ranking row invalid: ${state.firstRatingRow}`);
    if (!state.lastRatingRow || /loading|unavailable|error/i.test(state.lastRatingRow)) errors.push(`last ranking row invalid: ${state.lastRatingRow}`);
    if (expected.topTeam && !state.firstRatingRow.toLowerCase().includes(expected.topTeam.toLowerCase())) errors.push(`snapshot No. 1 mismatch: expected ${expected.topTeam}, got: ${state.firstRatingRow}`);
    if (expected.matchups === 0 && !/await|current-week comparisons/i.test(state.firstMatchupRow)) errors.push(`zero-comparison placeholder missing: ${state.firstMatchupRow}`);
    if (!/WITHHELD DISCONNECTED MARKET GRAPH/i.test(state.marketNotice)) errors.push(`market safeguard not visible: ${state.marketNotice}`);
  }

  const navLink = page.locator(`.page-nav a[href="${tc.marker}"]`).first();
  if (await navLink.count()) {
    await navLink.click();
    await page.waitForTimeout(100);
    const hash = await page.evaluate(() => location.hash);
    if (hash !== tc.marker) errors.push(`in-page navigation did not reach ${tc.marker}: ${hash}`);
  }

  report.push({ ...tc, expected: tc.page === 'ratings' ? expectedRatings[tc.league] : null, state, failedRequests, errors });
  if (failedRequests.length || errors.length) failed = true;
  await page.close();
}

await browser.close();
console.log(JSON.stringify(report, null, 2));
if (failed) process.exit(1);
