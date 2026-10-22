(() => {
  const MOBILE_BREAKPOINT = 820;
  let scheduled = false;
  let repairedOnce = false;

  const $ = id => document.getElementById(id);
  const state = () => {
    try { return typeof STATE !== 'undefined' ? STATE : null; }
    catch (_) { return null; }
  };

  function currentLeague() {
    return String(window.CB_ACTIVE_LEAGUE || document.documentElement.dataset.league || 'cfb').toLowerCase() === 'nfl' ? 'nfl' : 'cfb';
  }

  function formatDay(dateStr) {
    try {
      return new Date(`${dateStr}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
    } catch (_) {
      return dateStr;
    }
  }

  function filteredTotal() {
    const s = state();
    return Array.isArray(s?.filtered) ? s.filtered.length : 0;
  }

  function loadedTotal() {
    const s = state();
    return Array.isArray(s?.projections) ? s.projections.length : 0;
  }

  function priorityActive() {
    return $('priorityOnlyToggle')?.getAttribute('aria-pressed') === 'true';
  }

  function visibleCardTotal() {
    const cards = [...document.querySelectorAll('#projectionCards .projection-card[id^="card-"]')];
    return cards.filter(card => !card.hidden && getComputedStyle(card).display !== 'none').length;
  }

  function activeWeek() {
    const filter = $('weekFilter');
    if (filter?.value) return String(filter.value);
    const s = state();
    return s?.config?.currentWeek != null ? String(s.config.currentWeek) : '';
  }

  function clearToFullSlate({ keepWeek = true } = {}) {
    const s = state();
    if (!s) return false;
    const week = keepWeek ? (s.config?.currentWeek ?? '') : '';
    if (priorityActive()) $('priorityOnlyToggle')?.click();
    if ($('teamSearch')) $('teamSearch').value = '';
    if ($('conferenceFilter')) $('conferenceFilter').value = '';
    if ($('dateFilter')) $('dateFilter').value = '';
    if ($('weekFilter')) $('weekFilter').value = week;
    if ($('sortFilter')) $('sortFilter').value = 'kickoff';
    if (typeof filterProjections === 'function') filterProjections();
    sync();
    return true;
  }

  function openCurrentWeekProjections({ updateHistory = true } = {}) {
    if (!clearToFullSlate({ keepWeek: true })) return false;
    if (updateHistory && window.location.hash !== '#projections') {
      history.pushState({ cbSection: 'projections' }, '', '#projections');
    }
    const target = $('projections');
    window.setTimeout(() => target?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 40);
    return true;
  }

  function isSamePageProjectionLink(anchor) {
    if (!anchor) return false;
    try {
      const url = new URL(anchor.href, window.location.href);
      return url.origin === window.location.origin && url.pathname === window.location.pathname && url.hash === '#projections';
    } catch (_) {
      return anchor.getAttribute('href') === '#projections';
    }
  }

  function ensureToolbar() {
    const panel = document.querySelector('.filter-panel');
    if (!panel || $('slateNavigation')) return;
    const nav = document.createElement('div');
    nav.id = 'slateNavigation';
    nav.className = 'slate-navigation';
    nav.setAttribute('aria-label', 'Quick slate navigation');
    nav.innerHTML = `
      <div class="slate-navigation-summary">
        <div>
          <span class="command-label">FULL SLATE</span>
          <strong id="slateNavigationStatus">Loading games…</strong>
        </div>
        <button class="button button-ghost button-small" id="showFullSlate" type="button">Show all games</button>
      </div>
      <div class="slate-day-chips" id="slateDayChips" role="group" aria-label="Filter projections by date"></div>`;
    panel.insertAdjacentElement('afterend', nav);
    $('showFullSlate')?.addEventListener('click', () => clearToFullSlate({ keepWeek: true }));
  }

  function renderDayChips() {
    const s = state();
    const host = $('slateDayChips');
    const dateFilter = $('dateFilter');
    if (!s || !host || !dateFilter) return;

    const week = activeWeek();
    const games = (s.projections || []).filter(game => !week || String(game.week) === week);
    const dates = [...new Set(games.map(game => game.date).filter(Boolean))].sort();
    const selected = dateFilter.value || '';
    const allLabel = week ? `All Week ${week}` : 'All dates';
    host.innerHTML = '';

    const add = (value, label) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'slate-day-chip';
      button.dataset.date = value;
      button.setAttribute('aria-pressed', String(selected === value));
      button.textContent = label;
      button.addEventListener('click', () => {
        if (priorityActive()) $('priorityOnlyToggle')?.click();
        dateFilter.value = value;
        if (typeof filterProjections === 'function') filterProjections();
        sync();
        $('projectionCards')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      host.appendChild(button);
    };

    add('', allLabel);
    dates.forEach(date => add(date, formatDay(date)));
  }

  function updateSummary() {
    const loaded = loadedTotal();
    const filtered = filteredTotal();
    const priority = priorityActive();
    const shown = priority ? visibleCardTotal() : filtered;
    const week = activeWeek();
    const status = $('slateNavigationStatus');
    const count = $('projectionCount');
    if (!status || !loaded) return;

    const filtersActive = Boolean(priority || $('teamSearch')?.value || $('conferenceFilter')?.value || $('dateFilter')?.value);
    const leagueLabel = currentLeague().toUpperCase();
    status.textContent = priority
      ? `${shown} priority game${shown === 1 ? '' : 's'} shown · ${loaded} ${leagueLabel} loaded`
      : filtersActive
        ? `${shown} of ${loaded} ${leagueLabel} games shown`
        : `${loaded} ${leagueLabel}${week ? ` Week ${week}` : ''} games loaded`;
    if (count) count.textContent = priority
      ? `${shown} priority game${shown === 1 ? '' : 's'} shown · ${loaded} loaded`
      : filtersActive
        ? `${shown} of ${loaded} games shown`
        : `${shown} game${shown === 1 ? '' : 's'} shown · full slate loaded`;

    const fullButton = $('showFullSlate');
    if (fullButton) fullButton.hidden = !filtersActive && shown === loaded;
  }

  function verifyRenderIntegrity() {
    const s = state();
    if (!s || !Array.isArray(s.filtered) || !s.filtered.length) return;
    const expected = s.filtered.length;
    const rowCount = document.querySelectorAll('#projectionBody tr[id^="game-"]').length;
    const cardCount = document.querySelectorAll('#projectionCards .projection-card[id^="card-"]').length;

    if (rowCount === expected && cardCount === expected) {
      document.documentElement.dataset.slateRender = 'complete';
      repairedOnce = false;
      return;
    }

    document.documentElement.dataset.slateRender = 'mismatch';
    console.warn(`CB Model Projections render mismatch: expected ${expected}, rows ${rowCount}, cards ${cardCount}`);
    if (!repairedOnce && typeof renderProjections === 'function') {
      repairedOnce = true;
      renderProjections();
      window.setTimeout(sync, 60);
    }
  }

  function ensureMobileJump() {
    if (window.innerWidth > MOBILE_BREAKPOINT) return;
    const section = $('projections');
    const cards = $('projectionCards');
    if (!section || !cards || $('mobileProjectionJump')) return;
    const jump = document.createElement('button');
    jump.id = 'mobileProjectionJump';
    jump.className = 'mobile-projection-jump';
    jump.type = 'button';
    jump.textContent = '↓ Jump to current-week projections';
    jump.addEventListener('click', () => openCurrentWeekProjections());
    const heading = section.querySelector('.projections-heading');
    heading?.insertAdjacentElement('afterend', jump);
  }

  function sync() {
    scheduled = false;
    ensureToolbar();
    ensureMobileJump();
    renderDayChips();
    updateSummary();
    verifyRenderIntegrity();
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => window.setTimeout(sync, 20));
  }

  function boot() {
    ensureToolbar();
    ensureMobileJump();
    const body = $('projectionBody');
    const cards = $('projectionCards');
    const filters = ['teamSearch', 'weekFilter', 'conferenceFilter', 'dateFilter', 'sortFilter'];
    const observer = new MutationObserver(schedule);
    if (body) observer.observe(body, { childList: true });
    if (cards) observer.observe(cards, { childList: true });
    filters.forEach(id => {
      const el = $(id);
      if (!el) return;
      el.addEventListener(id === 'teamSearch' ? 'input' : 'change', schedule, { passive: true });
    });
    document.addEventListener('click', event => {
      if (event.target.closest('#priorityOnlyToggle')) window.setTimeout(schedule, 0);
      const anchor = event.target.closest('a[href]');
      if (!isSamePageProjectionLink(anchor)) return;
      event.preventDefault();
      openCurrentWeekProjections();
      const mobileToggle = $('cbMobileNavToggle');
      if (mobileToggle?.getAttribute('aria-expanded') === 'true') mobileToggle.click();
    });
    window.addEventListener('popstate', () => {
      if (window.location.hash === '#projections') openCurrentWeekProjections({ updateHistory: false });
    });
    window.addEventListener('resize', schedule, { passive: true });
    schedule();
  }

  window.CB_OPEN_CURRENT_WEEK_PROJECTIONS = openCurrentWeekProjections;

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
