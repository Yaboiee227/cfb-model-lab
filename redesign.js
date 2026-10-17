(() => {
  let priorityOnly = false;
  let drawerGameId = null;
  let renderTimer = null;

  const savedSet = () => {
    try { return new Set(JSON.parse(localStorage.getItem('cb-bookmarks') || '[]')); }
    catch { return new Set(); }
  };

  const gameById = id => {
    try { return STATE.projections.find(game => game.gameId === id) || null; }
    catch { return null; }
  };

  function ensurePriorityToolbar() {
    const filterPanel = document.querySelector('.filter-panel');
    if (!filterPanel || document.getElementById('priorityToolbar')) return;
    const toolbar = document.createElement('div');
    toolbar.className = 'priority-toolbar';
    toolbar.id = 'priorityToolbar';
    toolbar.innerHTML = `
      <div class="priority-copy">
        <span class="priority-star" aria-hidden="true">★</span>
        <div><strong>Priority board</strong><small>Star matchups you want to keep at the top and inspect quickly.</small></div>
      </div>
      <div class="priority-actions">
        <span class="priority-count" id="priorityCount">0 saved</span>
        <button class="button button-ghost button-small" id="priorityOnlyToggle" type="button" aria-pressed="false">Priority only</button>
      </div>`;
    filterPanel.insertAdjacentElement('afterend', toolbar);
    document.getElementById('priorityOnlyToggle').addEventListener('click', () => {
      priorityOnly = !priorityOnly;
      applyPriorityView();
    });
  }

  function ensureDrawer() {
    if (document.getElementById('gameDrawer')) return;
    const drawer = document.createElement('div');
    drawer.className = 'game-drawer';
    drawer.id = 'gameDrawer';
    drawer.hidden = true;
    drawer.innerHTML = `
      <button class="drawer-backdrop" type="button" aria-label="Close matchup details" data-close-drawer></button>
      <aside class="drawer-panel" role="dialog" aria-modal="true" aria-labelledby="drawerTitle">
        <div class="drawer-head">
          <div><span class="command-label">MATCHUP INSPECTOR</span><h2 id="drawerTitle">Game details</h2></div>
          <button class="icon-button drawer-close" type="button" aria-label="Close matchup details" data-close-drawer>×</button>
        </div>
        <div id="drawerContent" class="drawer-content"></div>
      </aside>`;
    document.body.appendChild(drawer);
    drawer.addEventListener('click', event => {
      if (event.target.closest('[data-close-drawer]')) closeDrawer();
      const priorityButton = event.target.closest('[data-drawer-priority]');
      if (priorityButton && drawerGameId) {
        toggleBookmark(drawerGameId);
        window.setTimeout(() => {
          renderDrawer(drawerGameId);
          enhanceRenderedGames();
          applyPriorityView();
        }, 0);
      }
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !drawer.hidden) closeDrawer();
    });
  }

  function enhanceRenderedGames() {
    const saved = savedSet();
    document.querySelectorAll('#projectionBody tr[id^="game-"]').forEach(row => {
      const id = row.id.replace(/^game-/, '');
      row.classList.toggle('priority-game', saved.has(id));
      const actions = row.querySelector('.row-actions');
      if (actions && !actions.querySelector('.inspect-button')) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'mini-button inspect-button';
        button.dataset.inspectGame = id;
        button.setAttribute('aria-label', 'Inspect matchup details');
        button.textContent = 'i';
        actions.appendChild(button);
      }
    });

    document.querySelectorAll('#projectionCards .projection-card[id^="card-"]').forEach(card => {
      const id = card.id.replace(/^card-/, '');
      card.classList.toggle('priority-game', saved.has(id));
      const actions = card.querySelector('.projection-card-actions');
      if (actions && !actions.querySelector('.inspect-button')) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'mini-button inspect-button';
        button.dataset.inspectGame = id;
        button.textContent = 'ⓘ Inspect';
        actions.appendChild(button);
      }
      const game = gameById(id);
      if (game && !card.querySelector('.card-status-line')) {
        const line = document.createElement('div');
        line.className = 'card-status-line';
        line.innerHTML = `<span>${escapeHtml(game.signalStrength || 'Signal —')}</span><strong>${escapeHtml(game.releaseStatus || 'Research')}</strong>`;
        const head = card.querySelector('.projection-card-head');
        if (head) head.insertAdjacentElement('afterend', line);
      }
    });
    updatePriorityCount();
  }

  function applyPriorityView() {
    const saved = savedSet();
    const toggle = document.getElementById('priorityOnlyToggle');
    if (toggle) {
      toggle.setAttribute('aria-pressed', String(priorityOnly));
      toggle.textContent = priorityOnly ? 'Show all games' : 'Priority only';
      toggle.classList.toggle('active', priorityOnly);
    }

    let visible = 0;
    document.querySelectorAll('#projectionBody tr[id^="game-"]').forEach(row => {
      const id = row.id.replace(/^game-/, '');
      const show = !priorityOnly || saved.has(id);
      row.hidden = !show;
      if (show) visible += 1;
    });
    document.querySelectorAll('#projectionCards .projection-card[id^="card-"]').forEach(card => {
      const id = card.id.replace(/^card-/, '');
      card.hidden = priorityOnly && !saved.has(id);
    });

    const count = document.getElementById('projectionCount');
    if (priorityOnly && count) count.textContent = `${visible} priority game${visible === 1 ? '' : 's'} shown`;
    updatePriorityCount();
  }

  function updatePriorityCount() {
    const count = savedSet().size;
    const el = document.getElementById('priorityCount');
    if (el) el.textContent = `${count} saved`;
  }

  function renderDrawer(id) {
    const game = gameById(id);
    const content = document.getElementById('drawerContent');
    if (!game || !content) return;
    drawerGameId = id;
    const saved = savedSet().has(id);
    const gap = spreadGapLabel(game);
    const totalGap = totalGapLabel(game);
    const dq = game.dataQuality === null ? null : game.dataQuality * (game.dataQuality <= 1 ? 100 : 1);
    const score = game.projectedAwayPoints === null ? 'Insufficient baseline' : `${fmt1(game.projectedAwayPoints)} – ${fmt1(game.projectedHomePoints)}`;
    const conference = game.awayConference === game.homeConference ? game.homeConference : `${game.awayConference} • ${game.homeConference}`;
    const execution = game.executionVerified ? 'Execution verified' : 'Public reference / execution unverified';

    document.getElementById('drawerTitle').textContent = `${game.awayTeam} @ ${game.homeTeam}`;
    content.innerHTML = `
      <div class="drawer-game-meta">${formatDate(game.date)} · ${escapeHtml(game.kickoffET)} ET · ${escapeHtml(conference)}</div>
      <div class="drawer-scoreboard">
        <div><span>${escapeHtml(game.awayTeam)}</span><strong>${fmt1(game.projectedAwayPoints)}</strong><small>${pct(game.awayWinProbability)} win probability</small></div>
        <span class="drawer-at">@</span>
        <div><span>${escapeHtml(game.homeTeam)}</span><strong>${fmt1(game.projectedHomePoints)}</strong><small>${pct(game.homeWinProbability)} win probability</small></div>
      </div>
      <div class="drawer-priority-row">
        <div><span class="command-label">PROJECTED SCORE</span><strong>${escapeHtml(score)}</strong></div>
        <button class="button ${saved ? 'button-primary' : 'button-ghost'} button-small" type="button" data-drawer-priority>${saved ? '★ Priority game' : '☆ Add to priority'}</button>
      </div>
      <div class="drawer-grid">
        <article><span>Model spread</span><strong class="model-value">${escapeHtml(spreadLabel(game.homeTeam, game.awayTeam, game.modelSpreadHome))}</strong></article>
        <article><span>Market spread</span><strong class="market-value">${escapeHtml(spreadLabel(game.homeTeam, game.awayTeam, game.marketSpreadHome))}</strong></article>
        <article><span>Spread gap</span><strong class="${gap.magnitude >= 4 ? 'gap-value big' : 'gap-value'}">${escapeHtml(gap.text)}</strong></article>
        <article><span>Model total</span><strong class="model-value">${fmt1(game.modelTotal)}</strong></article>
        <article><span>Market total</span><strong class="market-value">${fmt1(game.marketTotal)}</strong></article>
        <article><span>Total comparison</span><strong>${escapeHtml(totalGap)}</strong></article>
        <article><span>Home implied ML</span><strong>${impliedMoneyline(game.homeWinProbability)}</strong></article>
        <article><span>Away implied ML</span><strong>${impliedMoneyline(game.awayWinProbability)}</strong></article>
        <article><span>Data quality</span><strong>${dq === null ? '—' : `${Math.round(dq)}%`}</strong></article>
      </div>
      <div class="drawer-status-block">
        <div><span>Signal strength</span><strong>${escapeHtml(game.signalStrength || '—')}</strong></div>
        <div><span>Release status</span><strong>${escapeHtml(game.releaseStatus || 'Research')}</strong></div>
      </div>
      <div class="drawer-context">
        <div><span>Market source</span><strong>${escapeHtml(game.marketSource || 'No current reference')}</strong></div>
        <div><span>Observed</span><strong>${escapeHtml(game.marketObservedAt || '—')}</strong></div>
        <div><span>Execution</span><strong>${escapeHtml(execution)}</strong></div>
      </div>
      <div class="drawer-note"><span class="command-label">MODEL NOTE</span><p>${escapeHtml(game.notes || 'No additional matchup note is currently attached.')}</p></div>
      <div class="drawer-disclaimer"><strong>Research signal, not a release.</strong> A large model/market gap does not override personnel, market-freshness or validation gates.</div>`;
  }

  function openDrawer(id) {
    const drawer = document.getElementById('gameDrawer');
    if (!drawer) return;
    renderDrawer(id);
    drawer.hidden = false;
    document.body.classList.add('drawer-open');
    window.setTimeout(() => drawer.querySelector('.drawer-close')?.focus(), 0);
  }

  function closeDrawer() {
    const drawer = document.getElementById('gameDrawer');
    if (!drawer) return;
    drawer.hidden = true;
    document.body.classList.remove('drawer-open');
    drawerGameId = null;
  }

  function scheduleEnhance() {
    clearTimeout(renderTimer);
    renderTimer = setTimeout(() => {
      ensurePriorityToolbar();
      ensureDrawer();
      enhanceRenderedGames();
      applyPriorityView();
    }, 30);
  }

  document.addEventListener('click', event => {
    const inspect = event.target.closest('[data-inspect-game]');
    if (inspect) openDrawer(inspect.dataset.inspectGame);
  });

  document.addEventListener('DOMContentLoaded', () => {
    ensurePriorityToolbar();
    ensureDrawer();
    const body = document.getElementById('projectionBody');
    const cards = document.getElementById('projectionCards');
    const observer = new MutationObserver(scheduleEnhance);
    if (body) observer.observe(body, { childList: true });
    if (cards) observer.observe(cards, { childList: true });
    scheduleEnhance();
  });
})();