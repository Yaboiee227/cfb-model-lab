(() => {
  if (window.__CB_PHASE3_FILTERS) return;
  window.__CB_PHASE3_FILTERS = true;

  const league = String(window.CB_ACTIVE_LEAGUE || 'cfb').toLowerCase() === 'nfl' ? 'nfl' : 'cfb';
  const q = selector => document.querySelector(selector);
  const qa = selector => [...document.querySelectorAll(selector)];
  const num = value => value === '' || value == null || !Number.isFinite(Number(value)) ? null : Number(value);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const normalize = value => String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  const fmt1 = value => num(value) === null ? '—' : Number(value).toFixed(1);
  const pct = value => num(value) === null ? '—' : `${Number(value).toFixed(1)}%`;

  const NFL_DIVISIONS = {
    ARI:'NFC West',ATL:'NFC South',BAL:'AFC North',BUF:'AFC East',CAR:'NFC South',CHI:'NFC North',CIN:'AFC North',CLE:'AFC North',
    DAL:'NFC East',DEN:'AFC West',DET:'NFC North',GB:'NFC North',HOU:'AFC South',IND:'AFC South',JAX:'AFC South',KC:'AFC West',
    LV:'AFC West',LAC:'AFC West',LAR:'NFC West',MIA:'AFC East',MIN:'NFC North',NE:'AFC East',NO:'NFC South',NYG:'NFC East',
    NYJ:'AFC East',PHI:'NFC East',PIT:'AFC North',SEA:'NFC West',SF:'NFC West',TB:'NFC South',TEN:'AFC South',WAS:'NFC East',WSH:'NFC East'
  };

  let rankings = null;
  let applying = false;
  let refreshFrame = 0;

  function appState() {
    try { return typeof STATE !== 'undefined' ? STATE : null; }
    catch (_) { return null; }
  }

  function filterValue(id) { return document.getElementById(id)?.value || ''; }

  function spreadGap(game) {
    const model = num(game.modelSpreadHome), market = num(game.marketSpreadHome);
    if (model === null || market === null) return { raw:null, magnitude:0 };
    const raw = market - model;
    return { raw, magnitude:Math.abs(raw) };
  }

  function totalGap(game) {
    const model = num(game.modelTotal), market = num(game.marketTotal);
    if (model === null || market === null) return 0;
    return Math.abs(model - market);
  }

  function kickoffValue(game) {
    try {
      if (typeof parseKickoff === 'function') return parseKickoff(game.date, game.kickoffET).getTime();
    } catch (_) {}
    const raw = `${game.date || ''} ${game.kickoffET || ''}`;
    const d = new Date(raw);
    return Number.isFinite(d.getTime()) ? d.getTime() : Number.MAX_SAFE_INTEGER;
  }

  function confidenceBand(game) {
    const home = num(game.homeWinProbability), away = num(game.awayWinProbability);
    if (home === null && away === null) return 'unknown';
    const favorite = Math.max(home ?? 0, away ?? 0);
    if (favorite >= 70) return 'high';
    if (favorite >= 60) return 'medium';
    return 'lean';
  }

  function betTypeAvailable(game, type) {
    if (!type) return true;
    if (type === 'spread') return num(game.modelSpreadHome) !== null && num(game.marketSpreadHome) !== null;
    if (type === 'total') return num(game.modelTotal) !== null && num(game.marketTotal) !== null;
    if (type === 'moneyline') return num(game.homeWinProbability) !== null || num(game.awayWinProbability) !== null;
    return true;
  }

  function currentFilters() {
    return {
      search: filterValue('teamSearch').trim().toLowerCase(),
      team: filterValue('cbTeamFilter'),
      week: filterValue('weekFilter'),
      conference: filterValue('conferenceFilter'),
      date: filterValue('dateFilter'),
      confidence: filterValue('cbConfidenceFilter'),
      betType: filterValue('cbBetTypeFilter'),
      sort: filterValue('sortFilter') || 'kickoff'
    };
  }

  function matches(game, filters) {
    if (filters.search && !`${game.awayTeam} ${game.homeTeam}`.toLowerCase().includes(filters.search)) return false;
    if (filters.team && game.awayTeam !== filters.team && game.homeTeam !== filters.team) return false;
    if (filters.week && String(game.week) !== filters.week) return false;
    if (filters.conference && game.awayConference !== filters.conference && game.homeConference !== filters.conference) return false;
    if (filters.date && game.date !== filters.date) return false;
    if (filters.confidence && confidenceBand(game) !== filters.confidence) return false;
    if (!betTypeAvailable(game, filters.betType)) return false;
    return true;
  }

  function sortGames(games, sort) {
    games.sort((a,b) => {
      if (sort === 'winprob') return Math.max(num(b.homeWinProbability) ?? 0,num(b.awayWinProbability) ?? 0)-Math.max(num(a.homeWinProbability) ?? 0,num(a.awayWinProbability) ?? 0);
      if (sort === 'spreadgap') return spreadGap(b).magnitude-spreadGap(a).magnitude;
      if (sort === 'totalgap') return totalGap(b)-totalGap(a);
      if (sort === 'quality') return (num(b.dataQuality) ?? 0)-(num(a.dataQuality) ?? 0);
      return kickoffValue(a)-kickoffValue(b);
    });
    return games;
  }

  function computeFiltered() {
    const state = appState();
    if (!state?.projections) return [];
    const filters = currentFilters();
    const games = sortGames(state.projections.filter(game => matches(game, filters)), filters.sort);
    const saved = games.filter(game => state.bookmarks?.has?.(game.gameId));
    const unsaved = games.filter(game => !state.bookmarks?.has?.(game.gameId));
    return saved.concat(unsaved);
  }

  function selectedTeamGames(team) {
    const state = appState();
    if (!state?.projections || !team) return [];
    return state.projections.filter(game => game.homeTeam === team || game.awayTeam === team).sort((a,b) => kickoffValue(a)-kickoffValue(b));
  }

  function teamResultRows(team) {
    const state = appState();
    if (!state?.results || !team) return [];
    const target = normalize(team);
    return state.results.filter(row => normalize(row.homeTeam) === target || normalize(row.awayTeam) === target);
  }

  function atsRecord(rows) {
    let wins=0, losses=0, pushes=0;
    rows.forEach(row => {
      const result = String(row.atsResult || '').toUpperCase();
      if (result === 'WIN') wins++;
      else if (result === 'LOSS') losses++;
      else if (result === 'PUSH') pushes++;
    });
    const decisions = wins + losses;
    return { wins, losses, pushes, pct:decisions ? wins/decisions*100 : null };
  }

  function teamRankRow(team) {
    if (!rankings?.teams?.length) return null;
    const key = normalize(team);
    return rankings.teams.find(row => normalize(row.teamName) === key || normalize(row.team) === key) || null;
  }

  function teamVisual(team) {
    const visual = window.CBTeamVisuals;
    if (!visual) return `<strong>${esc(team)}</strong>`;
    return visual.teamMarkup(team,{abbr:league === 'nfl' ? team : null,size:'sm',detail:'Team lens'});
  }

  function renderTeamLens() {
    const root = q('#cbTeamLensBody');
    if (!root) return;
    const team = filterValue('cbTeamFilter');
    if (!team) {
      root.innerHTML = '<div class="cb-team-lens-empty">Choose a team to isolate its projection rows, current model/market differences and preserved ATS history. This view never changes the projection.</div>';
      return;
    }
    const games = selectedTeamGames(team);
    const results = teamResultRows(team);
    const record = atsRecord(results);
    const comparable = games.filter(game => spreadGap(game).raw !== null);
    const edges = comparable.map(game => {
      const raw = spreadGap(game).raw;
      return game.homeTeam === team ? raw : -raw;
    });
    const avgEdge = edges.length ? edges.reduce((a,b)=>a+b,0)/edges.length : null;
    const probs = games.map(game => game.homeTeam === team ? num(game.homeWinProbability) : num(game.awayWinProbability)).filter(v => v !== null);
    const avgProb = probs.length ? probs.reduce((a,b)=>a+b,0)/probs.length : null;
    const rankRow = teamRankRow(team);
    const rankingLink = `ratings.html${league === 'nfl' ? '?league=nfl&' : '?'}team=${encodeURIComponent(team)}#replay`;
    const visible = games.slice(0,4);
    root.innerHTML = `<div class="cb-team-lens-body">
      <div class="cb-team-lens-identity">
        <div class="cb-team-lens-name">${teamVisual(team)}</div>
        <a class="cb-team-lens-link" href="${rankingLink}">Open rankings view ↗</a>
      </div>
      <div class="cb-team-lens-metrics">
        <div><span>Loaded games</span><strong>${games.length}</strong><small>projection rows</small></div>
        <div><span>Avg win probability</span><strong>${avgProb === null ? '—' : pct(avgProb)}</strong><small>display summary</small></div>
        <div><span>Avg spread difference</span><strong>${avgEdge === null ? '—' : `${avgEdge > 0 ? '+' : ''}${avgEdge.toFixed(1)}`}</strong><small>team-side points</small></div>
        <div><span>${rankRow ? 'CB rank' : 'ATS history'}</span><strong>${rankRow ? `#${rankRow.rank}` : `${record.wins}-${record.losses}${record.pushes ? `-${record.pushes}` : ''}`}</strong><small>${rankRow ? `${fmt1(rankRow.cbPoints)} CB pts` : (record.pct === null ? 'no graded rows' : `${record.pct.toFixed(1)}%`)}</small></div>
      </div>
      <div class="cb-team-lens-games">${visible.map(game => {
        const opponent = game.homeTeam === team ? game.awayTeam : game.homeTeam;
        const probability = game.homeTeam === team ? game.homeWinProbability : game.awayWinProbability;
        return `<div class="cb-team-lens-game"><div><strong>${esc(team)} vs ${esc(opponent)}</strong><small>Week ${esc(game.week)} · ${esc(game.date || '')} · ${pct(probability)} win probability</small></div><a href="?game=${encodeURIComponent(game.gameId)}#projections">Game ↗</a></div>`;
      }).join('')}</div>
    </div>`;
  }

  function nflDivisionFor(value) {
    const code = String(value || '').trim().toUpperCase().split(/\s+/)[0];
    return NFL_DIVISIONS[code] || null;
  }

  function projectionGroups(game) {
    if (league === 'nfl') return [...new Set([nflDivisionFor(game.awayTeam),nflDivisionFor(game.homeTeam)].filter(Boolean))];
    return [...new Set([game.awayConference,game.homeConference].filter(Boolean))];
  }

  function edgeGroups() {
    const state = appState();
    const games = state?.filtered || [];
    const groups = new Map();
    games.forEach(game => {
      const gap = spreadGap(game);
      if (gap.raw === null) return;
      projectionGroups(game).forEach(group => {
        if (!groups.has(group)) groups.set(group,{name:group,games:0,sum:0,max:0});
        const item = groups.get(group);
        item.games++;
        item.sum += gap.magnitude;
        item.max = Math.max(item.max,gap.magnitude);
      });
    });
    return [...groups.values()].map(item => ({...item,score:item.games ? item.sum/item.games : 0})).sort((a,b)=>b.score-a.score);
  }

  function atsGroups() {
    const rows = appState()?.results || [];
    const groups = new Map();
    rows.forEach(row => {
      let group = null;
      if (league === 'nfl') group = nflDivisionFor(row.atsProjection);
      else group = row.conference || null;
      if (!group) return;
      if (!groups.has(group)) groups.set(group,{name:group,wins:0,losses:0,pushes:0});
      const item = groups.get(group);
      const result = String(row.atsResult || '').toUpperCase();
      if (result === 'WIN') item.wins++;
      else if (result === 'LOSS') item.losses++;
      else if (result === 'PUSH') item.pushes++;
    });
    return [...groups.values()].map(item => {
      const decisions = item.wins + item.losses;
      return {...item,decisions,score:decisions ? item.wins/decisions*100 : -1};
    }).filter(item => item.decisions).sort((a,b)=>b.score-a.score || b.decisions-a.decisions);
  }

  function renderGroupLens() {
    const root = q('#cbGroupLensBody');
    if (!root) return;
    const metric = filterValue('cbGroupMetric') || 'edge';
    const groups = metric === 'ats' ? atsGroups() : edgeGroups();
    if (!groups.length) {
      const missing = league === 'cfb' && metric === 'edge'
        ? 'The current CFB projection snapshot does not preserve conference fields, so conference model-difference rankings are withheld rather than inferred. ATS conference views remain available from preserved graded rows.'
        : 'No preserved rows currently support this group ranking.';
      root.innerHTML = `<div class="cb-group-lens-empty">${esc(missing)}</div>`;
      return;
    }
    root.innerHTML = `<div class="cb-group-lens-body">${groups.slice(0,10).map((item,index) => `
      <div class="cb-group-row">
        <span class="cb-group-rank">${String(index+1).padStart(2,'0')}</span>
        <div class="cb-group-name"><strong>${esc(item.name)}</strong><small>${metric === 'ats' ? `${item.decisions} graded ATS decisions` : `${item.games} comparable game${item.games === 1 ? '' : 's'}`}</small></div>
        <div class="cb-group-value"><strong>${metric === 'ats' ? `${item.score.toFixed(1)}%` : `${item.score.toFixed(1)} pts`}</strong><small>${metric === 'ats' ? `${item.wins}-${item.losses}${item.pushes ? `-${item.pushes}` : ''}` : `max ${item.max.toFixed(1)}`}</small></div>
      </div>`).join('')}</div>`;
  }

  function syncChips() {
    const row = q('#cbPhase3Chips');
    if (!row) return;
    const filters = currentFilters();
    const chips = [];
    if (filters.team) chips.push(['Team',filters.team]);
    if (filters.week) chips.push(['Week',filters.week]);
    if (filters.conference) chips.push([league === 'nfl' ? 'Group' : 'Conference',filters.conference]);
    if (filters.confidence) chips.push(['Confidence',filters.confidence]);
    if (filters.betType) chips.push(['Bet type',filters.betType]);
    row.innerHTML = chips.map(([label,value]) => `<span class="cb-phase3-filter-chip"><strong>${esc(label)}:</strong> ${esc(value)}</span>`).join('');
  }

  function syncUrl() {
    const url = new URL(location.href);
    const filters = currentFilters();
    const mapping = { team:filters.team, confidence:filters.confidence, bet:filters.betType };
    Object.entries(mapping).forEach(([key,value]) => value ? url.searchParams.set(key,value) : url.searchParams.delete(key));
    history.replaceState(history.state,'',url);
  }

  function applyPhase3Filters({ syncHistory=true } = {}) {
    if (applying) return;
    const state = appState();
    if (!state?.projections?.length || typeof renderProjections !== 'function') return;
    applying = true;
    try {
      state.filtered = computeFiltered();
      renderProjections();
      renderTeamLens();
      renderGroupLens();
      syncChips();
      if (syncHistory) syncUrl();
      document.documentElement.dataset.cbPhase = '3';
    } finally {
      applying = false;
    }
  }

  function scheduleApply(options) {
    cancelAnimationFrame(refreshFrame);
    refreshFrame = requestAnimationFrame(() => applyPhase3Filters(options));
  }

  function addSelect(panel, id, label, options, before) {
    if (document.getElementById(id)) return document.getElementById(id);
    const wrapper = document.createElement('label');
    wrapper.innerHTML = `<span>${esc(label)}</span><select id="${esc(id)}">${options.map(option => `<option value="${esc(option.value)}">${esc(option.label)}</option>`).join('')}</select>`;
    panel.insertBefore(wrapper,before || null);
    return wrapper.querySelector('select');
  }

  function populateTeamSelect(select) {
    const state = appState();
    const teams = [...new Set((state?.projections || []).flatMap(game => [game.awayTeam,game.homeTeam]).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
    select.innerHTML = '<option value="">All teams</option>' + teams.map(team => `<option value="${esc(team)}">${esc(team)}</option>`).join('');
    const requested = new URL(location.href).searchParams.get('team');
    if (requested && teams.includes(requested)) select.value = requested;
  }

  function installControls() {
    const panel = q('#projections .filter-panel');
    if (!panel || q('#cbTeamFilter')) return;
    panel.classList.add('cb-phase3-filter-panel');
    const sortLabel = q('#sortFilter')?.closest('label');
    const reset = q('#resetFilters');
    const team = addSelect(panel,'cbTeamFilter','Team',[{value:'',label:'All teams'}],sortLabel);
    const confidence = addSelect(panel,'cbConfidenceFilter','Confidence',[
      {value:'',label:'All confidence'},
      {value:'high',label:'High · 70%+ favorite'},
      {value:'medium',label:'Medium · 60–69.9%'},
      {value:'lean',label:'Lean · below 60%'}
    ],sortLabel);
    const bet = addSelect(panel,'cbBetTypeFilter','Bet type',[
      {value:'',label:'All markets'},
      {value:'spread',label:'Spread comparison'},
      {value:'total',label:'Total comparison'},
      {value:'moneyline',label:'Win probability / ML'}
    ],sortLabel);
    populateTeamSelect(team);
    const params = new URL(location.href).searchParams;
    if (params.get('confidence')) confidence.value = params.get('confidence');
    if (params.get('bet')) bet.value = params.get('bet');

    const note = document.createElement('p');
    note.className = 'cb-phase3-control-note';
    note.textContent = 'Confidence is a display-only band of the already published win probability (70%+, 60–69.9%, below 60%). It is not a new model feature, release grade or promotion signal.';
    panel.appendChild(note);

    [team,confidence,bet].forEach(control => control.addEventListener('change',() => scheduleApply()));
    ['teamSearch','weekFilter','conferenceFilter','dateFilter','sortFilter'].forEach(id => {
      const control = document.getElementById(id);
      if (!control) return;
      control.addEventListener(id === 'teamSearch' ? 'input' : 'change',() => scheduleApply());
    });
    reset?.addEventListener('click',() => {
      team.value=''; confidence.value=''; bet.value='';
      scheduleApply();
    });
    document.addEventListener('click',event => {
      if (event.target.closest('.bookmark-button')) setTimeout(() => scheduleApply(),0);
    });
    document.addEventListener('cb:live-update',() => scheduleApply({syncHistory:false}));
    document.addEventListener('cb:sportsbooks-update',() => scheduleApply({syncHistory:false}));
  }

  function installLenses() {
    if (q('#cbPhase3Lenses')) return;
    const meta = q('#projections .table-meta');
    if (!meta) return;
    const lenses = document.createElement('div');
    lenses.id = 'cbPhase3Lenses';
    lenses.className = 'cb-phase3-lenses';
    lenses.innerHTML = `
      <section class="cb-phase3-panel" aria-labelledby="cbTeamLensTitle">
        <div class="cb-phase3-panel-head"><div><span>Team view</span><h3 id="cbTeamLensTitle">Team lens</h3></div><div class="cb-phase3-filter-chip-row" id="cbPhase3Chips"></div></div>
        <div id="cbTeamLensBody" class="cb-team-lens-empty">Choose a team to open its projection lens.</div>
      </section>
      <section class="cb-phase3-panel" aria-labelledby="cbGroupLensTitle">
        <div class="cb-phase3-panel-head"><div><span>${league === 'nfl' ? 'Division view' : 'Conference view'}</span><h3 id="cbGroupLensTitle">Group rankings</h3></div><label><span class="sr-only">Group ranking metric</span><select id="cbGroupMetric"><option value="edge">Model difference</option><option value="ats">ATS record</option></select></label></div>
        <div id="cbGroupLensBody" class="cb-group-lens-empty">Loading preserved group evidence…</div>
      </section>`;
    meta.insertAdjacentElement('afterend',lenses);
    q('#cbGroupMetric')?.addEventListener('change',renderGroupLens);
  }

  async function loadRankingContext() {
    try {
      const response = await fetch(`data/power-rankings/${league}.json`,{cache:'no-store'});
      if (response.ok) rankings = await response.json();
    } catch (_) {}
    renderTeamLens();
  }

  async function waitForCore() {
    for (let i=0;i<120;i++) {
      const state = appState();
      if (state?.projections?.length && q('#projections .filter-panel') && typeof renderProjections === 'function') return true;
      await new Promise(resolve => setTimeout(resolve,100));
    }
    return false;
  }

  async function init() {
    if (!await waitForCore()) return;
    installControls();
    installLenses();
    await loadRankingContext();
    applyPhase3Filters({syncHistory:false});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',() => init().catch(console.error),{once:true});
  else init().catch(console.error);
})();
