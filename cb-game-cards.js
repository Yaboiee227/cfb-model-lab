(() => {
  if (window.__CB_PHASE2_GAME_CARDS) return;
  window.__CB_PHASE2_GAME_CARDS = true;

  const league = String(window.CB_ACTIVE_LEAGUE || 'cfb').toLowerCase() === 'nfl' ? 'nfl' : 'cfb';
  const q = selector => document.querySelector(selector);
  const qa = selector => [...document.querySelectorAll(selector)];
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
  const num = value => value === '' || value == null || !Number.isFinite(Number(value)) ? null : Number(value);
  const fmt1 = value => num(value) === null ? '—' : Number(value).toFixed(1);
  const pct = value => num(value) === null ? '—' : `${Number(value).toFixed(1)}%`;
  const visuals = () => window.CBTeamVisuals;

  const trendState = { doc: null, loaded: false, error: null };
  let scheduleFrame = 0;

  function state() {
    try { return typeof STATE !== 'undefined' ? STATE : null; }
    catch (_) { return null; }
  }

  function gameById(id) {
    return state()?.projections?.find(game => String(game.gameId) === String(id)) || null;
  }

  function spreadText(game, value) {
    try {
      if (typeof spreadLabel === 'function') return spreadLabel(game.homeTeam, game.awayTeam, value);
    } catch (_) {}
    const line = num(value);
    if (line === null) return '—';
    if (Math.abs(line) < 0.05) return "Pick 'em";
    return line < 0 ? `${game.homeTeam} ${line.toFixed(1)}` : `${game.awayTeam} -${line.toFixed(1)}`;
  }

  function spreadDifference(game) {
    try {
      if (typeof spreadGapLabel === 'function') return spreadGapLabel(game);
    } catch (_) {}
    const model = num(game.modelSpreadHome);
    const market = num(game.marketSpreadHome);
    if (model === null || market === null) return { text: '—', magnitude: 0, raw: null };
    const difference = market - model;
    if (Math.abs(difference) < 0.05) return { text: 'Aligned', magnitude: 0, raw: difference };
    return {
      text: `${difference > 0 ? game.homeTeam : game.awayTeam} ${Math.abs(difference).toFixed(1)}`,
      magnitude: Math.abs(difference), raw: difference
    };
  }

  function totalDifference(game) {
    const model = num(game.modelTotal);
    const market = num(game.marketTotal);
    if (model === null || market === null) return { text: '—', magnitude: 0, raw: null };
    const difference = model - market;
    if (Math.abs(difference) < 0.05) return { text: 'Aligned', magnitude: 0, raw: difference };
    return {
      text: `${difference > 0 ? 'Over' : 'Under'} ${Math.abs(difference).toFixed(1)}`,
      magnitude: Math.abs(difference), raw: difference
    };
  }

  function kickoffMinutes(value) {
    const raw = String(value || '').trim();
    if (!raw) return null;
    const twelve = raw.match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
    if (twelve) {
      let hour = Number(twelve[1]);
      const minute = Number(twelve[2]);
      const ap = twelve[3].toUpperCase();
      if (ap === 'PM' && hour !== 12) hour += 12;
      if (ap === 'AM' && hour === 12) hour = 0;
      return hour * 60 + minute;
    }
    const twentyFour = raw.match(/^(\d{1,2}):(\d{2})/);
    return twentyFour ? Number(twentyFour[1]) * 60 + Number(twentyFour[2]) : null;
  }

  function isPrimetime(game) {
    const minutes = kickoffMinutes(game.kickoffET);
    return minutes !== null && minutes >= 19 * 60;
  }

  function isRivalry(game) {
    const text = `${game.notes || ''} ${game.context || ''}`.toLowerCase();
    return /\brivalry\b|\brival\b/.test(text);
  }

  function modelLeans(game, config = {}) {
    const spreadBand = num(config.spreadNeutralBand) ?? 0.25;
    const totalBand = num(config.totalNeutralBand) ?? 1.0;
    const moneylineBand = num(config.moneylineNeutralBandPct) ?? 0.5;
    const modelSpread = num(game.modelSpreadHome);
    const marketSpread = num(game.marketSpreadHome);
    const modelTotal = num(game.modelTotal);
    const marketTotal = num(game.marketTotal);
    const homeWin = num(game.homeWinProbability);
    let spread = null, total = null, moneyline = null;

    if (modelSpread !== null && marketSpread !== null) {
      const difference = marketSpread - modelSpread;
      if (difference > spreadBand) spread = 'home';
      else if (difference < -spreadBand) spread = 'away';
    }
    if (modelTotal !== null && marketTotal !== null) {
      const difference = modelTotal - marketTotal;
      if (difference > totalBand) total = 'over';
      else if (difference < -totalBand) total = 'under';
    }
    if (homeWin !== null) {
      if (homeWin > 50 + moneylineBand) moneyline = 'home';
      else if (homeWin < 50 - moneylineBand) moneyline = 'away';
    }
    return { spread, total, moneyline };
  }

  function trendsForGame(game) {
    const doc = trendState.doc;
    if (league !== 'nfl' || !doc || !Array.isArray(doc.trends)) return [];
    if (Number(doc.season) !== Number(game.season) || Number(doc.week) !== Number(game.week)) return [];
    return doc.trends.filter(trend => String(trend.gameId) === String(game.gameId));
  }

  function alignmentFor(trend, game) {
    const pointsTo = String(trend?.pointsTo || 'none').toLowerCase();
    const target = String(trend?.alignmentTarget || 'none').toLowerCase();
    if (pointsTo === 'none' || target === 'none') return { state: 'informational', label: 'Informational' };
    const lean = modelLeans(game, trendState.doc?.alignmentConfig || {})[target] || null;
    if (!lean) return { state: 'neutral', label: 'No model lean' };
    return lean === pointsTo
      ? { state: 'aligns', label: 'Aligns with model' }
      : { state: 'conflicts', label: 'Conflicts with model' };
  }

  function trendSummary(game) {
    const rows = trendsForGame(game).map(trend => ({ trend, alignment: alignmentFor(trend, game) }));
    return { rows, aligns: rows.filter(row => row.alignment.state === 'aligns').length };
  }

  function gameTags(game) {
    const summary = trendSummary(game);
    const tags = [];
    if (isPrimetime(game)) tags.push('<span class="cb-game-tag cb-game-tag-primetime"><i aria-hidden="true"></i>Primetime</span>');
    if (isRivalry(game)) tags.push('<span class="cb-game-tag cb-game-tag-rivalry"><i aria-hidden="true"></i>Rivalry</span>');
    if (summary.aligns) tags.push(`<span class="cb-game-tag cb-game-tag-aligned"><i aria-hidden="true">✓</i>${summary.aligns} trend${summary.aligns === 1 ? '' : 's'} aligned</span>`);
    return tags.join('');
  }

  function trendMarkup(game) {
    if (league !== 'nfl') {
      return '<div class="cb-card-empty-context">No separate verified CFB trend feed is attached to this matchup. Context remains in the existing research layer.</div>';
    }
    if (!trendState.loaded) return '<div class="cb-card-empty-context">Loading preserved NFL trend context…</div>';
    if (trendState.error) return '<div class="cb-card-empty-context">NFL trend context is temporarily unavailable. The projection is unchanged.</div>';
    const rows = trendSummary(game).rows;
    if (!rows.length) {
      return '<div class="cb-card-empty-context">No verified current-week trend entry is attached to this game. No stale trend is carried forward.</div>';
    }
    return `<div class="cb-trend-list">${rows.map(({ trend, alignment }) => `
      <article class="cb-trend-row cb-trend-${esc(alignment.state)}">
        <div class="cb-trend-row-head">
          <span class="cb-trend-type">${esc(trend.trendType || 'Trend')}</span>
          <span class="cb-trend-alignment cb-trend-alignment-${esc(alignment.state)}"><i aria-hidden="true">${alignment.state === 'aligns' ? '✓' : alignment.state === 'conflicts' ? '!' : '•'}</i>${esc(alignment.label)}</span>
        </div>
        <p>${esc(trend.text || '')}</p>
        <div class="cb-trend-meta"><span>${esc(trend.record || 'Record unavailable')}</span><span>n=${Number(trend.sampleSize || 0)}</span></div>
      </article>`).join('')}</div>`;
  }

  function detailSignature(game) {
    return JSON.stringify({
      score:[game.projectedAwayPoints,game.projectedHomePoints],
      model:[game.modelSpreadHome,game.modelTotal,game.homeWinProbability,game.awayWinProbability],
      market:[game.marketSpreadHome,game.marketTotal,game.marketSource,game.marketObservedAt],
      trendLoaded:trendState.loaded,
      trendError:Boolean(trendState.error),
      trends:trendsForGame(game)
    });
  }

  function detailMarkup(game, signature) {
    const spread = spreadDifference(game);
    const total = totalDifference(game);
    const score = num(game.projectedAwayPoints) === null || num(game.projectedHomePoints) === null
      ? '—' : `${fmt1(game.projectedAwayPoints)} – ${fmt1(game.projectedHomePoints)}`;
    return `<details class="cb-game-breakdown" data-cb-signature="${esc(signature)}">
      <summary><span>Game breakdown</span><small>Model · market · difference · trends</small><i aria-hidden="true"></i></summary>
      <div class="cb-game-breakdown-body">
        <section class="cb-breakdown-section" aria-label="Model breakdown">
          <div class="cb-breakdown-head"><span>Model</span><small>Frozen projection</small></div>
          <div class="cb-breakdown-grid">
            <div><span>Projected score</span><strong>${esc(score)}</strong></div>
            <div><span>Spread</span><strong class="model-value">${esc(spreadText(game, game.modelSpreadHome))}</strong></div>
            <div><span>Total</span><strong class="model-value">${fmt1(game.modelTotal)}</strong></div>
            <div><span>Win probability</span><strong>${esc(game.homeTeam)} ${pct(game.homeWinProbability)}</strong><small>${esc(game.awayTeam)} ${pct(game.awayWinProbability)}</small></div>
          </div>
        </section>
        <section class="cb-breakdown-section" aria-label="Market comparison">
          <div class="cb-breakdown-head"><span>Market</span><small>Comparison layer only</small></div>
          <div class="cb-breakdown-grid">
            <div><span>Spread</span><strong class="market-value">${esc(spreadText(game, game.marketSpreadHome))}</strong></div>
            <div><span>Total</span><strong class="market-value">${fmt1(game.marketTotal)}</strong></div>
            <div class="cb-breakdown-wide"><span>Source</span><strong>${esc(game.marketSource || 'No current market reference')}</strong><small>${esc(game.marketObservedAt || 'Observation time unavailable')}</small></div>
          </div>
        </section>
        <section class="cb-breakdown-section" aria-label="Model market differences">
          <div class="cb-breakdown-head"><span>Difference</span><small>Descriptive research, not a release</small></div>
          <div class="cb-edge-pair">
            <div><span>Spread difference</span><strong>${esc(spread.text)}</strong><small>${spread.raw === null ? 'No comparable market line' : `${spread.magnitude.toFixed(1)} points`}</small></div>
            <div><span>Total difference</span><strong>${esc(total.text)}</strong><small>${total.raw === null ? 'No comparable market total' : `${total.magnitude.toFixed(1)} points`}</small></div>
          </div>
        </section>
        <section class="cb-breakdown-section cb-breakdown-trends" aria-label="Trend context">
          <div class="cb-breakdown-head"><span>Trends</span><small>Context only · zero canonical influence</small></div>
          ${trendMarkup(game)}
        </section>
      </div>
    </details>`;
  }

  function rebuildCardHeader(card, game) {
    const head = card.querySelector('.projection-card-head');
    if (!head) return;
    const time = head.querySelector('.projection-card-time')?.textContent?.trim() || `${game.date || ''} · ${game.kickoffET || ''}`;
    const badgeHtml = head.querySelector('.data-badge')?.outerHTML || '';
    const awayAbbr = league === 'nfl' ? game.awayTeam : null;
    const homeAbbr = league === 'nfl' ? game.homeTeam : null;
    head.innerHTML = `
      <div class="cb-game-card-meta"><span class="projection-card-time">${esc(time)}</span><span class="cb-game-tag-row">${gameTags(game)}</span></div>
      <div class="cb-game-card-matchup">
        ${visuals()?.teamMarkup(game.awayTeam,{abbr:awayAbbr,size:'md',detail:'Away'}) || `<strong>${esc(game.awayTeam)}</strong>`}
        <span class="cb-card-at" aria-hidden="true">@</span>
        ${visuals()?.teamMarkup(game.homeTeam,{abbr:homeAbbr,size:'md',detail:'Home'}) || `<strong>${esc(game.homeTeam)}</strong>`}
      </div>${badgeHtml}`;
    card.dataset.cbPhase2 = 'true';
  }

  function syncCard(card, game) {
    if (!card || !game) return;
    if (card.dataset.cbPhase2 !== 'true') rebuildCardHeader(card, game);

    const tags = card.querySelector('.cb-game-tag-row');
    const nextTags = gameTags(game);
    if (tags && tags.innerHTML !== nextTags) tags.innerHTML = nextTags;

    const signature = detailSignature(game);
    const oldDetails = card.querySelector('.cb-game-breakdown');
    if (oldDetails?.dataset.cbSignature === signature) return;
    const wasOpen = Boolean(oldDetails?.open);
    if (oldDetails) oldDetails.remove();
    const actions = card.querySelector('.projection-card-actions');
    if (actions) actions.insertAdjacentHTML('beforebegin', detailMarkup(game, signature));
    else card.insertAdjacentHTML('beforeend', detailMarkup(game, signature));
    const details = card.querySelector('.cb-game-breakdown');
    if (details && wasOpen) details.open = true;
  }

  function decorateCards() {
    qa('#projectionCards .projection-card[id^="card-"]').forEach(card => {
      syncCard(card, gameById(card.id.replace(/^card-/, '')));
    });
  }

  function applyView(view) {
    const section = q('#projections');
    if (!section) return;
    const next = view === 'table' ? 'table' : 'cards';
    section.dataset.cbView = next;
    localStorage.setItem('cb-projection-view', next);
    qa('[data-cb-view-choice]').forEach(button => {
      const active = button.dataset.cbViewChoice === next;
      button.setAttribute('aria-pressed', String(active));
      button.classList.toggle('active', active);
    });
  }

  function ensureViewToggle() {
    const section = q('#projections');
    const meta = q('#projections .table-meta');
    if (!section || !meta || q('#cbProjectionViewToggle')) return;
    const toolbar = document.createElement('div');
    toolbar.id = 'cbProjectionViewToggle';
    toolbar.className = 'cb-projection-view-toggle';
    toolbar.setAttribute('role','group');
    toolbar.setAttribute('aria-label','Projection view');
    toolbar.innerHTML = '<span>View</span><button type="button" data-cb-view-choice="cards" aria-pressed="false">Cards</button><button type="button" data-cb-view-choice="table" aria-pressed="false">Table</button>';
    meta.insertAdjacentElement('afterend', toolbar);
    toolbar.addEventListener('click', event => {
      const button = event.target.closest('[data-cb-view-choice]');
      if (button) applyView(button.dataset.cbViewChoice);
    });
    applyView(localStorage.getItem('cb-projection-view') || 'cards');
  }

  function scheduleDecorate() {
    cancelAnimationFrame(scheduleFrame);
    scheduleFrame = requestAnimationFrame(() => {
      ensureViewToggle();
      decorateCards();
    });
  }

  async function loadTrendContext() {
    if (league !== 'nfl') {
      trendState.loaded = true;
      scheduleDecorate();
      return;
    }
    try {
      const response = await fetch('nfl_data/site/nfl-trends.json', { cache:'no-store' });
      if (!response.ok) throw new Error(`trend file unavailable (${response.status})`);
      trendState.doc = await response.json();
    } catch (error) {
      trendState.error = error;
    } finally {
      trendState.loaded = true;
      scheduleDecorate();
    }
  }

  function installObserver() {
    const cards = q('#projectionCards');
    if (!cards) return;
    const observer = new MutationObserver(mutations => {
      const externalChange = mutations.some(mutation => [...mutation.addedNodes, ...mutation.removedNodes]
        .some(node => !(node instanceof Element) || !node.closest?.('.cb-game-breakdown')));
      if (externalChange) scheduleDecorate();
    });
    observer.observe(cards,{childList:true,subtree:false});
  }

  function init() {
    document.documentElement.dataset.cbPhase = '2';
    ensureViewToggle();
    installObserver();
    decorateCards();
    loadTrendContext();
    document.addEventListener('cb:live-update', scheduleDecorate);
    document.addEventListener('cb:sportsbooks-update', scheduleDecorate);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once:true });
  else init();
})();
