(() => {
  if (window.CB_ACTIVE_LEAGUE !== 'nfl') return;

  const TREND_DISCLAIMER = 'Trends are summarized from third-party sources, may contain errors, and are provided for research and entertainment purposes only. Trends describe past results and do not predict future outcomes. Not betting advice.';
  const FULL_DISCLAIMER = 'All content on CB Model Projections is model-generated and provided for research and entertainment purposes only. It is not betting advice and not an official wager recommendation. Past performance does not guarantee future results. Must be 21+ (or the legal age in your jurisdiction). If you or someone you know has a gambling problem, call 1-800-GAMBLER.';
  const DATA_URL = 'nfl_data/site/nfl-trends.json';
  const RESULTS_URL = 'nfl_data/site/nfl-trend-results.json';
  const MOCK_URL = 'nfl_data/templates/nfl-trends-example.json';
  const MOCK_MODE = new URL(location.href).searchParams.get('mockTrends') === '1';
  const VALID_TYPES = new Set(['ATS','SU','TOTAL','SITUATIONAL']);
  const VALID_POINTS = new Set(['home','away','over','under','none']);
  const VALID_TARGETS = new Set(['spread','moneyline','total','none']);
  const TEAM_ALIASES = {JAC:'JAX',LAR:'LA',WSH:'WAS',OAK:'LV',SD:'LAC',SDG:'LAC'};

  const local = {
    data: null,
    results: { results: [] },
    projections: [],
    gameMap: new Map(),
    currentWeek: null,
    selectedWeek: null,
    validation: { errors: [], warnings: [] },
    lastFocus: null,
    activeDetailGame: null,
    activeDetailTab: 'overview'
  };

  const esc = value => String(value ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
  const num = value => value === '' || value == null ? null : (Number.isFinite(Number(value)) ? Number(value) : null);
  const fmt = value => num(value) === null ? '—' : Number(value).toFixed(1);
  const parseTime = value => { const d = new Date(value); return Number.isNaN(d.getTime()) ? null : d; };
  const typeLabel = type => ({ATS:'ATS',SU:'Straight up',TOTAL:'Total',SITUATIONAL:'Situational'}[type] || type);

  function siteState() {
    try { return typeof STATE !== 'undefined' ? STATE : null; } catch (_) { return null; }
  }

  function getConfig() { return siteState()?.config || {}; }
  function getProjections() { return siteState()?.projections || []; }

  // Single source of truth for how a trend is compared with the model.
  function determineModelLeans(game, config = {}) {
    const spreadBand = num(config.spreadNeutralBand) ?? 0.25;
    const totalBand = num(config.totalNeutralBand) ?? 1.0;
    const moneylineBand = num(config.moneylineNeutralBandPct) ?? 0.5;
    const modelSpread = num(game?.modelSpreadHome);
    const marketSpread = num(game?.marketSpreadHome);
    const modelTotal = num(game?.modelTotal);
    const marketTotal = num(game?.marketTotal);
    const homeWin = num(game?.homeWinProbability);

    let spread = null, total = null, moneyline = null;
    let spreadDifference = null, totalDifference = null;
    if (modelSpread !== null && marketSpread !== null) {
      spreadDifference = marketSpread - modelSpread;
      if (spreadDifference > spreadBand) spread = 'home';
      else if (spreadDifference < -spreadBand) spread = 'away';
    }
    if (modelTotal !== null && marketTotal !== null) {
      totalDifference = modelTotal - marketTotal;
      if (totalDifference > totalBand) total = 'over';
      else if (totalDifference < -totalBand) total = 'under';
    }
    if (homeWin !== null) {
      if (homeWin > 50 + moneylineBand) moneyline = 'home';
      else if (homeWin < 50 - moneylineBand) moneyline = 'away';
    }
    return { spread, total, moneyline, spreadDifference, totalDifference };
  }

  function determineTrendAlignment(trend, game, config = {}) {
    const pointsTo = String(trend?.pointsTo || 'none').toLowerCase();
    const target = String(trend?.alignmentTarget || 'none').toLowerCase();
    if (pointsTo === 'none' || target === 'none') {
      return { state: 'informational', label: 'Informational', icon: 'ℹ', modelSide: null };
    }
    const leans = determineModelLeans(game, config);
    const modelSide = leans[target] || null;
    if (!modelSide) {
      return { state: 'neutral', label: 'No model lean', icon: '—', modelSide: null };
    }
    if (pointsTo === modelSide) {
      return { state: 'aligns', label: 'Aligns with model', icon: '✓', modelSide };
    }
    return { state: 'conflicts', label: 'Conflicts with model', icon: '!', modelSide };
  }

  function validateTrendData(data, projections) {
    const errors = [], warnings = [];
    const games = new Map(projections.map(g => [String(g.gameId), g]));
    const ids = new Set();
    if (!data || typeof data !== 'object') return { errors: ['Trend data is not an object.'], warnings };
    if (data.schemaVersion !== 1) errors.push('schemaVersion must be 1.');
    if (!Number.isInteger(data.season)) errors.push('season must be an integer.');
    if (!Number.isInteger(data.week) || data.week < 1 || data.week > 25) errors.push('week must be 1-25.');
    if (!parseTime(data.lastUpdated)) errors.push('lastUpdated must be a valid timestamp.');
    if (!data.source?.name || !data.source?.url) errors.push('source name and link are required.');
    if (!Array.isArray(data.trends)) errors.push('trends must be an array.');
    const currentWeek = Number(getConfig().currentWeek);
    if (Number.isFinite(currentWeek) && Number(data.week) !== currentWeek) warnings.push(`File is Week ${data.week}; site current week is ${currentWeek}. It will be shown only as archived data.`);

    for (const [i, trend] of (Array.isArray(data.trends) ? data.trends : []).entries()) {
      const p = `Trend ${i + 1}`;
      if (!trend.id) errors.push(`${p}: id is required.`);
      else if (ids.has(trend.id)) errors.push(`${p}: duplicate id ${trend.id}.`);
      ids.add(trend.id);
      const game = games.get(String(trend.gameId));
      if (!game) { errors.push(`${p}: gameId ${trend.gameId || 'missing'} does not match the NFL projections file.`); continue; }
      if (Number(trend.season) !== Number(game.season) || Number(trend.week) !== Number(game.week)) errors.push(`${p}: season/week does not match the game.`);
      if (Number(trend.season) !== Number(data.season) || Number(trend.week) !== Number(data.week)) errors.push(`${p}: season/week does not match the weekly trend file.`);
      if (trend.matchup?.away !== game.awayTeam || trend.matchup?.home !== game.homeTeam) errors.push(`${p}: matchup must be ${game.awayTeam} at ${game.homeTeam}.`);
      if (TEAM_ALIASES[trend.matchup?.away] || TEAM_ALIASES[trend.matchup?.home] || TEAM_ALIASES[trend.subject]) errors.push(`${p}: use canonical team abbreviations such as JAX, LA, WAS, or LAC.`);
      if (trend.subject !== 'TOTAL' && ![game.awayTeam, game.homeTeam].includes(trend.subject)) errors.push(`${p}: subject must be ${game.awayTeam}, ${game.homeTeam}, or TOTAL.`);
      if (!VALID_TYPES.has(trend.trendType)) errors.push(`${p}: invalid trendType.`);
      if (!VALID_POINTS.has(trend.pointsTo)) errors.push(`${p}: invalid pointsTo.`);
      if (!VALID_TARGETS.has(trend.alignmentTarget)) errors.push(`${p}: invalid alignmentTarget.`);
      if (trend.trendType === 'ATS' && trend.alignmentTarget !== 'spread') errors.push(`${p}: ATS requires alignmentTarget spread.`);
      if (trend.trendType === 'SU' && trend.alignmentTarget !== 'moneyline') errors.push(`${p}: SU requires alignmentTarget moneyline.`);
      if (trend.trendType === 'TOTAL' && trend.alignmentTarget !== 'total') errors.push(`${p}: TOTAL requires alignmentTarget total.`);
      if (trend.alignmentTarget === 'total' && !['over','under','none'].includes(trend.pointsTo)) errors.push(`${p}: total trends can point only over, under, or none.`);
      if (['spread','moneyline'].includes(trend.alignmentTarget) && !['home','away','none'].includes(trend.pointsTo)) errors.push(`${p}: side trends can point only home, away, or none.`);
      const text = String(trend.text || '').trim();
      if (text.length < 5 || text.length > 180) errors.push(`${p}: text must be 5-180 characters.`);
      if (!Number.isInteger(trend.sampleSize) || trend.sampleSize < 1) errors.push(`${p}: sampleSize must be a positive integer.`);
      if (!String(trend.record || '').trim()) errors.push(`${p}: record is required.`);
      if (!trend.sourceName || !trend.sourceUrl) errors.push(`${p}: sourceName and sourceUrl are required.`);
    }
    return { errors, warnings };
  }

  function isFileCurrentForGame(game) {
    return Number(local.data?.season) === Number(game?.season) && Number(local.data?.week) === Number(game?.week) && Number(local.data?.week) === Number(local.currentWeek);
  }

  function trendsForGame(game, { currentOnly = false } = {}) {
    if (!game || !local.data) return [];
    if (currentOnly && !isFileCurrentForGame(game)) return [];
    return local.data.trends.filter(t => String(t.gameId) === String(game.gameId));
  }

  function summarizeGame(game, trends = trendsForGame(game, {currentOnly:true})) {
    const rows = trends.map(trend => ({ trend, alignment: determineTrendAlignment(trend, game, local.data?.alignmentConfig) }));
    const directional = rows.filter(x => ['aligns','conflicts'].includes(x.alignment.state));
    return {
      total: rows.length,
      evaluated: directional.length,
      aligns: directional.filter(x => x.alignment.state === 'aligns').length,
      conflicts: directional.filter(x => x.alignment.state === 'conflicts').length,
      neutral: rows.filter(x => x.alignment.state === 'neutral').length,
      informational: rows.filter(x => x.alignment.state === 'informational').length,
      rows
    };
  }

  function alignmentBadge(alignment) {
    return `<span class="trend-indicator trend-${alignment.state}" aria-label="${esc(alignment.label)}"><span aria-hidden="true">${esc(alignment.icon)}</span>${esc(alignment.label)}</span>`;
  }

  function sourceLink(trend) {
    return `<a class="trend-source-link" href="${esc(trend.sourceUrl || local.data?.source?.url || '#')}" target="_blank" rel="noopener noreferrer">Source: ${esc(trend.sourceName || local.data?.source?.name || 'Action Network')}</a>`;
  }

  function renderTrendItem(trend, game) {
    const alignment = determineTrendAlignment(trend, game, local.data?.alignmentConfig);
    const tags = Array.isArray(trend.tags) && trend.tags.length ? `<div class="trend-tags">${trend.tags.map(tag => `<span>${esc(tag)}</span>`).join('')}</div>` : '';
    return `<article class="trend-item trend-item-${alignment.state}">
      <div class="trend-item-head"><span class="trend-type">${esc(typeLabel(trend.trendType))}</span>${alignmentBadge(alignment)}</div>
      <p>${esc(trend.text)}</p>
      <div class="trend-meta"><span><strong>${esc(trend.record)}</strong></span><span>Sample: ${Number(trend.sampleSize)}</span><span>Points to: ${esc(trend.pointsTo)}</span></div>
      ${tags}
      <div class="trend-source-row">${sourceLink(trend)}</div>
    </article>`;
  }

  function ensureNav() {
    const nav = document.querySelector('.primary-nav');
    if (!nav || nav.querySelector('a[href="#trends"]')) return;
    const link = document.createElement('a');
    link.href = '#trends';
    link.textContent = 'Trends';
    const record = nav.querySelector('a[href="#record"]');
    record ? nav.insertBefore(link, record) : nav.appendChild(link);
  }

  function ensurePage() {
    if (document.getElementById('trends')) return;
    const projections = document.getElementById('projections');
    if (!projections) return;
    const section = document.createElement('section');
    section.className = 'section-shell nfl-trends-section';
    section.id = 'trends';
    section.setAttribute('aria-labelledby', 'nflTrendsTitle');
    section.innerHTML = `
      <div class="section-heading nfl-trends-heading">
        <div><p class="eyebrow">WEEKLY CONTEXT</p><h2 id="nflTrendsTitle">NFL Trends</h2><p>Short historical trend summaries compared with the current CB Model projection. Alignment is context only; it does not change the projection, reliability, confidence, or official model record.</p></div>
        <div class="trend-source-credit"><a id="nflTrendSourceTop" target="_blank" rel="noopener noreferrer">Source: Action Network ↗</a><span id="nflTrendUpdated">Loading…</span></div>
      </div>
      <div class="trend-status-row"><span id="nflTrendWeekChip" class="research-chip">Week —</span><span id="nflTrendModeChip" class="trend-mode-chip" hidden>Mock data mode</span><span id="nflTrendValidationChip" class="trend-validation-chip">Validating…</span></div>
      <div id="nflTrendStale" class="trend-stale-banner" role="status" hidden></div>
      <article class="panel trend-top-panel"><div class="panel-head"><div><p class="eyebrow">THIS WEEK</p><h3>Top aligned games</h3></div></div><p class="trend-explainer">“Aligned” means a historical trend points in the same direction as the model's current spread, total, or straight-up lean. It does not mean the game is more likely to win.</p><div id="nflTrendTopGames" class="trend-top-games"></div></article>
      <div class="trend-filter-panel" aria-label="NFL trend filters">
        <label><span>Week</span><select id="nflTrendWeek"></select></label>
        <label><span>Trend type</span><select id="nflTrendType"><option value="">All types</option><option value="ATS">ATS</option><option value="SU">Straight up</option><option value="TOTAL">Totals</option><option value="SITUATIONAL">Situational</option></select></label>
        <label><span>Team</span><select id="nflTrendTeam"><option value="">All teams</option></select></label>
        <label class="trend-check"><input id="nflTrendAlignedOnly" type="checkbox"><span>Aligns with model only</span></label>
        <button id="nflTrendReset" class="button button-quiet" type="button">Reset</button>
      </div>
      <div id="nflTrendCards" class="trend-game-list" aria-live="polite"></div>
      <div class="trend-bottom-grid">
        <article class="panel"><div class="panel-head"><div><p class="eyebrow">HOW TO READ TRENDS</p><h3>Context, not prediction</h3></div></div><p>ATS compares with the model's spread side. Straight-up compares with the calibrated win side. Total trends compare with the model total versus the market total. Situational trends use the alignment target entered in the weekly JSON.</p><p>Small samples and long-running historical patterns can be noise. Trends describe what happened before; they do not prove what will happen next.</p></article>
        <article class="panel"><div class="panel-head"><div><p class="eyebrow">INFORMATIONAL TRACKER</p><h3>Trend alignment results</h3></div></div><div id="nflTrendResults"></div></article>
      </div>
      <div id="nflTrendValidator" class="trend-validator" hidden></div>
      <p class="trend-panel-disclaimer">${esc(TREND_DISCLAIMER)}</p>`;
    projections.insertAdjacentElement('afterend', section);
    bindPageControls();
  }

  function fillPageControls() {
    const weeks = [...new Set([...local.projections.map(g => Number(g.week)).filter(Number.isFinite), Number(local.data?.week)].filter(Number.isFinite))].sort((a,b)=>a-b);
    const weekSelect = document.getElementById('nflTrendWeek');
    if (weekSelect) weekSelect.innerHTML = weeks.map(w => `<option value="${w}">Week ${w}</option>`).join('');
    local.selectedWeek = weeks.includes(Number(local.currentWeek)) ? Number(local.currentWeek) : (Number(local.data?.week) || weeks.at(-1));
    if (weekSelect && local.selectedWeek != null) weekSelect.value = String(local.selectedWeek);
    const teams = [...new Set(local.projections.flatMap(g => [g.awayTeam,g.homeTeam]).filter(Boolean))].sort();
    const teamSelect = document.getElementById('nflTrendTeam');
    if (teamSelect) teamSelect.innerHTML = '<option value="">All teams</option>' + teams.map(t => `<option value="${esc(t)}">${esc(t)}</option>`).join('');
  }

  function bindPageControls() {
    for (const id of ['nflTrendWeek','nflTrendType','nflTrendTeam','nflTrendAlignedOnly']) {
      document.getElementById(id)?.addEventListener('change', () => {
        local.selectedWeek = Number(document.getElementById('nflTrendWeek')?.value || local.currentWeek);
        renderPage();
      });
    }
    document.getElementById('nflTrendReset')?.addEventListener('click', () => {
      const week = document.getElementById('nflTrendWeek'); if (week) week.value = String(local.currentWeek ?? local.data?.week ?? '');
      const type = document.getElementById('nflTrendType'); if (type) type.value = '';
      const team = document.getElementById('nflTrendTeam'); if (team) team.value = '';
      const only = document.getElementById('nflTrendAlignedOnly'); if (only) only.checked = false;
      local.selectedWeek = Number(week?.value || local.data?.week);
      renderPage();
    });
  }

  function renderHeaderState() {
    const updated = document.getElementById('nflTrendUpdated');
    const dt = parseTime(local.data?.lastUpdated);
    if (updated) updated.textContent = dt ? `Last updated ${dt.toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})}` : 'Last updated unavailable';
    const chip = document.getElementById('nflTrendWeekChip');
    if (chip) chip.textContent = `Week ${local.data?.week ?? '—'} · ${local.data?.season ?? ''}`;
    const source = document.getElementById('nflTrendSourceTop');
    if (source) { source.href = local.data?.source?.url || '#'; source.textContent = `Source: ${local.data?.source?.name || 'Action Network'} ↗`; }
    const mode = document.getElementById('nflTrendModeChip');
    if (mode) mode.hidden = !MOCK_MODE;
    const validation = document.getElementById('nflTrendValidationChip');
    if (validation) {
      const e = local.validation.errors.length, w = local.validation.warnings.length;
      validation.textContent = e ? `${e} validation error${e===1?'':'s'}` : w ? `Valid · ${w} warning${w===1?'':'s'}` : 'Data valid';
      validation.dataset.state = e ? 'error' : w ? 'warning' : 'ok';
    }
    const showValidator = MOCK_MODE || new URL(location.href).searchParams.get('validateTrends') === '1' || local.validation.errors.length > 0;
    const validator = document.getElementById('nflTrendValidator');
    if (validator) {
      validator.hidden = !showValidator;
      validator.innerHTML = `<strong>Trend data validator</strong>${local.validation.errors.length?`<ul>${local.validation.errors.map(x=>`<li class="error">${esc(x)}</li>`).join('')}</ul>`:'<p>No validation errors.</p>'}${local.validation.warnings.length?`<ul>${local.validation.warnings.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}`;
    }
  }

  function selectedFilters() {
    return {
      week: Number(document.getElementById('nflTrendWeek')?.value || local.selectedWeek || local.currentWeek),
      type: document.getElementById('nflTrendType')?.value || '',
      team: document.getElementById('nflTrendTeam')?.value || '',
      alignsOnly: Boolean(document.getElementById('nflTrendAlignedOnly')?.checked)
    };
  }

  function filteredTrendRows(game, filters) {
    return trendsForGame(game).filter(trend => {
      if (Number(trend.week) !== filters.week) return false;
      if (filters.type && trend.trendType !== filters.type) return false;
      if (filters.team && ![trend.matchup?.away, trend.matchup?.home, trend.subject].includes(filters.team)) return false;
      if (filters.alignsOnly && determineTrendAlignment(trend, game, local.data?.alignmentConfig).state !== 'aligns') return false;
      return true;
    });
  }

  function renderTopGames(filters) {
    const host = document.getElementById('nflTrendTopGames'); if (!host) return;
    const games = local.projections.filter(g => Number(g.week) === filters.week).map(game => ({game, summary:summarizeGame(game, trendsForGame(game).filter(t=>Number(t.week)===filters.week))})).filter(x => x.summary.evaluated > 0).sort((a,b) => b.summary.aligns-a.summary.aligns || (b.summary.aligns/b.summary.evaluated)-(a.summary.aligns/a.summary.evaluated)).slice(0,4);
    host.innerHTML = games.length ? games.map(({game,summary}) => `<button type="button" class="trend-top-game" data-open-trend-game="${esc(game.gameId)}"><strong>${esc(game.awayTeam)} @ ${esc(game.homeTeam)}</strong><span>✓ ${summary.aligns} of ${summary.evaluated} directional trends align</span></button>`).join('') : '<p class="trend-empty-inline">No directional trends entered for this week yet.</p>';
  }

  function renderResultsTracker() {
    const host = document.getElementById('nflTrendResults'); if (!host) return;
    const graded = (local.results?.results || []).filter(r => r.alignmentAtPublish === 'aligns' && ['win','loss','push'].includes(r.outcome));
    const wins = graded.filter(r=>r.outcome==='win').length, losses=graded.filter(r=>r.outcome==='loss').length, pushes=graded.filter(r=>r.outcome==='push').length;
    if (!graded.length) { host.innerHTML = '<p>No aligned-trend results have been graded yet.</p><small>When games are final, grade the separate nfl-trend-results.json file. These results never enter the official model record.</small>'; return; }
    const decisions=wins+losses;
    host.innerHTML = `<div class="trend-result-grid"><div><span>Aligned results</span><strong>${wins}-${losses}${pushes?`-${pushes}`:''}</strong></div><div><span>Decision rate</span><strong>${decisions?`${(wins/decisions*100).toFixed(1)}%`:'—'}</strong></div><div><span>Sample</span><strong>${graded.length}</strong></div></div><small>Small samples can be misleading. This is an informational context tracker, not the official CB Model record.</small>`;
  }

  function renderPage() {
    if (!local.data) return;
    renderHeaderState();
    const filters = selectedFilters();
    local.selectedWeek = filters.week;
    const stale = Number(filters.week) !== Number(local.currentWeek) || Number(local.data.week) !== Number(local.currentWeek);
    const staleBox = document.getElementById('nflTrendStale');
    if (staleBox) {
      staleBox.hidden = !stale;
      staleBox.textContent = `Archived/stale trend view: these trends are not treated as current Week ${local.currentWeek ?? '—'} context and are excluded from projection badges.`;
    }
    renderTopGames(filters);
    renderResultsTracker();
    const host = document.getElementById('nflTrendCards'); if (!host) return;
    const games = local.projections.filter(g => Number(g.week) === filters.week && (!filters.team || g.awayTeam===filters.team || g.homeTeam===filters.team));
    const cards = [];
    for (const game of games) {
      const all = trendsForGame(game).filter(t => Number(t.week) === filters.week);
      const visible = filteredTrendRows(game, filters);
      if ((filters.type || filters.alignsOnly) && !visible.length) continue;
      const summary = summarizeGame(game, all);
      const leans = determineModelLeans(game, local.data.alignmentConfig);
      cards.push(`<details class="trend-game-card" ${visible.length && cards.length<2?'open':''}>
        <summary><div><span class="trend-game-time">${esc(game.date || '')} · ${esc(game.kickoffET || '')} ET</span><strong>${esc(game.awayTeam)} @ ${esc(game.homeTeam)}</strong><small>Model context: spread ${esc(leans.spread || 'neutral')} · total ${esc(leans.total || 'neutral')} · SU ${esc(leans.moneyline || 'neutral')}</small></div><div class="trend-game-summary">${summary.evaluated?`<span>✓ ${summary.aligns} of ${summary.evaluated} align</span>`:'<span>No directional trend comparison</span>'}<b>${all.length} trend${all.length===1?'':'s'}</b></div></summary>
        <div class="trend-game-body">
          ${visible.length ? `<div class="trend-items">${visible.map(t=>renderTrendItem(t,game)).join('')}</div>` : '<p class="trend-empty-inline">No trends entered for this game yet.</p>'}
          <div class="trend-game-footer"><a href="${esc(local.data.source.url)}" target="_blank" rel="noopener noreferrer">Source: ${esc(local.data.source.name)} ↗</a><button class="button button-ghost button-small" type="button" data-open-trend-game="${esc(game.gameId)}">Open game detail</button></div>
          <p class="trend-panel-disclaimer">${esc(TREND_DISCLAIMER)}</p>
        </div></details>`);
    }
    host.innerHTML = cards.length ? cards.join('') : '<div class="empty-state">No games match the current trend filters.</div>';
  }

  function decorateProjectionBadges() {
    for (const game of local.projections) {
      const current = isFileCurrentForGame(game);
      const summary = summarizeGame(game, current ? trendsForGame(game, {currentOnly:true}) : []);
      const label = current ? (summary.evaluated ? `✓ ${summary.aligns}/${summary.evaluated} trends align` : summary.total ? `${summary.total} trend${summary.total===1?'':'s'} · no model comparison` : '0 trends entered') : 'Trends archived';
      for (const node of [document.getElementById(`game-${game.gameId}`), document.getElementById(`card-${game.gameId}`)]) {
        if (!node) continue;
        node.querySelectorAll('.nfl-trend-summary-badge').forEach(x=>x.remove());
        const badge = document.createElement('button');
        badge.type = 'button';
        badge.className = `nfl-trend-summary-badge ${summary.aligns?'has-align':''}`;
        badge.dataset.openTrendGame = game.gameId;
        badge.setAttribute('aria-label', `${label}. Open ${game.awayTeam} at ${game.homeTeam} trend detail.`);
        badge.innerHTML = `<span aria-hidden="true">${summary.aligns?'✓':'↗'}</span>${esc(label)}`;
        const target = node.id.startsWith('game-') ? node.querySelector('.game-cell') : node.querySelector('.projection-card-head > div');
        target?.appendChild(badge);
      }
    }
  }

  function ensureProjectionObserver() {
    const body = document.getElementById('projectionBody'), cards = document.getElementById('projectionCards');
    const observer = new MutationObserver(() => decorateProjectionBadges());
    if (body) observer.observe(body,{childList:true});
    if (cards) observer.observe(cards,{childList:true});
    decorateProjectionBadges();
  }

  function ensureDetail() {
    if (document.getElementById('nflTrendGameDetail')) return;
    const wrap = document.createElement('div');
    wrap.id='nflTrendGameDetail'; wrap.className='nfl-trend-detail'; wrap.hidden=true;
    wrap.innerHTML=`<button class="nfl-trend-detail-backdrop" type="button" data-trend-detail-close aria-label="Close game detail"></button><section class="nfl-trend-detail-panel" role="dialog" aria-modal="true" aria-labelledby="nflTrendDetailTitle"><header><button class="button button-quiet button-small" type="button" data-trend-detail-close>← Back</button><div><span class="command-label">NFL GAME RESEARCH</span><h2 id="nflTrendDetailTitle">Game detail</h2></div><button class="icon-button" type="button" data-trend-detail-close aria-label="Close game detail">×</button></header><div id="nflTrendDetailTabs" class="live-tabs" role="tablist" aria-label="NFL game detail sections"></div><div id="nflTrendDetailPanel" class="nfl-trend-detail-content" role="tabpanel" tabindex="0"></div></section>`;
    document.body.appendChild(wrap);
  }

  function detailGame() { return local.gameMap.get(local.activeDetailGame) || null; }
  function detailTabs() {
    const host=document.getElementById('nflTrendDetailTabs'); if(!host)return;
    host.innerHTML=[['overview','Overview'],['trends','Trends'],['context','Context']].map(([id,label])=>`<button role="tab" type="button" data-trend-detail-tab="${id}" aria-selected="${local.activeDetailTab===id}" class="${local.activeDetailTab===id?'active':''}">${label}</button>`).join('');
  }

  function renderDetail() {
    const game=detailGame(), panel=document.getElementById('nflTrendDetailPanel'); if(!game||!panel)return;
    document.getElementById('nflTrendDetailTitle').textContent=`${game.awayTeam} @ ${game.homeTeam}`;
    detailTabs();
    if(local.activeDetailTab==='overview'){
      const leans=determineModelLeans(game,local.data.alignmentConfig),summary=summarizeGame(game,trendsForGame(game,{currentOnly:true}));
      panel.innerHTML=`<section class="detail-section"><div class="detail-section-head"><div><span class="command-label">PREGAME MODEL</span><h3>Frozen projection</h3></div><span class="current-not-final">Research only</span></div><div class="detail-model-grid"><div><span>Projected score</span><strong>${fmt(game.projectedAwayPoints)} – ${fmt(game.projectedHomePoints)}</strong><small>${esc(game.awayTeam)} – ${esc(game.homeTeam)}</small></div><div><span>Model spread</span><strong>${fmt(game.modelSpreadHome)}</strong><small>Home-line convention</small></div><div><span>Model total</span><strong>${fmt(game.modelTotal)}</strong><small>Market ${fmt(game.marketTotal)}</small></div><div><span>Home win probability</span><strong>${fmt(game.homeWinProbability)}%</strong><small>${esc(game.homeTeam)}</small></div></div><div class="trend-detail-summary"><strong>Trend context</strong><span>${summary.evaluated?`${summary.aligns} of ${summary.evaluated} directional trends align`:`${summary.total} trend${summary.total===1?'':'s'} entered`}</span><span>Spread ${esc(leans.spread||'neutral')} · Total ${esc(leans.total||'neutral')} · SU ${esc(leans.moneyline||'neutral')}</span></div></section><p class="trend-panel-disclaimer">${esc(TREND_DISCLAIMER)}</p>`;
    } else if(local.activeDetailTab==='trends'){
      const current=isFileCurrentForGame(game), trends=trendsForGame(game,{currentOnly:true});
      panel.innerHTML=`<section class="detail-section"><div class="detail-section-head"><div><span class="command-label">HISTORICAL CONTEXT</span><h3>Trends</h3></div><a class="trend-source-link" href="${esc(local.data.source.url)}" target="_blank" rel="noopener noreferrer">Source: ${esc(local.data.source.name)} ↗</a></div>${current?(trends.length?`<div class="trend-items">${trends.map(t=>renderTrendItem(t,game)).join('')}</div>`:'<div class="detail-empty">No current-week trends entered for this game yet.</div>'):`<div class="detail-empty">The loaded trend file is not current for this game. Stale trends are hidden from game detail.</div>`}</section><p class="trend-panel-disclaimer">${esc(TREND_DISCLAIMER)}</p>`;
    } else {
      panel.innerHTML=`<section class="detail-section"><div class="detail-section-head"><div><span class="command-label">MODEL CONTEXT</span><h3>Reliability and release state</h3></div></div><div class="trend-context-grid"><div><span>Spread reliability</span><strong>${esc(game.spreadReliability||'—')}</strong></div><div><span>Total reliability</span><strong>${esc(game.totalReliability||'—')}</strong></div><div><span>Personnel</span><strong>${esc(String(game.personnelState||'').replaceAll('_',' ')||'—')}</strong></div><div><span>Weather / roof</span><strong>${esc(String(game.weatherRoofState||'').replaceAll('_',' ')||'—')}</strong></div></div><div class="detail-context-note"><strong>Release status</strong><span>${esc(String(game.releaseStatus||'HOLD').replaceAll('_',' '))}</span></div></section><p class="trend-panel-disclaimer">${esc(TREND_DISCLAIMER)}</p>`;
    }
  }

  function openDetail(gameId, tab='trends') {
    const game=local.gameMap.get(String(gameId)); if(!game)return;
    ensureDetail(); local.lastFocus=document.activeElement; local.activeDetailGame=String(gameId); local.activeDetailTab=tab;
    const wrap=document.getElementById('nflTrendGameDetail'); wrap.hidden=false; document.body.classList.add('nfl-trend-detail-open');
    renderDetail(); wrap.querySelector('[data-trend-detail-close]')?.focus();
    const url=new URL(location.href); url.searchParams.set('game',gameId); history.replaceState(history.state,'',url.toString());
  }

  function closeDetail() {
    const wrap=document.getElementById('nflTrendGameDetail'); if(!wrap||wrap.hidden)return;
    wrap.hidden=true; document.body.classList.remove('nfl-trend-detail-open'); local.activeDetailGame=null;
    const url=new URL(location.href); url.searchParams.delete('game'); history.replaceState(history.state,'',url.toString()); local.lastFocus?.focus?.();
  }

  function bindGlobalClicks() {
    document.addEventListener('click',event=>{
      const opener=event.target.closest('[data-open-trend-game]'); if(opener){event.preventDefault();openDetail(opener.dataset.openTrendGame,'trends');return;}
      if(event.target.closest('[data-trend-detail-close]')){closeDetail();return;}
      const tab=event.target.closest('[data-trend-detail-tab]'); if(tab){local.activeDetailTab=tab.dataset.trendDetailTab;renderDetail();}
    });
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!document.getElementById('nflTrendGameDetail')?.hidden)closeDetail();});
  }

  async function loadData() {
    const dataPath=MOCK_MODE?MOCK_URL:DATA_URL;
    const [data,results]=await Promise.all([
      fetch(dataPath,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`Could not load ${dataPath}`);return r.json()}),
      fetch(RESULTS_URL,{cache:'no-store'}).then(r=>r.ok?r.json():({results:[]})).catch(()=>({results:[]}))
    ]);
    local.data=data; local.results=results;
  }

  async function waitForSiteData() {
    for(let i=0;i<50;i++){
      const p=getProjections(); if(p.length){local.projections=p;local.gameMap=new Map(p.map(g=>[String(g.gameId),g]));local.currentWeek=Number(getConfig().currentWeek);return;}
      await new Promise(r=>setTimeout(r,100));
    }
    throw new Error('NFL projection data did not become available for trends integration.');
  }

  async function boot() {
    try {
      await Promise.all([loadData(),waitForSiteData()]);
      local.validation=validateTrendData(local.data,local.projections);
      ensureNav(); ensurePage(); fillPageControls(); bindGlobalClicks(); ensureProjectionObserver(); renderPage(); ensureDetail();
      document.getElementById('footerDisclaimer') && (document.getElementById('footerDisclaimer').textContent=FULL_DISCLAIMER);
      const deep=new URL(location.href).searchParams.get('game'); if(deep&&local.gameMap.has(deep))openDetail(deep,'overview');
      window.CBNFLTrends={determineModelLeans,determineTrendAlignment,validateTrendData,summarizeGame,openDetail,refresh:renderPage,state:local};
    } catch(error) {
      console.error('NFL Trends:',error);
      ensureNav(); ensurePage();
      const host=document.getElementById('nflTrendCards'); if(host)host.innerHTML='<div class="empty-state">NFL trends data could not be loaded. Check nfl-trends.json and the validation workflow.</div>';
    }
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
