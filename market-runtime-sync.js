(() => {
  if (window.CB_ACTIVE_LEAGUE === 'nfl') return; // Never match NFL abbreviations to CFB books/cache.
  const STALE_MS = 15 * 60 * 1000;
  const PREKICKOFF_LOOKBACK_MS = 45 * 60 * 1000;
  const CACHE_KEY = 'cb-pregame-market-freeze-v1';
  const BOOKS = ['fanduel', 'draftkings'];
  let aliasData = null;
  let syncing = false;

  const norm = value => String(value || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  const hasNum = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const bookLabel = key => key === 'fanduel' ? 'FanDuel' : key === 'draftkings' ? 'DraftKings' : key;

  function readCache() {
    try { return JSON.parse(localStorage.getItem(CACHE_KEY) || '{}'); }
    catch { return {}; }
  }
  function writeCache(cache) {
    try { localStorage.setItem(CACHE_KEY, JSON.stringify(cache)); } catch {}
  }

  async function aliases() {
    if (aliasData) return aliasData;
    try {
      const response = await fetch('data/team-aliases.json', { cache:'no-store' });
      const json = response.ok ? await response.json() : {};
      aliasData = json.aliases || {};
    } catch { aliasData = {}; }
    return aliasData;
  }

  function sameTeam(canonical, external, map) {
    const target = norm(external);
    const forms = [canonical, ...(map?.[canonical] || [])].map(norm).filter(Boolean);
    return forms.some(value => value === target || value.includes(target) || target.includes(value));
  }

  function matchRow(game, rows, map) {
    return rows.find(row => sameTeam(game.homeTeam, row.homeTeam, map) && sameTeam(game.awayTeam, row.awayTeam, map)) || null;
  }

  function candidateRows(row, type) {
    return BOOKS.map(key => ({ key, book:row?.books?.[key] }))
      .filter(({book}) => {
        if (!book?.updatedAt) return false;
        return type === 'spread' ? hasNum(book.spread?.home) : hasNum(book.total?.point);
      });
  }

  function freshCandidate(row, type) {
    return candidateRows(row, type)
      .filter(({book}) => {
        const ts = new Date(book.updatedAt).getTime();
        return Number.isFinite(ts) && Date.now() - ts <= STALE_MS;
      })
      .sort((a,b) => new Date(b.book.updatedAt).getTime() - new Date(a.book.updatedAt).getTime())[0] || null;
  }

  function preKickoffCandidate(row, type, kickoff) {
    return candidateRows(row, type)
      .filter(({book}) => {
        const ts = new Date(book.updatedAt).getTime();
        return Number.isFinite(ts) && ts <= kickoff && kickoff - ts <= PREKICKOFF_LOOKBACK_MS;
      })
      .sort((a,b) => new Date(b.book.updatedAt).getTime() - new Date(a.book.updatedAt).getTime())[0] || null;
  }

  function preserveOriginal(game) {
    if (game._originalMarketReference) return;
    game._originalMarketReference = {
      marketSpreadHome:game.marketSpreadHome,
      marketTotal:game.marketTotal,
      marketSource:game.marketSource,
      marketObservedAt:game.marketObservedAt,
      executionVerified:game.executionVerified
    };
  }

  function applyReference(game, ref) {
    preserveOriginal(game);
    if (hasNum(ref.marketSpreadHome)) game.marketSpreadHome = Number(ref.marketSpreadHome);
    if (hasNum(ref.marketTotal)) game.marketTotal = Number(ref.marketTotal);
    if (ref.marketSource) game.marketSource = ref.marketSource;
    if (ref.marketObservedAt) game.marketObservedAt = ref.marketObservedAt;
    game.executionVerified = Boolean(ref.executionVerified);
    game._liveMarketReference = true;
  }

  function freezeReference(game, row, spread, total, cache, label='live pregame') {
    const sources = [];
    if (spread) sources.push(`${bookLabel(spread.key)} spread`);
    if (total) sources.push(`${bookLabel(total.key)} total`);
    const timestamps = [spread?.book?.updatedAt, total?.book?.updatedAt].filter(Boolean)
      .sort((a,b) => new Date(b).getTime() - new Date(a).getTime());
    const ref = {
      marketSpreadHome:spread ? Number(spread.book.spread.home) : game.marketSpreadHome,
      marketTotal:total ? Number(total.book.total.point) : game.marketTotal,
      marketSource:sources.length ? `${sources.join(' · ')} · ${label}` : game.marketSource,
      marketObservedAt:timestamps[0] || game.marketObservedAt,
      executionVerified:Boolean(spread && total),
      cachedAt:new Date().toISOString(),
      commenceTime:row.commenceTime || null
    };
    cache[game.gameId] = ref;
    applyReference(game, ref);
  }

  function restoreFrozen(game, cache) {
    const ref = cache[game.gameId];
    if (!ref) return false;
    applyReference(game, ref);
    return true;
  }

  function triggerRerender() {
    if (typeof filterProjections === 'function') {
      filterProjections();
      return;
    }
    const target = document.querySelector('.hero') || document.getElementById('projectionBody');
    if (!target) return;
    const marker = document.createElement('span');
    marker.hidden = true;
    target.appendChild(marker);
    marker.remove();
  }

  async function sync(data) {
    if (syncing || !window.STATE && typeof STATE === 'undefined') return;
    syncing = true;
    try {
      const map = await aliases();
      const rows = data?.games || [];
      const cache = readCache();
      let changed = false;

      for (const game of (STATE.projections || [])) {
        const row = matchRow(game, rows, map);
        if (!row) {
          if (restoreFrozen(game, cache)) changed = true;
          continue;
        }

        const kickoff = new Date(row.commenceTime || 0).getTime();
        const pregame = Number.isFinite(kickoff) && kickoff > Date.now();
        if (!pregame) {
          if (restoreFrozen(game, cache)) {
            changed = true;
            continue;
          }
          if (Number.isFinite(kickoff)) {
            const spread = preKickoffCandidate(row, 'spread', kickoff);
            const total = preKickoffCandidate(row, 'total', kickoff);
            if (spread || total) {
              freezeReference(game, row, spread, total, cache, 'frozen pregame');
              changed = true;
            }
          }
          continue;
        }

        const spread = freshCandidate(row, 'spread');
        const total = freshCandidate(row, 'total');
        if (!spread && !total) continue;
        freezeReference(game, row, spread, total, cache);
        changed = true;
      }

      writeCache(cache);
      if (changed) {
        triggerRerender();
        document.dispatchEvent(new CustomEvent('cb:pregame-market-sync', { detail:{ syncedAt:new Date().toISOString() } }));
      }
    } finally { syncing = false; }
  }

  document.addEventListener('cb:sportsbooks-update', event => sync(event.detail?.data));

  async function init() {
    if (window.CBMarketsSportsbooks?.load) {
      const data = await window.CBMarketsSportsbooks.load(true);
      await sync(data);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once:true });
  else init();

  window.CBMarketRuntimeSync = { sync, readCache };
})();
