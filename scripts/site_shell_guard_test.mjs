import { webkit } from 'playwright';

const base = process.env.SITE_BASE_URL || 'http://127.0.0.1:8000';
const cases = [
  { name: 'cfb-laptop', path: '/', league: 'cfb', width: 1348 },
  { name: 'nfl-laptop', path: '/?league=nfl', league: 'nfl', width: 1348 },
  { name: 'cfb-320', path: '/', league: 'cfb', width: 320 },
  { name: 'nfl-320', path: '/?league=nfl', league: 'nfl', width: 320 },
  { name: 'cfb-390', path: '/', league: 'cfb', width: 390 },
  { name: 'nfl-390', path: '/?league=nfl', league: 'nfl', width: 390 },
  { name: 'cfb-tablet', path: '/', league: 'cfb', width: 1024 },
  { name: 'nfl-tablet', path: '/?league=nfl', league: 'nfl', width: 1024 },
  { name: 'cfb-desktop', path: '/', league: 'cfb', width: 1440 },
  { name: 'nfl-desktop', path: '/?league=nfl', league: 'nfl', width: 1440 }
];

const browser = await webkit.launch({ headless: true });
const report = [];
let failed = false;

for (const tc of cases) {
  const compact = tc.width <= 1400;
  const page = await browser.newPage({ viewport: { width: tc.width, height: 844 }, isMobile: compact, hasTouch: compact });
  const errors = [];
  const failedRequests = [];
  page.on('pageerror', err => errors.push(`pageerror: ${err.message}`));
  page.on('requestfailed', req => failedRequests.push(`${req.method()} ${req.url()} :: ${req.failure()?.errorText || 'failed'}`));
  page.on('response', res => { if (res.status() >= 400) failedRequests.push(`HTTP ${res.status()} ${res.url()}`); });

  const response = await page.goto(`${base}${tc.path}`, { waitUntil: 'networkidle', timeout: 30000 });
  if (!response || !response.ok()) errors.push(`page load failed: ${response?.status() ?? 'no response'}`);
  await page.waitForFunction(() => document.body.classList.contains('site-v2') && document.getElementById('leagueSwitch'), { timeout: 15000 }).catch(() => {});

  const initial = await page.evaluate(() => {
    const header = document.querySelector('.site-header')?.getBoundingClientRect();
    const nav = document.querySelector('.primary-nav');
    const toggle = document.getElementById('cbMobileNavToggle');
    const pressed = [...document.querySelectorAll('#leagueSwitch button')].filter(b => b.getAttribute('aria-pressed') === 'true').map(b => b.dataset.league);
    const controls = ['.brand', '#cbMobileNavToggle', '#leagueSwitch', '#themeToggle']
      .map(selector => ({ selector, el: document.querySelector(selector) }))
      .filter(x => x.el)
      .map(x => {
        const r = x.el.getBoundingClientRect();
        return { selector: x.selector, left: r.left, right: r.right, top: r.top, bottom: r.bottom, display: getComputedStyle(x.el).display };
      });
    const vw = document.documentElement.clientWidth;
    const overflowOffenders = [...document.querySelectorAll('body *')].map((el, index) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return {
        index,
        tag: el.tagName.toLowerCase(),
        id: el.id || '',
        className: typeof el.className === 'string' ? el.className : '',
        left: Math.round(r.left * 10) / 10,
        right: Math.round(r.right * 10) / 10,
        width: Math.round(r.width * 10) / 10,
        scrollWidth: el.scrollWidth,
        clientWidth: el.clientWidth,
        display: s.display,
        position: s.position,
        minWidth: s.minWidth,
        maxWidth: s.maxWidth,
        widthCss: s.width,
        overflowX: s.overflowX,
        whiteSpace: s.whiteSpace
      };
    }).filter(x => x.display !== 'none' && (x.right > vw + 2 || x.left < -2))
      .sort((a,b) => Math.max(b.right - vw, -b.left) - Math.max(a.right - vw, -a.left))
      .slice(0, 30);
    return {
      league: document.documentElement.dataset.league || '',
      header: header && { top: header.top, bottom: header.bottom, height: header.height },
      navDisplay: nav ? getComputedStyle(nav).display : '',
      navOpen: document.body.dataset.navOpen || '',
      navAriaHidden: nav?.getAttribute('aria-hidden') ?? null,
      toggleExpanded: toggle?.getAttribute('aria-expanded') ?? null,
      toggleDisplay: toggle ? getComputedStyle(toggle).display : '',
      htmlScrollWidth: document.documentElement.scrollWidth,
      htmlClientWidth: document.documentElement.clientWidth,
      bodyScrollWidth: document.body.scrollWidth,
      bodyClientWidth: document.body.clientWidth,
      pressed,
      controls,
      overflowOffenders
    };
  });

  if (initial.league !== tc.league) errors.push(`expected league ${tc.league}, got ${initial.league}`);
  if (initial.htmlScrollWidth > initial.htmlClientWidth + 2) errors.push(`horizontal html overflow ${initial.htmlScrollWidth} > ${initial.htmlClientWidth}; offenders=${JSON.stringify(initial.overflowOffenders)}`);
  if (initial.bodyScrollWidth > initial.bodyClientWidth + 2) errors.push(`horizontal body overflow ${initial.bodyScrollWidth} > ${initial.bodyClientWidth}; offenders=${JSON.stringify(initial.overflowOffenders)}`);
  if (initial.pressed.length !== 1 || initial.pressed[0] !== tc.league) errors.push(`league switch state mismatch: ${JSON.stringify(initial.pressed)}`);
  if (!initial.header || initial.header.height > 82) errors.push(`header wrapped or too tall: ${JSON.stringify(initial.header)}`);
  for (const control of initial.controls) {
    if (control.display !== 'none' && (control.left < -1 || control.right > initial.htmlClientWidth + 1)) errors.push(`control outside viewport: ${JSON.stringify(control)}`);
    if (control.display !== 'none' && initial.header && (control.top < initial.header.top - 1 || control.bottom > initial.header.bottom + 1)) errors.push(`control outside header bounds: ${JSON.stringify(control)}`);
  }

  let opened = null;
  let escaped = null;
  if (compact) {
    if (initial.navDisplay !== 'none') errors.push(`compact nav should start collapsed, got ${initial.navDisplay}`);
    if (initial.toggleDisplay === 'none') errors.push('compact nav toggle is hidden');

    const toggle = page.locator('#cbMobileNavToggle');
    await toggle.click();
    await page.waitForTimeout(120);
    opened = await page.evaluate(() => ({
      open: document.body.dataset.navOpen,
      display: getComputedStyle(document.querySelector('.primary-nav')).display,
      expanded: document.getElementById('cbMobileNavToggle')?.getAttribute('aria-expanded'),
      hidden: document.querySelector('.primary-nav')?.getAttribute('aria-hidden'),
      bodyOverflow: getComputedStyle(document.body).overflow,
      navRect: (() => { const r=document.querySelector('.primary-nav')?.getBoundingClientRect(); return r && {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height}; })()
    }));
    if (opened.open !== 'true' || opened.display === 'none' || opened.expanded !== 'true' || opened.hidden !== 'false') errors.push(`nav open state invalid after 120ms: ${JSON.stringify(opened)}`);
    if (opened.bodyOverflow !== 'hidden') errors.push(`background scroll not locked while menu open: ${opened.bodyOverflow}`);

    await page.keyboard.press('Escape');
    await page.waitForTimeout(120);
    escaped = await page.evaluate(() => ({
      open: document.body.dataset.navOpen,
      display: getComputedStyle(document.querySelector('.primary-nav')).display,
      expanded: document.getElementById('cbMobileNavToggle')?.getAttribute('aria-expanded'),
      hidden: document.querySelector('.primary-nav')?.getAttribute('aria-hidden'),
      active: document.activeElement?.id || ''
    }));
    if (escaped.open === 'true' || escaped.display !== 'none' || escaped.expanded !== 'false' || escaped.hidden !== 'true') errors.push(`Escape did not close menu cleanly: ${JSON.stringify(escaped)}`);
    if (escaped.active !== 'cbMobileNavToggle') errors.push(`Escape did not return focus to menu toggle: ${escaped.active}`);

    await toggle.click();
    await page.waitForTimeout(80);
    await page.locator('#home').click({ position: { x: 10, y: 10 }, force: true });
    await page.waitForTimeout(120);
    const outside = await page.evaluate(() => document.body.dataset.navOpen);
    if (outside === 'true') errors.push('outside click did not close compact navigation');
  } else {
    if (initial.navDisplay === 'none') errors.push('desktop primary navigation is hidden');
    if (initial.toggleDisplay !== 'none') errors.push(`desktop nav toggle should be hidden, got ${initial.toggleDisplay}`);
  }

  const item = { ...tc, compact, initial, opened, escaped, failedRequests, errors };
  report.push(item);
  if (failedRequests.length || errors.length) {
    failed = true;
    console.error(`\nSHELL_GUARD_FAILURE ${tc.name}\n${JSON.stringify(item, null, 2)}\n`);
  } else {
    console.log(`SHELL_GUARD_PASS ${tc.name}`);
  }
  await page.close();
}

await browser.close();
console.log(JSON.stringify(report, null, 2));
if (failed) process.exit(1);
