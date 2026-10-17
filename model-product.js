(() => {
  const ALT_CUSHION = 2.0;
  let activeGameId = null;
  let refreshTimer = null;

  const currentGames = () => {
    try {
      const week = STATE.config?.currentWeek;
      return (STATE.projections || []).filter(game => !week || Number(game.week) === Number(week));
    } catch { return []; }
  };

  const gameById = id => {
    try { return (STATE.projections || []).find(game => game.gameId === id) || null; }
    catch { return null; }
  };

  const roundHalf = n => Math.round(Number(n) * 2) / 2;
  const ceilHalf = n => Math.ceil((Number(n) - 1e-9) * 2) / 2;
  const floorHalf = n => Math.floor((Number(n) + 1e-9) * 2) / 2;
  const hasNum = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const signed = n => {
    if (!Number.isFinite(Number(n))) return '—';
    const value = Number(n);
    if (Math.abs(value) < .05) return 'PK';
    return `${value > 0 ? '+' : ''}${value.toFixed(1)}`;
  };
  const lineFor = (team, line) => signed(line) === 'PK' ? `${team} PK` : `${team} ${signed(line)}`;
  const dataQualityPct = game => {
    if (!hasNum(game.dataQuality)) return null;
    const raw = Number(game.dataQuality);
    return raw <= 1 ? raw * 100 : raw;
  };

  function gapBand(edge) {
    if (!Number.isFinite(edge)) return { key: 'none', label: 'No comparison', range: '—' };
    if (edge < 3) return { key: 'watch', label: 'Watch', range: '< 3.0' };
    if (edge < 5) return { key: 'notable', label: 'Notable', range: '3.0–4.99' };
    if (edge < 7) return { key: 'strong', label: 'Strong', range: '5.0–6.99' };
    return { key: 'large', label: 'Very large', range: '7.0+' };
  }

  function spreadSignal(game) {
    if (!hasNum(game.modelSpreadHome) || !hasNum(game.marketSpreadHome)) return null;
    const modelHome = Number(game.modelSpreadHome);
    const marketHome = Number(game.marketSpreadHome);
    const raw = marketHome - modelHome;
    if (Math.abs(raw) < .001) {
      return {
        side: 'Aligned', team: null, edge: 0, modelSide: 0, marketSide: 0,
        fairRounded: roundHalf(modelHome), altTarget: null, remainingCushion: null,
        band: gapBand(0)
      };
    }
    const homeSide = raw > 0;
    const team = homeSide ? game.homeTeam : game.awayTeam;
    const modelSide = homeSide ? modelHome : -modelHome;
    const marketSide = homeSide ? marketHome : -marketHome;
    const edge = Math.abs(raw);
    const fairRounded = roundHalf(modelSide);
    const altTarget = edge >= ALT_CUSHION ? ceilHalf(modelSide + ALT_CUSHION) : null;
    const remainingCushion = altTarget === null ? null : altTarget - modelSide;
    return {
      side: team, team, edge, modelSide, marketSide, fairRounded, altTarget,
      remainingCushion, band: gapBand(edge)
    };
  }

  function totalSignal(game) {
    if (!hasNum(game.modelTotal) || !hasNum(game.marketTotal)) return null;
    const model = Number(game.modelTotal);
    const market = Number(game.marketTotal);
    const raw = model - market;
    if (Math.abs(raw) < .001) return {
      side: 'Aligned', edge: 0, model, market, fairRounded: roundHalf(model), altTarget: null,
      remainingCushion: null, directionText: 'Total aligned', band: gapBand(0)
    };
    const over = raw > 0;
    const edge = Math.abs(raw);
    let altTarget = null;
    let remainingCushion = null;
    if (edge >= ALT_CUSHION) {
      altTarget = over ? floorHalf(model - ALT_CUSHION) : ceilHalf(model + ALT_CUSHION);
      remainingCushion = over ? model - altTarget : altTarget - model;
    }
    return {
      side: over ? 'Over' : 'Under', edge, model, market, fairRounded: roundHalf(model), altTarget,
      remainingCushion, directionText: `${over ? 'Over' : 'Under'} by model`, band: gapBand(edge)
    };
  }

  function sameDaySnapshot(game) {
    if (!game.marketObservedAt || !game.date) return false;
    return String(game.marketObservedAt).trim().startsWith(String(game.date));
  }

  function validationPass(value) {
    const text = String(value || '').toUpperCase();
    return !text.includes('HOLD') && /(LIVE|PASS|READY|VALIDATED)/.test(text);
  }

  function releasePass(game) {
    const text = String(game.releaseStatus || '').toUpperCase();
    return !text.includes('HOLD') && /(READY|RELEASED|LIVE)/.test(text);
  }

  function personnelFlag(game) {
    return /(personnel|absence|injur|availability|depth|starter|quarterback|qb)/i.test(String(game.notes || ''));
  }

  function readiness(game, marketType = 'spread') {
    const dq = dataQualityPct(game);
    const marketPresent = marketType === 'spread' ? hasNum(game.marketSpreadHome) : hasNum(game.marketTotal);
    const validation = marketType === 'spread' ? STATE.config?.spreadValidation : STATE.config?.totalValidation;
    const checks = [
      { id: 'quality', label: 'Data quality ≥90%', pass: dq !== null && dq >= 90, blocking: true },
      { id: 'market', label: `${marketType === 'spread' ? 'Spread' : 'Total'} reference present`, pass: marketPresent, blocking: true },
      { id: 'freshness', label: 'Same-day market snapshot', pass: sameDaySnapshot(game), blocking: true },
      { id: 'execution', label: 'Execution verified', pass: Boolean(game.executionVerified), blocking: true },
      { id: 'validation', label: `${marketType === 'spread' ? 'Spread' : 'Total'} validation`, pass: validationPass(validation), blocking: true },
      { id: 'release', label: 'Game release state READY', pass: releasePass(game), blocking: true }
    ];
    const passed = checks.filter(check => check.pass).length;
    const blockers = checks.filter(check => check.blocking && !check.pass).map(check => check.label);
    if (personnelFlag(game)) blockers.push('Personnel / availability review');
    return {
      checks, passed, total: checks.length, blockers,
      status: blockers.length ? 'HOLD' : 'READY',
      personnelReview: personnelFlag(game)
    };
  }

  function spreadAltText(game, signal) {
    if (!signal || !signal.team) return 'No directional spread gap';
    if (signal.altTarget === null) return `No ${ALT_CUSHION.toFixed(1)}-pt alt cushion available from current reference`;
    return `${lineFor(signal.team, signal.altTarget)} or better`;
  }

  function totalAltText(signal) {
    if (!signal || signal.side === 'Aligned') return 'No directional total gap';
    if (signal.altTarget === null) return `No ${ALT_CUSHION.toFixed(1)}-pt alt cushion available from current reference`;
    return signal.side === 'Over'
      ? `Over ${signal.altTarget.toFixed(1)} or lower`
      : `Under ${signal.altTarget.toFixed(1)} or higher`;
  }

  function ensureTopSignals() {
    const audit = document.getElementById('slateAudit');
    if (!audit || document.getElementById('topSignals')) return;
    const section = document.createElement('section');
    section.className = 'top-signals';
    section.id = 'topSignals';
    section.setAttribute('aria-labelledby', 'topSignalsTitle');
    section.innerHTML = `
      <div class="top-signals-head">
        <div>
          <span class="command-label">MODEL / MARKET MONITOR</span>
          <h2 id="topSignalsTitle">Top spread gaps</h2>
          <p>Largest current model/market differences for the loaded week. Ranked by gap only—not by release readiness.</p>
        </div>
        <div class="signal-threshold-key" aria-label="Provisional gap bands">
          <span>&lt;3 Watch</span><span>3–4.99 Notable</span><span>5–6.99 Strong</span><span>7+ Very large</span>
        </div>
      </div>
      <div class="top-signals-note"><strong>Provisional bands.</strong> These organize research signals only. They are not validated betting thresholds and cannot override HOLD gates.</div>
      <div class="top-signals-grid" id="topSignalsGrid"></div>`;
    audit.insertAdjacentElement('afterend', section);
  }

  function renderTopSignals() {
    const grid = document.getElementById('topSignalsGrid');
    if (!grid) return;
    const signals = currentGames()
      .map(game => ({ game, signal: spreadSignal(game), ready: readiness(game, 'spread') }))
      .filter(item => item.signal)
      .sort((a, b) => b.signal.edge - a.signal.edge)
      .slice(0, 6);

    if (!signals.length) {
      grid.innerHTML = '<div class="top-signals-empty">No current spread references are available for ranking.</div>';
      return;
    }

    let saved = new Set();
    try { saved = new Set(JSON.parse(localStorage.getItem('cb-bookmarks') || '[]')); } catch {}
    grid.innerHTML = signals.map(({ game, signal, ready }, index) => {
      const alt = spreadAltText(game, signal);
      const fair = signal.team ? lineFor(signal.team, signal.fairRounded) : 'Aligned';
      const market = signal.team ? lineFor(signal.team, signal.marketSide) : 'Aligned';
      const cushion = signal.remainingCushion === null ? '—' : `${signal.remainingCushion.toFixed(1)} pts`;
      const isSaved = saved.has(game.gameId);
      return `
        <article class="top-signal-card gap-${signal.band.key}">
          <div class="top-signal-rank"><span>#${index + 1}</span><span class="gap-band-badge">${escapeHtml(signal.band.range)}</span></div>
          <div class="top-signal-meta">${formatDate(game.date)} · ${escapeHtml(game.kickoffET)} ET</div>
          <h3>${escapeHtml(game.awayTeam)} <span>@</span> ${escapeHtml(game.homeTeam)}</h3>
          <div class="top-signal-main">
            <span>Projected side</span>
            <strong>${escapeHtml(signal.side)}</strong>
            <b>${signal.edge.toFixed(1)}-pt spread gap</b>
          </div>
          <div class="top-signal-lines">
            <div><span>Model fair · rounded</span><strong class="model-value">${escapeHtml(fair)}</strong></div>
            <div><span>Market reference</span><strong class="market-value">${escapeHtml(market)}</strong></div>
          </div>
          <div class="alt-target-box">
            <span>Computed alternative target · unpriced</span>
            <strong>${escapeHtml(alt)}</strong>
            <small>Model cushion at target: ${cushion}</small>
          </div>
          <div class="signal-readiness-row">
            <span class="readiness-badge ${ready.status.toLowerCase()}">${ready.status}</span>
            <small>${ready.passed}/${ready.total} release checks pass${ready.personnelReview ? ' · personnel review flagged' : ''}</small>
          </div>
          <div class="top-signal-actions">
            <button class="button button-ghost button-small" type="button" data-inspect-game="${escapeHtml(game.gameId)}">Inspect</button>
            <button class="button button-quiet button-small" type="button" data-top-priority="${escapeHtml(game.gameId)}">${isSaved ? '★ Saved' : '☆ Save'}</button>
          </div>
        </article>`;
    }).join('');
  }

  function addBandBadges() {
    document.querySelectorAll('#projectionBody tr[id^="game-"]').forEach(row => {
      const id = row.id.replace(/^game-/, '');
      const game = gameById(id);
      const signal = game ? spreadSignal(game) : null;
      const gap = row.querySelector('.gap-value');
      const cell = gap?.parentElement;
      if (!signal || !cell || cell.querySelector('.edge-band-badge')) return;
      const badge = document.createElement('span');
      badge.className = `edge-band-badge gap-${signal.band.key}`;
      badge.textContent = signal.band.range;
      badge.title = `Provisional gap band: ${signal.band.label}. Research organization only.`;
      cell.appendChild(badge);
    });

    document.querySelectorAll('#projectionCards .projection-card[id^="card-"]').forEach(card => {
      const id = card.id.replace(/^card-/, '');
      const game = gameById(id);
      const signal = game ? spreadSignal(game) : null;
      const gap = card.querySelector('.gap-value');
      const box = gap?.parentElement;
      if (!signal || !box || box.querySelector('.edge-band-badge')) return;
      const badge = document.createElement('span');
      badge.className = `edge-band-badge gap-${signal.band.key}`;
      badge.textContent = `${signal.band.range} band`;
      badge.title = `Provisional gap band: ${signal.band.label}. Research organization only.`;
      box.appendChild(badge);
    });
  }

  function enhanceDrawer(id) {
    const game = gameById(id);
    const content = document.getElementById('drawerContent');
    if (!game || !content) return;
    const existing = content.querySelector('#modelProductDrawer');
    if (existing) existing.remove();

    const spread = spreadSignal(game);
    const total = totalSignal(game);
    const spreadReady = readiness(game, 'spread');
    const totalReady = readiness(game, 'total');
    const section = document.createElement('section');
    section.className = 'model-product-drawer';
    section.id = 'modelProductDrawer';

    const spreadFair = spread?.team ? lineFor(spread.team, spread.fairRounded) : (spread ? 'Aligned' : '—');
    const spreadAlt = spread ? spreadAltText(game, spread) : 'No market spread reference';
    const spreadCushion = spread?.remainingCushion === null || spread?.remainingCushion === undefined ? '—' : `${spread.remainingCushion.toFixed(1)} pts`;
    const totalAlt = total ? totalAltText(total) : 'No market total reference';
    const totalCushion = total?.remainingCushion === null || total?.remainingCushion === undefined ? '—' : `${total.remainingCushion.toFixed(1)} pts`;

    section.innerHTML = `
      <div class="model-product-head">
        <div><span class="command-label">MODEL PRODUCT LAYER</span><h3>Edge, alternatives & readiness</h3></div>
        <span class="readiness-badge ${spreadReady.status.toLowerCase()}">${spreadReady.status}</span>
      </div>

      <div class="edge-analysis-grid">
        <article>
          <span>Spread research signal</span>
          <strong>${spread ? `${escapeHtml(spread.side)} · ${spread.edge.toFixed(1)} pts` : 'No comparison'}</strong>
          <small>${spread ? `Provisional band ${escapeHtml(spread.band.range)} · ${escapeHtml(spread.band.label)}` : 'Market spread unavailable'}</small>
        </article>
        <article>
          <span>Model fair spread · rounded</span>
          <strong class="model-value">${escapeHtml(spreadFair)}</strong>
          <small>Nearest half-point display line</small>
        </article>
        <article class="alt-analysis-card">
          <span>Computed spread alternative · unpriced</span>
          <strong>${escapeHtml(spreadAlt)}</strong>
          <small>Preserved model cushion: ${spreadCushion}</small>
        </article>
      </div>

      <div class="edge-analysis-grid total-analysis-grid">
        <article>
          <span>Total research signal</span>
          <strong>${total ? `${escapeHtml(total.side)} · ${total.edge.toFixed(1)} pts` : 'No comparison'}</strong>
          <small>${total ? `Model ${total.model.toFixed(1)} vs market ${total.market.toFixed(1)}` : 'Market total unavailable'}</small>
        </article>
        <article>
          <span>Model fair total · rounded</span>
          <strong class="model-value">${total ? total.fairRounded.toFixed(1) : '—'}</strong>
          <small>Totals validation: ${escapeHtml(String(STATE.config?.totalValidation || '—'))}</small>
        </article>
        <article class="alt-analysis-card">
          <span>Computed total alternative · unpriced</span>
          <strong>${escapeHtml(totalAlt)}</strong>
          <small>Preserved model cushion: ${totalCushion}</small>
        </article>
      </div>

      <div class="readiness-audit-block">
        <div class="readiness-title-row"><div><span class="command-label">SPREAD RELEASE GATES</span><strong>${spreadReady.passed}/${spreadReady.total} checks currently pass</strong></div><span class="readiness-badge ${spreadReady.status.toLowerCase()}">${spreadReady.status}</span></div>
        <div class="readiness-checks">${spreadReady.checks.map(check => `<div class="readiness-check ${check.pass ? 'pass' : 'block'}"><span aria-hidden="true">${check.pass ? '✓' : '×'}</span><strong>${escapeHtml(check.label)}</strong></div>`).join('')}</div>
        ${spreadReady.personnelReview ? '<div class="personnel-review-flag"><strong>Review flag:</strong> personnel / availability context is present in the model note.</div>' : ''}
        <p class="readiness-blocker-copy">${spreadReady.blockers.length ? `Current blockers: ${escapeHtml(spreadReady.blockers.join(' · '))}` : 'No current release blockers are detected by the website readiness checklist.'}</p>
      </div>

      <div class="total-hold-strip"><strong>Totals remain informational.</strong><span>Current total validation: ${escapeHtml(String(STATE.config?.totalValidation || '—'))}. The computed total alternative is a research target only.</span><small>${totalReady.passed}/${totalReady.total} total-readiness checks pass.</small></div>
      <p class="model-product-footnote">Alternative targets are computed from the model fair line and preserve at least ${ALT_CUSHION.toFixed(1)} points of model cushion when the current reference provides enough room. They are not prices, wagers, or release instructions.</p>`;

    const disclaimer = content.querySelector('.drawer-disclaimer');
    if (disclaimer) disclaimer.insertAdjacentElement('beforebegin', section);
    else content.appendChild(section);
  }

  function refresh() {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => {
      ensureTopSignals();
      renderTopSignals();
      addBandBadges();
      if (activeGameId && !document.getElementById('gameDrawer')?.hidden) enhanceDrawer(activeGameId);
    }, 40);
  }

  document.addEventListener('click', event => {
    const inspect = event.target.closest('[data-inspect-game]');
    if (inspect) {
      activeGameId = inspect.dataset.inspectGame;
      setTimeout(() => enhanceDrawer(activeGameId), 0);
    }

    const topPriority = event.target.closest('[data-top-priority]');
    if (topPriority) {
      const id = topPriority.dataset.topPriority;
      if (typeof toggleBookmark === 'function') toggleBookmark(id);
      setTimeout(refresh, 0);
    }

    if (event.target.closest('.bookmark-button') || event.target.closest('[data-drawer-priority]')) {
      setTimeout(refresh, 0);
    }
  });

  document.addEventListener('DOMContentLoaded', () => {
    const watchForCore = new MutationObserver(refresh);
    const hero = document.querySelector('.hero');
    const body = document.getElementById('projectionBody');
    const cards = document.getElementById('projectionCards');
    if (hero) watchForCore.observe(hero, { childList: true, subtree: true });
    if (body) watchForCore.observe(body, { childList: true });
    if (cards) watchForCore.observe(cards, { childList: true });

    const drawerContent = document.getElementById('drawerContent');
    if (drawerContent) {
      const drawerObserver = new MutationObserver(() => {
        if (activeGameId && !document.getElementById('gameDrawer')?.hidden) setTimeout(() => enhanceDrawer(activeGameId), 0);
      });
      drawerObserver.observe(drawerContent, { childList: true });
    }
    refresh();
  });
})();
