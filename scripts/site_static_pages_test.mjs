import { webkit } from 'playwright';

const base = process.env.SITE_BASE_URL || 'http://127.0.0.1:8000';
const pages = [
  { page: 'recap', path: '/recap.html', marker: '#performance' },
  { page: 'ratings', path: '/ratings.html', marker: '#ratings' }
];
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

  await page.waitForFunction(({ kind }) => {
    if (kind === 'recap') return document.getElementById('graded')?.textContent?.trim() !== '—';
    return !/loading/i.test(document.getElementById('count')?.textContent || 'Loading');
  }, { kind: tc.page }, { timeout: 15000 }).catch(() => {});

  const state = await page.evaluate(({ kind }) => {
    const nav = document.querySelector('.page-nav');
    const topbar = document.querySelector('.topbar')?.getBoundingClientRect();
    const activeLeague = document.querySelector('.league-switch a.active')?.textContent?.trim().toLowerCase() || '';
    const marker = kind === 'recap' ? document.getElementById('graded')?.textContent?.trim() || '' : document.getElementById('count')?.textContent?.trim() || '';
    return {
      title: document.title,
      activeLeague,
      marker,
      navDisplay: nav ? getComputedStyle(nav).display : '',
      navOverflowX: nav ? getComputedStyle(nav).overflowX : '',
      topbarHeight: topbar?.height || 0,
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
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

  const navLink = page.locator(`.page-nav a[href="${tc.marker}"]`).first();
  if (await navLink.count()) {
    await navLink.click();
    await page.waitForTimeout(100);
    const hash = await page.evaluate(() => location.hash);
    if (hash !== tc.marker) errors.push(`in-page navigation did not reach ${tc.marker}: ${hash}`);
  }

  report.push({ ...tc, state, failedRequests, errors });
  if (failedRequests.length || errors.length) failed = true;
  await page.close();
}

await browser.close();
console.log(JSON.stringify(report, null, 2));
if (failed) process.exit(1);
