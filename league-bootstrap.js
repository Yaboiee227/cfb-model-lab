(() => {
  const VALID = new Set(['cfb', 'nfl']);
  const params = new URL(location.href).searchParams;
  const requested = String(params.get('league') || '').toLowerCase();
  let league = VALID.has(requested) ? requested : String(localStorage.getItem('cb-active-league') || 'cfb').toLowerCase();
  if (!VALID.has(league)) league = 'cfb';

  window.CB_ACTIVE_LEAGUE = league;
  localStorage.setItem('cb-active-league', league);
  document.documentElement.dataset.league = league;

  const nativeFetch = window.fetch.bind(window);
  const NFL_FILES = new Set(['config.json', 'projections.csv', 'results.csv', 'research.json']);

  window.fetch = function(input, init) {
    if (window.CB_ACTIVE_LEAGUE !== 'nfl' || typeof input !== 'string') return nativeFetch(input, init);
    const clean = input.replace(/^\.\//, '');
    if (clean.startsWith('data/')) {
      const file = clean.slice('data/'.length);
      if (NFL_FILES.has(file)) return nativeFetch(`nfl_data/site/${file}`, init);
    }
    return nativeFetch(input, init);
  };

  function switchLeague(next) {
    if (!VALID.has(next) || next === window.CB_ACTIVE_LEAGUE) return;
    localStorage.setItem('cb-active-league', next);
    const url = new URL(location.href);
    if (next === 'cfb') url.searchParams.delete('league');
    else url.searchParams.set('league', next);
    url.searchParams.delete('game');
    location.href = url.toString();
  }

  function ensureStyle() {
    if (document.getElementById('leagueBootstrapStyle')) return;
    const style = document.createElement('style');
    style.id = 'leagueBootstrapStyle';
    style.textContent = `
      .league-switch{display:flex;align-items:center;gap:3px;padding:3px;border:1px solid rgba(143,240,203,.2);border-radius:10px;background:rgba(7,17,31,.44);margin-left:auto}
      .league-switch button{border:0;background:transparent;color:var(--muted,#9fb1c4);font:800 10px/1 system-ui;letter-spacing:.08em;padding:9px 10px;border-radius:7px;cursor:pointer}
      .league-switch button[aria-pressed="true"]{background:var(--accent,#8ff0cb);color:#07111f}
      .league-switch button:focus-visible{outline:2px solid var(--accent,#8ff0cb);outline-offset:2px}
      html[data-league="nfl"] .alt-target-box,
      html[data-league="nfl"] .alt-analysis-card{display:none!important}
      html[data-league="nfl"] .conference-filter-hidden{display:none!important}
      .nfl-policy-note{margin-top:8px;font-size:10px;line-height:1.45;color:var(--muted,#9fb1c4)}
      @media(max-width:860px){.league-switch{order:3;margin-left:0}.header-inner{flex-wrap:wrap}.primary-nav{order:4;width:100%}}
    `;
    document.head.appendChild(style);
  }

  function ensureSwitch() {
    const header = document.querySelector('.header-inner');
    if (!header || document.getElementById('leagueSwitch')) return;
    const wrap = document.createElement('div');
    wrap.className = 'league-switch';
    wrap.id = 'leagueSwitch';
    wrap.setAttribute('role', 'group');
    wrap.setAttribute('aria-label', 'Prediction league');
    wrap.innerHTML = `
      <button type="button" data-league="cfb" aria-pressed="${league === 'cfb'}">CFB</button>
      <button type="button" data-league="nfl" aria-pressed="${league === 'nfl'}">NFL</button>`;
    wrap.addEventListener('click', event => {
      const button = event.target.closest('button[data-league]');
      if (button) switchLeague(button.dataset.league);
    });
    const theme = document.getElementById('themeToggle');
    theme ? header.insertBefore(wrap, theme) : header.appendChild(wrap);
  }

  function enforceTitle() {
    if (league !== 'nfl') return;
    const desired = 'CB Model Projections | NFL Research';
    if (document.title !== desired) document.title = desired;
  }

  function applyLeagueCopy() {
    document.body?.classList.toggle('league-nfl', league === 'nfl');
    document.body?.classList.toggle('league-cfb', league === 'cfb');
    ensureStyle();
    ensureSwitch();

    if (league !== 'nfl') return;

    const brandSmall = document.querySelector('.brand-copy small');
    if (brandSmall) brandSmall.textContent = 'NFL intelligence';
    const kicker = document.querySelector('.hero-kicker-row .eyebrow');
    if (kicker) kicker.textContent = 'NFL MODEL • WEEKLY COMMAND CENTER';
    const lede = document.querySelector('.hero-lede');
    if (lede) lede.textContent = 'Independent NFL projections for score, spread and total—paired with market comparison, reliability, personnel, weather and transparent validation gates.';
    const search = document.getElementById('teamSearch');
    if (search) search.placeholder = 'Search Bills, Chiefs, Steelers…';

    const labels = [...document.querySelectorAll('.filter-panel label')];
    const conference = labels.find(label => /^Conference$/i.test(label.querySelector('span')?.textContent?.trim() || ''));
    if (conference) conference.classList.add('conference-filter-hidden');

    const metricWin = document.getElementById('metricWinProb')?.parentElement;
    if (metricWin) {
      const label = metricWin.querySelector('span');
      const small = metricWin.querySelector('small');
      if (label) label.textContent = 'Win probability';
      if (small) small.textContent = 'NFL probability layer not yet validated';
    }

    const limits = document.querySelector('.limitations p:last-child');
    if (limits) limits.textContent = 'NFL personnel and quarterback states can change quickly, final inactives arrive close to kickoff, roof and weather decisions can remain open, and historical relationships can weaken out of sample. The site therefore keeps projection, market gap, reliability and release status separate.';

    const about = document.querySelector('#about .about-grid > div:first-child p:last-child');
    if (about) about.textContent = 'CB Model Projections is a shared front end for college football and NFL research. Each league keeps its own model, data, validation evidence and release state while using one consistent interface.';

    const glossary = [...document.querySelectorAll('.glossary-grid article')];
    const moneyline = glossary.find(x => x.querySelector('h3')?.textContent === 'Moneyline');
    if (moneyline) moneyline.querySelector('p').textContent = 'NFL implied moneyline is intentionally not displayed until an NFL-specific win-probability layer is validated.';
    const winProb = glossary.find(x => x.querySelector('h3')?.textContent === 'Win probability');
    if (winProb) winProb.querySelector('p').textContent = 'The NFL win-probability layer remains withheld while it is unvalidated; blank probability fields are intentional, not missing estimates.';
    const dataQuality = glossary.find(x => x.querySelector('h3')?.textContent === 'Data quality');
    if (dataQuality) dataQuality.querySelector('p').textContent = 'NFL reliability grades summarize model/data uncertainty and game-state risk. They do not imply a betting recommendation.';

    const projectionRules = document.querySelector('.projection-rules');
    if (projectionRules && !projectionRules.querySelector('.nfl-policy-note')) {
      const p = document.createElement('p');
      p.className = 'nfl-policy-note';
      p.textContent = 'NFL alternative-line recommendations and wager thresholds remain locked until prospective calibration earns them. Model/market gaps shown here are descriptive research only.';
      projectionRules.appendChild(p);
    }

    const support = document.getElementById('venmoLink');
    if (support && (!support.getAttribute('href') || support.getAttribute('href').includes('undefined'))) {
      support.href = 'https://venmo.com/u/Kaleb_InThe_Cut';
    }
    enforceTitle();
  }

  const titleEl = document.querySelector('title');
  if (titleEl && league === 'nfl') {
    new MutationObserver(enforceTitle).observe(titleEl, { childList: true, characterData: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      applyLeagueCopy();
      setTimeout(applyLeagueCopy, 250);
      setTimeout(applyLeagueCopy, 1000);
    }, { once: true });
  } else {
    applyLeagueCopy();
  }
})();
