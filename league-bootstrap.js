(() => {
  const VALID = new Set(['cfb', 'nfl']);
  const params = new URL(location.href).searchParams;
  const requested = String(params.get('league') || '').toLowerCase();
  let league = VALID.has(requested) ? requested : String(localStorage.getItem('cb-active-league') || 'cfb').toLowerCase();
  if (!VALID.has(league)) league = 'cfb';

  window.CB_ACTIVE_LEAGUE = league;
  localStorage.setItem('cb-active-league', league);
  document.documentElement.dataset.league = league;

  // The legacy CFB application stores bookmarks under cb-bookmarks. In NFL mode,
  // transparently redirect only that key so CFB and NFL game IDs never mix.
  if (league === 'nfl' && !window.__CB_NFL_BOOKMARK_STORAGE_PATCHED) {
    window.__CB_NFL_BOOKMARK_STORAGE_PATCHED = true;
    const nativeGetItem = Storage.prototype.getItem;
    const nativeSetItem = Storage.prototype.setItem;
    const nativeRemoveItem = Storage.prototype.removeItem;
    const remap = key => key === 'cb-bookmarks' ? 'cb-bookmarks-nfl' : key;
    Storage.prototype.getItem = function(key) {
      return nativeGetItem.call(this, this === localStorage ? remap(key) : key);
    };
    Storage.prototype.setItem = function(key, value) {
      return nativeSetItem.call(this, this === localStorage ? remap(key) : key, value);
    };
    Storage.prototype.removeItem = function(key) {
      return nativeRemoveItem.call(this, this === localStorage ? remap(key) : key);
    };
  }

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
      html[data-league="nfl"] .alt-analysis-card,
      html[data-league="nfl"] .conference-filter-hidden,
      html[data-league="nfl"] .conference-panel{display:none!important}
      .nfl-policy-note{margin-top:8px;font-size:10px;line-height:1.45;color:var(--muted,#9fb1c4)}
      .nfl-validation-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:12px;padding-top:12px;border-top:1px solid var(--line,rgba(255,255,255,.12))}
      .nfl-validation-strip div{padding:8px 10px;border:1px solid var(--line,rgba(255,255,255,.12));border-radius:9px;background:rgba(127,127,127,.04)}
      .nfl-validation-strip span{display:block;font-size:9px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--muted,#9fb1c4)}
      .nfl-validation-strip strong{display:block;margin-top:3px;font-size:12px;color:var(--text,#fff)}
      .nfl-card-context{margin-top:10px;padding:9px 10px;border:1px solid var(--line,rgba(255,255,255,.12));border-radius:9px;font-size:10px;line-height:1.5;color:var(--muted,#9fb1c4)}
      .nfl-card-context strong{color:var(--text,#fff)}
      @media(max-width:860px){.league-switch{order:3;margin-left:0}.header-inner{flex-wrap:wrap}.primary-nav{order:4;width:100%}.nfl-validation-strip{grid-template-columns:1fr}}
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

  function setText(selector, text) {
    const el = document.querySelector(selector);
    if (el) el.textContent = text;
  }

  function setMeta(selector, value) {
    const el = document.querySelector(selector);
    if (el) el.setAttribute('content', value);
  }

  function applyNflRecordCopy() {
    setText('#recordTitle', 'Prospective projection audit');
    const intro = document.querySelector('#record .section-heading p:not(.eyebrow)');
    if (intro) intro.textContent = 'Grades frozen NFL projection direction against the tracked market benchmark. This is a research audit, not a wager ledger or released-bet record.';
    const cards = document.querySelectorAll('#record .record-card');
    if (cards[0]) {
      setText('#record .record-card.featured .record-card-head span', 'Market direction');
      setText('#record .record-card.featured .record-card-head small', 'Spread benchmark');
    }
    const chartTitle = document.querySelector('#record .chart-panel h3');
    if (chartTitle) chartTitle.textContent = 'Spread benchmark cumulative direction';
    const chartTag = document.querySelector('#record .chart-panel .panel-head > span');
    if (chartTag) chartTag.textContent = 'projection audit';
    const weeklyHeaders = document.querySelectorAll('#weeklyRecordBody')?.[0]?.closest('table')?.querySelectorAll('thead th') || [];
    if (weeklyHeaders.length >= 5) {
      weeklyHeaders[1].textContent = 'Spread';
      weeklyHeaders[2].textContent = 'Spread %';
    }
  }

  function applyNflMethodologyCopy() {
    const cards = [...document.querySelectorAll('#methodology .method-card')];
    const copy = [
      ['Build pregame team strength', 'EPA, success rate, passing/rushing matchups, explosiveness, sacks, neutral pass tendency and rest are built strictly from information available before kickoff, with early-season shrinkage toward prior information.'],
      ['Add validated defensive context', 'Opponent and defensive coverage information is included only where leakage-safe testing supported it. Recursive win Elo and margin rating use prior completed games only.'],
      ['Project spread and total separately', 'The spread uses the validated canonical stack. The total remains a deliberately simpler frozen core because pace, red-zone and other additions did not earn robust promotion.'],
      ['Gate live game context', 'Starting QB, injuries, final inactives, weather and roof state can change reliability or HOLD status. They do not receive discretionary point adjustments.'],
      ['Compare with a timestamped market', 'The independent model is compared with a public sportsbook benchmark. The numerical difference is descriptive research, not automatically expected value or a released edge.'],
      ['Validate prospectively', 'Immutable weekly snapshots are graded after games finish. Recommendation thresholds remain locked until enough prospectively frozen games and weeks accumulate for explicit review.']
    ];
    cards.forEach((card, i) => {
      if (!copy[i]) return;
      const h = card.querySelector('h3');
      const p = card.querySelector('p');
      if (h) h.textContent = copy[i][0];
      if (p) p.textContent = copy[i][1];
    });
  }

  function applyNflGlossaryCopy() {
    const glossary = [...document.querySelectorAll('.glossary-grid article')];
    const find = name => glossary.find(x => x.querySelector('h3')?.textContent === name);
    const ats = find('ATS');
    if (ats) ats.querySelector('p').textContent = 'Against the spread benchmark grading. On the NFL research page this records model direction versus a tracked line; it is not a released-bet record.';
    const moneyline = find('Moneyline');
    if (moneyline) moneyline.querySelector('p').textContent = 'NFL model-implied moneyline is a mathematical translation of the validated research win probability. It is not a validated moneyline edge or wager recommendation.';
    const winProb = find('Win probability');
    if (winProb) winProb.querySelector('p').textContent = 'NFL home-win probability is walk-forward calibrated from the canonical projected margin. It is approved for research display only and does not authorize moneyline betting, sizing or confidence tiers.';
    const gap = find('Model / market gap');
    if (gap) {
      gap.querySelector('h3').textContent = 'Model / market difference';
      gap.querySelector('p').textContent = 'The numerical difference between the frozen canonical model and a timestamped market benchmark. Larger does not automatically mean more valuable.';
    }
    const dataQuality = find('Data quality');
    if (dataQuality) {
      dataQuality.querySelector('h3').textContent = 'Reliability';
      dataQuality.querySelector('p').textContent = 'NFL reliability grades summarize model-domain and live-context uncertainty. They are not cover probabilities or betting-confidence tiers.';
    }
  }

  async function ensureValidationStrip() {
    if (league !== 'nfl') return;
    const host = document.querySelector('.command-center');
    if (!host || host.querySelector('.nfl-validation-strip')) return;
    try {
      const response = await fetch('data/config.json', { cache: 'no-store' });
      if (!response.ok) return;
      const cfg = await response.json();
      const strip = document.createElement('div');
      strip.className = 'nfl-validation-strip';
      strip.innerHTML = `
        <div><span>Historical validation</span><strong>816 OOS games</strong></div>
        <div><span>Prospective sample</span><strong>${Number(cfg.completedProspectiveGames || 0)} games · ${Number(cfg.prospectiveWeeks || 0)} week${Number(cfg.prospectiveWeeks || 0) === 1 ? '' : 's'}</strong></div>
        <div><span>Recommendation state</span><strong>HOLD</strong></div>`;
      host.appendChild(strip);
    } catch (_) {}
  }

  function decorateNflProjectionCards() {
    if (league !== 'nfl') return;
    let games;
    try { games = STATE?.filtered || STATE?.projections || []; } catch (_) { return; }
    for (const game of games) {
      const reliability = `${String(game.spreadReliability || '').slice(0,1) || '—'}/${String(game.totalReliability || '').slice(0,1) || '—'}`;
      for (const node of [document.getElementById(`game-${game.gameId}`), document.getElementById(`card-${game.gameId}`)]) {
        if (!node) continue;
        node.querySelectorAll('.data-badge').forEach(badge => {
          badge.textContent = reliability;
          badge.title = `Spread/total reliability ${reliability}. Reliability is not betting confidence.`;
        });
      }
      const card = document.getElementById(`card-${game.gameId}`);
      if (card && !card.querySelector('.nfl-card-context')) {
        const shadow = Number(game.shadowModelSpreadHome);
        const shadowText = Number.isFinite(shadow) ? ` · Shadow challenger ${shadow > 0 ? '+' : ''}${shadow.toFixed(1)}` : '';
        const context = document.createElement('div');
        context.className = 'nfl-card-context';
        context.innerHTML = `<strong>Reliability ${reliability}</strong> · ${game.hardQbStateBreak === 'true' || game.hardQbStateBreak === true ? 'Hard QB break · ' : ''}${String(game.releaseStatus || 'HOLD').replaceAll('_',' ')}${shadowText}<br>${String(game.weatherRoofState || '').replaceAll('_',' ')}${game.executionVerified ? ' · executable price verified' : ' · public market benchmark only'}`;
        card.appendChild(context);
      }
    }
  }

  function installProjectionObserver() {
    if (league !== 'nfl' || window.__CB_NFL_PROJECTION_OBSERVER) return;
    const cards = document.getElementById('projectionCards');
    if (!cards) return;
    window.__CB_NFL_PROJECTION_OBSERVER = new MutationObserver(() => decorateNflProjectionCards());
    window.__CB_NFL_PROJECTION_OBSERVER.observe(cards, { childList: true });
    decorateNflProjectionCards();
  }

  function installNflCsvExport() {
    if (league !== 'nfl' || window.__CB_NFL_EXPORT_INSTALLED) return;
    const button = document.getElementById('exportCsv');
    if (!button) return;
    window.__CB_NFL_EXPORT_INSTALLED = true;
    button.addEventListener('click', event => {
      event.preventDefault();
      event.stopImmediatePropagation();
      let rows = [];
      try { rows = STATE?.filtered || []; } catch (_) {}
      const columns = ['league','season','week','date','kickoffET','gameId','awayTeam','homeTeam','projectedAwayPoints','projectedHomePoints','modelSpreadHome','modelTotal','homeWinProbability','awayWinProbability','marketSpreadHome','marketTotal','marketSource','marketObservedAt','executionVerified','shadowModelSpreadHome','spreadReliability','totalReliability','personnelState','hardQbStateBreak','weatherRoofState','weatherElevatedUncertainty','finalInactivesResolved','releaseStatus','releaseBlockers','preferredArchitecture','winProbabilityState','websitePublishAllowed'];
      const quote = value => {
        const s = String(value ?? '');
        return /[",\n]/.test(s) ? `"${s.replace(/"/g,'""')}"` : s;
      };
      const csv = [columns.join(','), ...rows.map(row => columns.map(key => quote(row[key])).join(','))].join('\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      const week = document.getElementById('weekFilter')?.value || 'all';
      a.download = `cb-model-projections-nfl-week-${week}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    }, true);
  }

  function applyLeagueCopy() {
    document.body?.classList.toggle('league-nfl', league === 'nfl');
    document.body?.classList.toggle('league-cfb', league === 'cfb');
    ensureStyle();
    ensureSwitch();
    if (league !== 'nfl') return;

    setMeta('meta[name="description"]', 'CB Model Projections NFL research: independent spread, total and score projections with market benchmarks, reliability gates and transparent validation.');
    setMeta('meta[property="og:description"]', 'Independent NFL projections with market comparison, reliability, personnel/weather context and transparent validation gates.');
    const brandSmall = document.querySelector('.brand-copy small');
    if (brandSmall) brandSmall.textContent = 'NFL intelligence';
    const kicker = document.querySelector('.hero-kicker-row .eyebrow');
    if (kicker) kicker.textContent = 'NFL MODEL • WEEKLY COMMAND CENTER';
    const lede = document.querySelector('.hero-lede');
    if (lede) lede.textContent = 'Independent NFL projections for score, spread and total—paired with calibrated research win probability, market comparison, reliability, personnel, weather and transparent validation gates.';
    const search = document.getElementById('teamSearch');
    if (search) search.placeholder = 'Search Bills, Chiefs, Steelers…';

    const labels = [...document.querySelectorAll('.filter-panel label')];
    const conference = labels.find(label => /^Conference$/i.test(label.querySelector('span')?.textContent?.trim() || ''));
    if (conference) conference.classList.add('conference-filter-hidden');
    const sort = document.getElementById('sortFilter');
    if (sort) {
      const spread = [...sort.options].find(o => o.value === 'spreadgap');
      const total = [...sort.options].find(o => o.value === 'totalgap');
      if (spread) spread.textContent = 'Spread difference';
      if (total) total.textContent = 'Total difference';
    }
    const headers = document.querySelectorAll('.projection-table thead th');
    if (headers.length >= 5) headers[4].textContent = 'Spread difference';

    const metricWin = document.getElementById('metricWinProb')?.parentElement;
    if (metricWin) {
      const label = metricWin.querySelector('span');
      const small = metricWin.querySelector('small');
      if (label) label.textContent = 'Highest win probability';
      if (small) small.textContent = 'Walk-forward calibrated from canonical margin · research only';
    }

    setText('#research .section-heading h2', 'NFL research hub');
    const researchIntro = document.querySelector('#research .section-heading p:not(.eyebrow)');
    if (researchIntro) researchIntro.textContent = 'QB/personnel, official inactives, weather/roof, market snapshots, efficiency and prospective validation—kept separate from the frozen numerical projection.';

    const limits = document.querySelector('.limitations p:last-child');
    if (limits) limits.textContent = 'NFL personnel and quarterback states can change quickly, final inactives arrive close to kickoff, roof and weather decisions can remain open, and historical relationships can weaken out of sample. Win probability is calibrated from the canonical margin but inherits the same matchup uncertainty and release gates.';

    const about = document.querySelector('#about .about-grid > div:first-child p:last-child');
    if (about) about.textContent = 'CB Model Projections is a shared front end for college football and NFL research. Each league keeps its own model, data, validation evidence, bookmarks and release state while using one consistent interface.';

    applyNflRecordCopy();
    applyNflMethodologyCopy();
    applyNflGlossaryCopy();

    const projectionRules = document.querySelector('.projection-rules');
    if (projectionRules && !projectionRules.querySelector('.nfl-policy-note')) {
      const p = document.createElement('p');
      p.className = 'nfl-policy-note';
      p.textContent = 'NFL alternative-line recommendations, moneyline edge, wager thresholds and sizing remain locked until prospective calibration earns them. Model/market differences and win probability are descriptive research outputs.';
      projectionRules.appendChild(p);
    }

    const support = document.getElementById('venmoLink');
    if (support && (!support.getAttribute('href') || support.getAttribute('href').includes('undefined'))) {
      support.href = 'https://venmo.com/u/Kaleb_InThe_Cut';
    }
    ensureValidationStrip();
    installProjectionObserver();
    installNflCsvExport();
    decorateNflProjectionCards();
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
