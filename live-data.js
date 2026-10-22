(() => {
  const ACTIVE_LEAGUE = String(window.CB_ACTIVE_LEAGUE || 'cfb').toLowerCase() === 'nfl' ? 'nfl' : 'cfb';
  const SCOREBOARD_URL = ACTIVE_LEAGUE === 'nfl' ? 'nfl_data/site/live-scoreboard.json' : 'data/live-scoreboard.json';
  const POLL_MS = 60000;
  const DETAIL_TTL_MS = 25000;
  const state = {
    games: [], lastUpdated: null, paused: localStorage.getItem('cb-live-paused') === '1',
    aliases: {}, mockMode: new URL(location.href).searchParams.get('mock') === '1' || localStorage.getItem('cb-live-mock') === '1',
    timer: null, wakeTimer: null, detailCache: new Map(), previous: new Map(), mock: null, initialized: false
  };

  const emit = (name, detail) => document.dispatchEvent(new CustomEvent(name, { detail }));
  const clean = value => String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/&/g,'and').replace(/[^a-z0-9]+/g,' ').replace(/\b(university|college|state university|the)\b/g,' ').replace(/\s+/g,' ').trim();

  async function loadAliases() {
    try {
      const data = await fetch('data/team-aliases.json', { cache:'no-store' }).then(r => r.ok ? r.json() : Promise.reject());
      state.aliases = data.aliases || data || {};
    } catch { state.aliases = {}; }
  }
  async function loadMock() {
    if (!state.mockMode) return null;
    if (state.mock) return state.mock;
    state.mock = await fetch('data/mock-live.json', { cache:'no-store' }).then(r => r.json());
    return state.mock;
  }

  function aliasSet(name) {
    const values = [name];
    const aliases = state.aliases[name] || [];
    values.push(...aliases);
    for (const [canonical, list] of Object.entries(state.aliases)) {
      if (canonical === name || list.some(v => clean(v) === clean(name))) values.push(canonical, ...list);
    }
    return new Set(values.map(clean).filter(Boolean));
  }
  function sameTeam(a,b) {
    const A = aliasSet(a), B = aliasSet(b);
    for (const value of A) if (B.has(value)) return true;
    const ca = clean(a), cb = clean(b);
    return ca === cb || ca.includes(cb) || cb.includes(ca);
  }

  function normalizeEspnEvent(event) {
    const c = event.competitions?.[0] || {};
    const homeRaw = c.competitors?.find(x => x.homeAway === 'home') || {};
    const awayRaw = c.competitors?.find(x => x.homeAway === 'away') || {};
    const status = c.status || {};
    const type = status.type || {};
    const situation = c.situation || {};
    const stateName = type.state || (type.completed ? 'post' : 'pre');
    return {
      eventId: String(event.id),
      date: event.date || c.date,
      state: stateName,
      statusText: type.shortDetail || type.detail || type.description || '',
      period: status.period || 0,
      clock: status.displayClock || '0:00',
      network: c.broadcasts?.flatMap(b => b.names || [b.name]).filter(Boolean).join(', ') || '',
      venue: c.venue?.fullName || '',
      home: {
        id: String(homeRaw.id || homeRaw.team?.id || ''),
        name: homeRaw.team?.shortDisplayName || homeRaw.team?.location || homeRaw.team?.displayName || '',
        displayName: homeRaw.team?.displayName || homeRaw.team?.shortDisplayName || '',
        score: Number(homeRaw.score || 0), logo: homeRaw.team?.logo || ''
      },
      away: {
        id: String(awayRaw.id || awayRaw.team?.id || ''),
        name: awayRaw.team?.shortDisplayName || awayRaw.team?.location || awayRaw.team?.displayName || '',
        displayName: awayRaw.team?.displayName || awayRaw.team?.shortDisplayName || '',
        score: Number(awayRaw.score || 0), logo: awayRaw.team?.logo || ''
      },
      possessionTeamId: String(situation.possession || situation.lastPlay?.team?.id || ''),
      down: Number.isFinite(Number(situation.down)) && Number(situation.down) > 0 ? Number(situation.down) : null,
      distance: Number.isFinite(Number(situation.distance)) && Number(situation.distance) >= 0 ? Number(situation.distance) : null,
      yardLine: Number.isFinite(Number(situation.yardLine)) ? Number(situation.yardLine) : null,
      isRedZone: Boolean(situation.isRedZone),
      lastPlay: situation.lastPlay?.text || '',
      playByPlayAvailable: Boolean(c.playByPlayAvailable)
    };
  }

  function matchProjection(game) {
    try {
      return (STATE.projections || []).find(p => sameTeam(p.homeTeam, game.home.name) && sameTeam(p.awayTeam, game.away.name)) ||
             (STATE.projections || []).find(p => sameTeam(p.homeTeam, game.home.displayName) && sameTeam(p.awayTeam, game.away.displayName)) || null;
    } catch { return null; }
  }

  function snapshotChanged(a,b) {
    if (!a || !b) return false;
    return a.home.score !== b.home.score || a.away.score !== b.away.score || a.statusText !== b.statusText || a.possessionTeamId !== b.possessionTeamId;
  }

  function scheduleNext() {
    clearTimeout(state.timer); clearTimeout(state.wakeTimer);
    if (state.paused || document.hidden) return;
    const live = state.games.some(g => g.state === 'in');
    if (live) {
      state.timer = setTimeout(refreshScoreboard, POLL_MS);
      return;
    }
    const next = state.games.filter(g => g.state === 'pre').map(g => new Date(g.date).getTime()).filter(t => t > Date.now()).sort((a,b) => a-b)[0];
    if (next) state.wakeTimer = setTimeout(refreshScoreboard, Math.max(5000, Math.min(next - Date.now() + 5000, 2147480000)));
  }

  async function refreshScoreboard() {
    if (state.paused || document.hidden) { scheduleNext(); return state.games; }
    try {
      let games;
      if (state.mockMode) {
        const mock = await loadMock();
        games = (mock.scoreboard?.events || []).map(g => ({ ...g }));
      } else {
        const json = await fetch(SCOREBOARD_URL, { cache:'no-store', headers:{'Accept':'application/json'} }).then(r => { if (!r.ok) throw new Error(`Local scoreboard ${r.status}`); return r.json(); });
        if (json.league && String(json.league).toLowerCase() !== ACTIVE_LEAGUE) throw new Error(`Scoreboard league mismatch: ${json.league}`);
        games = (json.events || []).map(normalizeEspnEvent);
      }
      const changes = [];
      for (const game of games) {
        game.projection = matchProjection(game);
        const old = state.previous.get(game.eventId);
        if (old && snapshotChanged(old, game)) changes.push(game.eventId);
        state.previous.set(game.eventId, JSON.parse(JSON.stringify(game)));
      }
      state.games = games;
      state.lastUpdated = new Date();
      emit('cb:live-update', { games, updatedAt:state.lastUpdated, changes, mockMode:state.mockMode, paused:state.paused, league:ACTIVE_LEAGUE });
      scheduleNext();
      return games;
    } catch (error) {
      emit('cb:live-error', { source:`${ACTIVE_LEAGUE.toUpperCase()} scoreboard`, error:String(error?.message || error) });
      scheduleNext();
      return state.games;
    }
  }

  async function fetchSummary(eventId, { force=false } = {}) {
    const cached = state.detailCache.get(String(eventId));
    if (!force && cached && Date.now() - cached.ts < DETAIL_TTL_MS) return cached.data;
    if (!state.mockMode) return cached?.data || null;
    try {
      const mock = await loadMock();
      const data = mock.summaries?.[eventId] || {};
      state.detailCache.set(String(eventId), { ts:Date.now(), data });
      return data;
    } catch (error) {
      emit('cb:live-error', { source:'Mock game detail', eventId, error:String(error?.message || error) });
      return cached?.data || null;
    }
  }

  function getGame(eventId) { return state.games.find(g => String(g.eventId) === String(eventId)) || null; }
  function getGameForProjection(gameId) { return state.games.find(g => g.projection?.gameId === gameId) || null; }
  function getProjectionForEvent(eventId) { return getGame(eventId)?.projection || null; }
  function setPaused(value) {
    state.paused = Boolean(value);
    localStorage.setItem('cb-live-paused', state.paused ? '1' : '0');
    if (!state.paused && !document.hidden) refreshScoreboard(); else scheduleNext();
    emit('cb:live-pause', { paused:state.paused });
  }
  function setMockMode(value) {
    localStorage.setItem('cb-live-mock', value ? '1' : '0');
    const url = new URL(location.href);
    value ? url.searchParams.set('mock','1') : url.searchParams.delete('mock');
    location.href = url.toString();
  }

  document.addEventListener('visibilitychange', () => {
    clearTimeout(state.timer); clearTimeout(state.wakeTimer);
    if (!document.hidden && !state.paused) refreshScoreboard();
  });

  async function init() {
    if (state.initialized) return state.games;
    state.initialized = true;
    await loadAliases();
    if (state.mockMode) await loadMock();
    return refreshScoreboard();
  }

  window.CBLiveData = {
    state, init, refreshScoreboard, fetchSummary, getGame, getGameForProjection, getProjectionForEvent,
    matchProjection, sameTeam, setPaused, setMockMode, normalizeName:clean, pollMs:POLL_MS, league:ACTIVE_LEAGUE
  };
})();