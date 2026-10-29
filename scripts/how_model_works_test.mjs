import { webkit } from 'playwright';

const base = process.env.SITE_BASE_URL || 'http://127.0.0.1:8000';
const widths = [390, 1440];
const browser = await webkit.launch({ headless: true });
const report = [];
let failed = false;

for (const width of widths) {
  const mobile = width < 900;
  const page = await browser.newPage({ viewport: { width, height: 844 }, isMobile: mobile, hasTouch: mobile });
  const errors = [];
  const failedRequests = [];
  page.on('pageerror', err => errors.push(`pageerror: ${err.message}`));
  page.on('requestfailed', req => failedRequests.push(`${req.method()} ${req.url()} :: ${req.failure()?.errorText || 'failed'}`));
  page.on('response', res => { if (res.status() >= 400) failedRequests.push(`HTTP ${res.status()} ${res.url()}`); });

  const response = await page.goto(`${base}/how-it-works.html`, { waitUntil: 'networkidle', timeout: 30000 });
  if (!response || !response.ok()) errors.push(`page load failed: ${response?.status() ?? 'no response'}`);

  const state = await page.evaluate(() => {
    const nav = document.querySelector('.page-nav');
    const topbar = document.querySelector('.topbar')?.getBoundingClientRect();
    const text = document.body.innerText;
    return {
      title: document.title,
      h1: document.querySelector('h1')?.textContent?.trim() || '',
      sectionIds: [...document.querySelectorAll('main section[id]')].map(el => el.id),
      navDisplay: nav ? getComputedStyle(nav).display : '',
      navOverflowX: nav ? getComputedStyle(nav).overflowX : '',
      topbarHeight: topbar?.height || 0,
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      text,
      tableWraps: [...document.querySelectorAll('.input-table-wrap')].map(el => ({ scrollWidth: el.scrollWidth, clientWidth: el.clientWidth, overflowX: getComputedStyle(el).overflowX }))
    };
  });

  const required = [
    'two predictive systems',
    'collect pregame information broadly',
    'marketSpreadHome − modelSpreadHome',
    'modelTotal − marketTotal',
    'They are not ATS cover probabilities',
    'Games remain pending until the result is Final',
    'No postgame reconstruction',
    'Explicit promotion'
  ];
  for (const phrase of required) {
    if (!state.text.includes(phrase)) errors.push(`required guide language missing: ${phrase}`);
  }
  if (!/How the Model Works/.test(state.title)) errors.push(`unexpected title: ${state.title}`);
  for (const id of ['overview','inputs','production','reading','grading','validation']) {
    if (!state.sectionIds.includes(id)) errors.push(`missing section #${id}`);
  }
  if (state.scrollWidth > state.clientWidth + 2) errors.push(`document horizontal overflow ${state.scrollWidth} > ${state.clientWidth}`);
  if (mobile && state.navDisplay === 'none') errors.push('mobile page navigation is hidden');
  if (mobile && !['auto','scroll'].includes(state.navOverflowX)) errors.push(`mobile nav should scroll horizontally, got ${state.navOverflowX}`);
  if (mobile && state.topbarHeight > 132) errors.push(`mobile topbar unexpectedly tall: ${state.topbarHeight}`);
  for (const wrap of state.tableWraps) {
    if (wrap.scrollWidth > wrap.clientWidth + 2 && !['auto','scroll'].includes(wrap.overflowX)) errors.push(`input table is not contained: ${JSON.stringify(wrap)}`);
  }

  const gradingLink = page.locator('.page-nav a[href="#grading"]').first();
  if (await gradingLink.count()) {
    await gradingLink.click();
    await page.waitForTimeout(100);
    const hash = await page.evaluate(() => location.hash);
    if (hash !== '#grading') errors.push(`grading navigation failed: ${hash}`);
  }

  report.push({ width, state: { ...state, text: undefined }, failedRequests, errors });
  if (failedRequests.length || errors.length) failed = true;
  await page.close();
}

await browser.close();
console.log(JSON.stringify(report, null, 2));
if (failed) process.exit(1);
