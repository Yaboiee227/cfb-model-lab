(() => {
  if (window.__CB_PHASE4_MOTION) return;
  window.__CB_PHASE4_MOTION = true;

  const league = String(window.CB_ACTIVE_LEAGUE || 'cfb').toLowerCase() === 'nfl' ? 'nfl' : 'cfb';
  const q = selector => document.querySelector(selector);
  const qa = selector => [...document.querySelectorAll(selector)];
  const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num = value => value === '' || value == null || !Number.isFinite(Number(value)) ? null : Number(value);
  const normalizeResult = value => {
    const result = String(value || '').trim().toUpperCase();
    if (result === 'WIN') return 'W';
    if (result === 'LOSS') return 'L';
    if (result === 'PUSH') return 'P';
    return result || '—';
  };

  let revealObserver = null;
  let mutationFrame = 0;
  let tickerSignature = '';

  function appState() {
    try { return typeof STATE !== 'undefined' ? STATE : null; }
    catch (_) { return null; }
  }

  function spreadDifference(game) {
    const model = num(game?.modelSpreadHome);
    const market = num(game?.marketSpreadHome);
    if (model === null || market === null) return null;
    const raw = market - model;
    return {
      raw,
      magnitude:Math.abs(raw),
      team:raw >= 0 ? game.homeTeam : game.awayTeam
    };
  }

  function dateValue(row) {
    const value = new Date(`${row?.date || ''}T12:00:00`).getTime();
    if (Number.isFinite(value)) return value;
    return Number(row?.week || 0) * 86400000;
  }

  function gameHref(gameId) {
    const params = new URLSearchParams();
    if (league === 'nfl') params.set('league','nfl');
    if (gameId) params.set('game',gameId);
    const query = params.toString();
    return `${query ? `?${query}` : ''}#projections`;
  }

  function topDifferenceItems() {
    const games = appState()?.projections || [];
    return games
      .map(game => ({ game, difference:spreadDifference(game) }))
      .filter(item => item.difference)
      .sort((a,b) => b.difference.magnitude - a.difference.magnitude)
      .slice(0,4)
      .map(({game,difference}) => ({
        kind:'difference',
        label:'Model diff',
        title:`${difference.team} ${difference.magnitude.toFixed(1)} pts`,
        detail:`${game.awayTeam} @ ${game.homeTeam} · Week ${game.week ?? '—'}`,
        href:gameHref(game.gameId)
      }));
  }

  function recentResultItems() {
    const rows = [...(appState()?.results || [])]
      .filter(row => row?.awayTeam && row?.homeTeam)
      .sort((a,b) => dateValue(b) - dateValue(a) || Number(b.week || 0) - Number(a.week || 0))
      .slice(0,4);

    return rows.map(row => ({
      kind:'result',
      label:'Recent grade',
      title:`${row.awayTeam} ${row.awayScore ?? '—'} · ${row.homeTeam} ${row.homeScore ?? '—'}`,
      detail:`ATS ${normalizeResult(row.atsResult)} · Total ${normalizeResult(row.totalResult)} · SU ${normalizeResult(row.suResult)}`,
      href:'#record'
    }));
  }

  function tickerItems() {
    const differences = topDifferenceItems();
    const results = recentResultItems();
    const items = [];
    const max = Math.max(differences.length, results.length);
    for (let i=0;i<max;i++) {
      if (differences[i]) items.push(differences[i]);
      if (results[i]) items.push(results[i]);
    }
    if (!items.length) {
      items.push({
        kind:'state',
        label:'Preserved data',
        title:'No comparable model/market rows or graded results loaded',
        detail:'The pulse remains descriptive and never reconstructs missing history.',
        href:'#projections'
      });
    }
    return items;
  }

  function itemMarkup(item) {
    return `<a class="cb-phase4-ticker-item" href="${esc(item.href)}">
      <span class="cb-phase4-ticker-tag" data-kind="${esc(item.kind)}">${esc(item.label)}</span>
      <span class="cb-phase4-ticker-copy"><strong>${esc(item.title)}</strong><small>${esc(item.detail)}</small></span>
    </a>`;
  }

  function ensureTickerHost() {
    let section = q('#cbPhase4Pulse');
    if (section) return section;
    const hero = q('#home');
    if (!hero) return null;
    section = document.createElement('section');
    section.id = 'cbPhase4Pulse';
    section.className = 'section-shell cb-phase4-pulse-shell';
    section.setAttribute('aria-label','Slate pulse from existing frozen and graded site data');
    section.innerHTML = `<div class="cb-phase4-pulse">
      <div class="cb-phase4-pulse-head">
        <div class="cb-phase4-pulse-title"><span class="cb-phase4-pulse-dot" aria-hidden="true"></span><div><strong>Slate pulse</strong><small>Top model/market differences + recent graded results</small></div></div>
        <span class="cb-phase4-pulse-state">Existing site data · no live API</span>
      </div>
      <div class="cb-phase4-ticker-viewport" aria-live="off">
        <div class="cb-phase4-ticker-track" id="cbPhase4TickerTrack"></div>
      </div>
    </div>`;
    hero.insertAdjacentElement('afterend',section);
    return section;
  }

  function renderTicker() {
    const host = ensureTickerHost();
    const track = q('#cbPhase4TickerTrack');
    if (!host || !track) return;
    const items = tickerItems();
    const signature = JSON.stringify(items);
    if (signature === tickerSignature && track.children.length) return;
    tickerSignature = signature;
    const group = items.map(itemMarkup).join('');
    track.innerHTML = `<div class="cb-phase4-ticker-group">${group}</div><div class="cb-phase4-ticker-group" aria-hidden="true">${group}</div>`;
    track.style.setProperty('--cb-phase4-ticker-duration',`${Math.max(30,items.length * 5.5)}s`);
  }

  function parseRecord(text) {
    const match = String(text || '').trim().match(/^(\d+)-(\d+)(?:-(\d+))?$/);
    if (!match) return null;
    return {
      wins:Number(match[1]),
      losses:Number(match[2]),
      pushes:match[3] === undefined ? null : Number(match[3])
    };
  }

  function recordText(record, progress) {
    const wins = Math.round(record.wins * progress);
    const losses = Math.round(record.losses * progress);
    if (record.pushes === null) return `${wins}-${losses}`;
    return `${wins}-${losses}-${Math.round(record.pushes * progress)}`;
  }

  function animateRecordCounter(element) {
    if (!element || element.dataset.cbPhase4Animating === 'true') return;
    const finalText = element.textContent.trim();
    const record = parseRecord(finalText);
    if (!record) return;
    if (element.dataset.cbPhase4Final === finalText) return;
    element.dataset.cbPhase4Final = finalText;

    if (reducedMotion()) {
      element.textContent = finalText;
      return;
    }

    element.dataset.cbPhase4Animating = 'true';
    element.classList.add('cb-phase4-counter-active');
    const started = performance.now();
    const duration = 720;
    const tick = now => {
      const elapsed = Math.min(1,(now - started) / duration);
      const eased = 1 - Math.pow(1 - elapsed,3);
      element.textContent = recordText(record,eased);
      if (elapsed < 1) {
        requestAnimationFrame(tick);
        return;
      }
      element.textContent = finalText;
      element.dataset.cbPhase4Animating = 'false';
      element.classList.remove('cb-phase4-counter-active');
      element.classList.add('cb-phase4-counter-settled');
      window.setTimeout(() => element.classList.remove('cb-phase4-counter-settled'),340);
    };
    requestAnimationFrame(tick);
  }

  function animateRecordCounters() {
    const targets = [
      ...qa('#recordTrackerV2 .rt-cards .record-card > strong'),
      q('#atsRecord'),
      q('#suRecord')
    ].filter(Boolean);
    [...new Set(targets)].forEach(animateRecordCounter);
  }

  function revealTargets(root = document) {
    const selectors = [
      '.projection-card',
      '#recordTrackerV2 .record-card',
      '.cb-phase3-panel',
      '.cb-layer-card',
      '.method-card',
      '.glossary-grid > article',
      '.research-shell',
      '.slate-audit',
      '.command-center',
      '.panel',
      '.support-card',
      '.contact-card'
    ];
    const nodes = selectors.flatMap(selector => [...(root.querySelectorAll?.(selector) || [])]);
    let index = 0;
    [...new Set(nodes)].forEach(node => {
      if (node.dataset.cbPhase4Reveal === 'true') return;
      node.dataset.cbPhase4Reveal = 'true';
      node.style.setProperty('--cb-reveal-index',String(index++ % 6));
      if (reducedMotion() || !revealObserver) {
        node.classList.add('cb-phase4-visible');
        return;
      }
      node.classList.add('cb-phase4-reveal');
      revealObserver.observe(node);
    });
  }

  function installRevealObserver() {
    if (reducedMotion() || !('IntersectionObserver' in window)) return;
    revealObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('cb-phase4-visible');
        revealObserver.unobserve(entry.target);
      });
    },{ threshold:.06, rootMargin:'0px 0px -5% 0px' });
  }

  function refreshPresentation() {
    renderTicker();
    animateRecordCounters();
    revealTargets(document);
    document.documentElement.dataset.cbPhase = '4';
  }

  function scheduleRefresh() {
    cancelAnimationFrame(mutationFrame);
    mutationFrame = requestAnimationFrame(refreshPresentation);
  }

  function installMutationObserver() {
    const observer = new MutationObserver(mutations => {
      if (mutations.every(mutation => mutation.target.closest?.('#cbPhase4Pulse'))) return;
      scheduleRefresh();
    });
    observer.observe(document.body,{ childList:true, subtree:true });
  }

  async function waitForState() {
    for (let i=0;i<120;i++) {
      const state = appState();
      if (state?.projections?.length || state?.results?.length) return true;
      await new Promise(resolve => window.setTimeout(resolve,100));
    }
    return false;
  }

  async function init() {
    installRevealObserver();
    ensureTickerHost();
    revealTargets(document);
    installMutationObserver();
    await waitForState();
    refreshPresentation();

    document.addEventListener('cb:live-update',scheduleRefresh);
    document.addEventListener('cb:sportsbooks-update',scheduleRefresh);
    window.matchMedia?.('(prefers-reduced-motion: reduce)').addEventListener?.('change',scheduleRefresh);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',() => init().catch(console.error),{once:true});
  else init().catch(console.error);
})();
